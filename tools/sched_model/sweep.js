#!/usr/bin/env node
// RMC scheduler weights/sizing sweep (OQ-20) against the golden model.
//
// Two staged passes over a representative trace suite (b4800 timing, queueArch —
// the adopted residency model):
//   A. arbiter weights   — K (control-vs-age), control tiers, DQ servo pools
//   B. sizing            — per-bank queue depth, TCAM admission depth
// plus a small R/W-organization probe (rawPause on/off).
//
// Objective: maximize mean DQ-busy across the suite while keeping the tail wait
// (max over traces of maxWait) bounded and every emit legal (0 violations, 0
// unscheduled). We report both so the knee is visible, and print a recommended
// config block ready to fold into the docs.
//
// Run:  node sweep.js            (full sweep, ranked tables + recommendation)
//       node sweep.js --quick    (smaller grid)

'use strict';
const {runScheduler, genTrace, validate, PARAMS} = require('./sched_test.js');

const BIN = 'b4800', P = PARAMS[BIN];
const QUICK = process.argv.includes('--quick');

// -- representative trace suite: address maps × R/W mix × locality × seed -------
const suite = [
  {nm: 'interleave 70R',      o: {map: 'interleave', readPct: 70, seed: 1}},
  {nm: 'interleave 50R',      o: {map: 'interleave', readPct: 50, seed: 2}},
  {nm: 'rowlocal 70R',        o: {map: 'rowlocal',   readPct: 70, seed: 3}},
  {nm: 'rowlocal 90R',        o: {map: 'rowlocal',   readPct: 90, seed: 4}},
  {nm: 'mixed hot',           o: {map: 'rowlocal',   readPct: 70, seed: 5, linear: 0.5, strided: 0.2, random: 0.15, hot: 0.15}},
  {nm: 'random-heavy',        o: {map: 'interleave', readPct: 60, seed: 6, linear: 0.4, strided: 0.2, random: 0.4}},
].map(s => ({...s, q: genTrace(QUICK ? 2500 : 4000, s.o)}));

// -- run a config across the suite, aggregate -----------------------------------
function evalCfg(opts) {
  let busySum = 0, tailWait = 0, meanWaitSum = 0, bad = 0;
  for (const s of suite) {
    const r = runScheduler(s.q, BIN, {queueArch: true, arbiter: 'weighted', ...opts});
    if (validate(r.cmds, P).length || r.unscheduled || r.guardHit) bad++;
    busySum += r.busy; tailWait = Math.max(tailWait, r.maxWait); meanWaitSum += r.meanWait;
  }
  const n = suite.length;
  return {busy: +(busySum / n).toFixed(1), tail: tailWait, mean: Math.round(meanWaitSum / n), bad};
}

const CTL = {
  '2/1/0': {CAS: 2, ACT: 1, PRE: 0},
  '3/1/0': {CAS: 3, ACT: 1, PRE: 0},
  '4/2/1': {CAS: 4, ACT: 2, PRE: 1},
};
const fmtRow = (label, m) =>
  `  ${label.padEnd(40)} busy=${String(m.busy).padStart(5)}%  tailWait=${String(m.tail).padStart(5)}  meanWait=${String(m.mean).padStart(4)}${m.bad ? `  BAD=${m.bad}` : ''}`;

// ================================ PASS A =======================================
console.log(`\n================ PASS A — arbiter weights (queueArch, depth=8 tcam=32) ================`);
const Ks = QUICK ? [200, 1000, 100000] : [50, 200, 1000, 5000, 100000];
const servos = [
  {tag: 'servo-off',  o: {servo: false}},
  {tag: 'servo-std',  o: {servo: true, poolLow: 2, poolHigh: 6, lookahead: 12}},
  {tag: 'servo-aggr', o: {servo: true, poolLow: 3, poolHigh: 8, lookahead: 20}},
];
let rowsA = [];
for (const [ctlTag, control] of Object.entries(CTL))
  for (const K of Ks)
    for (const sv of servos) {
      const m = evalCfg({control, K, ...sv.o});
      rowsA.push({label: `ctl=${ctlTag} K=${String(K).padStart(6)} ${sv.tag}`, m, K, ctlTag, control, sv});
    }
// rank: legal first, then busy desc, then tail asc
const rank = rows => rows.slice().sort((a, b) => a.m.bad - b.m.bad || b.m.busy - a.m.busy || a.m.tail - b.m.tail);
console.log('\n  -- top 10 by DQ-busy (legal only) --');
for (const r of rank(rowsA).slice(0, 10)) console.log(fmtRow(r.label, r.m));
// a fairness-aware pick: best busy among configs whose tail wait is within 1.5x of the min legal tail
const legalA = rowsA.filter(r => !r.m.bad);
const minTail = Math.min(...legalA.map(r => r.m.tail));
const balanced = legalA.filter(r => r.m.tail <= minTail * 1.5).sort((a, b) => b.m.busy - a.m.busy)[0];
const bestBusyA = rank(rowsA)[0];
console.log(`\n  min legal tailWait = ${minTail}`);
console.log('  balanced pick (best busy within 1.5x min tail):');
console.log(fmtRow(balanced.label, balanced.m));

// carry the balanced arbiter into Pass B
const ARB = {control: balanced.control, K: balanced.K, ...balanced.sv.o};

// ================================ PASS B =======================================
console.log(`\n================ PASS B — sizing (balanced arbiter fixed) ================`);
const depths = QUICK ? [4, 8] : [2, 4, 6, 8, 12];
const tcams  = QUICK ? [16, 32] : [8, 16, 32];
let rowsB = [];
for (const bankDepth of depths)
  for (const tcam of tcams) {
    const m = evalCfg({...ARB, bankDepth, tcam});
    rowsB.push({label: `bankDepth=${String(bankDepth).padStart(2)} tcam=${String(tcam).padStart(2)} (inflight≤${16 * bankDepth})`, m, bankDepth, tcam});
  }
console.log('\n  -- all sizing points (legal-ranked) --');
for (const r of rank(rowsB)) console.log(fmtRow(r.label, r.m));
// knee: smallest total in-flight whose busy is within 1pt of the best legal busy
const legalB = rowsB.filter(r => !r.m.bad);
const bestBusyB = Math.max(...legalB.map(r => r.m.busy));
const knee = legalB.filter(r => r.m.busy >= bestBusyB - 1)
  .sort((a, b) => (16 * a.bankDepth) - (16 * b.bankDepth) || a.tcam - b.tcam)[0];
console.log(`\n  best legal busy = ${bestBusyB}%`);
console.log('  knee (smallest in-flight within 1pt of best busy):');
console.log(fmtRow(knee.label, knee.m));

// ============================ R/W ORG PROBE ====================================
console.log(`\n================ R/W organization probe (rawPause on/off, unified FIFO) ================`);
for (const rp of [true, false]) {
  const m = evalCfg({...ARB, bankDepth: knee.bankDepth, tcam: knee.tcam, rawPause: rp});
  console.log(fmtRow(`rawPause=${rp}`, m));
}
console.log('  (unified per-bank FIFO program-orders same-bank; rawPause is the guard for the split variant)');

// ============================ RECOMMENDATION ===================================
console.log(`\n================ RECOMMENDED CONFIG (fold into docs / pkg intent) ================`);
console.log(`  arbiter   : weighted`);
console.log(`  control   : CAS/ACT/PRE = ${balanced.ctlTag}`);
console.log(`  K         : ${balanced.K}      (control-vs-age scale)`);
console.log(`  servo     : ${balanced.sv.tag}  ${JSON.stringify(balanced.sv.o)}`);
console.log(`  AGE_MAX   : 256   (row-lock cap; retained from baseline)`);
console.log(`  bankDepth : ${knee.bankDepth}   → total in-flight ≤ ${16 * knee.bankDepth}`);
console.log(`  tcam      : ${knee.tcam}   (admission depth)`);
console.log(`  R/W org   : unified per-bank + tag (rawPause guard reserved for split)`);
console.log(`  → suite mean DQ-busy ${knee.m.busy}%, tailWait ${knee.m.tail}, all legal\n`);
