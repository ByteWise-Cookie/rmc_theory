// OW-7 buffer-depth sweep: read-buffer (rdCap) vs write-buffer (wrCap) sizing.
// Question: read=write=64 (plan) vs N_WR = 2-3x N_RD (KB), and is there a read-depth floor?
// Config = the RTL-reference weighted arbiter + queueArch (OQ-20 design point).
const {runScheduler, genTrace, validate, PARAMS} = require('./sched_test.js');

const CFG = {queueArch: true, arbiter: "weighted", control: {CAS: 2, ACT: 1, PRE: 0},
             K: 5000, servo: false, ageMax: 256, tcam: 32, bankDepth: 8};
const BIN = "b4800";
const N = 6000;
const SEEDS = [3, 5, 7, 9, 11, 21];
const MAPS = ["interleave", "rowlocal"];

// average a metric set over seeds x maps at a given readPct and cap pair
function avg(rdCap, wrCap, readPct) {
  let busy = 0, span = 0, tailR = 0, meanR = 0, tailW = 0, meanW = 0, acts = 0, unsched = 0, viol = 0, n = 0;
  for (const seed of SEEDS) for (const map of MAPS) {
    const q = genTrace(N, {seed, map, readPct});
    const r = runScheduler(q, BIN, {...CFG, rdCap, wrCap});
    busy += r.busy; span += r.span; tailR += r.maxWaitR; meanR += r.meanWaitR;
    tailW += r.maxWaitW; meanW += r.meanWaitW; unsched += r.unscheduled;
    acts += r.cmds.filter(c => c.type === "ACT").length;
    viol += validate(r.cmds, PARAMS[BIN]).length; n++;
  }
  const R = x => Math.round(x / n);
  return {busy: R(busy), span: R(span), tailR: R(tailR), meanR: R(meanR),
          tailW: R(tailW), meanW: R(meanW), acts: R(acts), unsched, viol};
}

function row(label, m) {
  console.log(`  ${label.padEnd(16)} busy=${String(m.busy).padStart(3)}%  span=${String(m.span).padStart(6)}  ` +
    `readTail=${String(m.tailR).padStart(6)} readMean=${String(m.meanR).padStart(5)}  ` +
    `writeTail=${String(m.tailW).padStart(6)} writeMean=${String(m.meanW).padStart(5)}  ` +
    `ACTs=${String(m.acts).padStart(5)}  unsched=${m.unsched} viol=${m.viol}`);
}

console.log(`OW-7 buffer-depth sweep  (bin=${BIN}, N=${N}, ${SEEDS.length} seeds x ${MAPS.length} maps, arbiter=weighted)`);
console.log(`floor hypothesis (I24): row-miss lookahead >= tRCD+tRP = 80 tCK = 10 bursts (BL2=8)\n`);

console.log("A) READ-DEPTH FLOOR  (wrCap=inf, readPct=70) — find where busy saturates & read tail settles");
for (const rd of [4, 8, 12, 16, 24, 32, 48, 64]) row(`rdCap=${rd}`, avg(rd, Infinity, 70));

console.log("\nB) WRITE-DEPTH EFFECT  (rdCap=32, readPct=70) — does a bigger write buffer help reads?");
for (const wr of [8, 16, 32, 48, 64, 96, 128]) row(`wrCap=${wr}`, avg(32, wr, 70));

console.log("\nB2) WRITE-DEPTH under write-heavy mix  (rdCap=32, readPct=50)");
for (const wr of [16, 32, 64, 96, 128]) row(`wrCap=${wr}`, avg(32, wr, 50));

console.log("\nC) CANDIDATE HEAD-TO-HEAD  (readPct=70)");
for (const [rd, wr, tag] of [[32, 64, "KB v1"], [32, 96, "KB v2 3x"], [48, 96, "2x"],
                             [64, 64, "plan 64/64"], [64, 128, "2x big"], [48, 48, "sym small"]])
  row(`${rd}/${wr} ${tag}`, avg(rd, wr, 70));

console.log("\nC2) CANDIDATE HEAD-TO-HEAD under write-heavy mix (readPct=50)");
for (const [rd, wr, tag] of [[32, 64, "KB v1"], [32, 96, "KB v2 3x"], [64, 64, "plan"], [64, 128, "big"]])
  row(`${rd}/${wr} ${tag}`, avg(rd, wr, 50));
