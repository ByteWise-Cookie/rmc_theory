#!/usr/bin/env node
// RMC greedy scheduler — golden reference model + test harness.
//
// This is the cycle-accurate JS model the eventual RTL must match (the "golden
// model" referenced by docs/scheduler_staged_logic.md). It was previously a
// scratchpad-only file recovered from the published bench artifact 1d271c33;
// it now lives in the repo so it stops getting wiped between sessions.
//
// runScheduler(queue, bin, opts) emits the full PRE/ACT/CAS command stream for a
// request queue and scores DQ-busy. An independent windowed timing checker
// (validate) catches any illegal command the scheduler emits.
//
// Features added this pass (all opt-gated so they can be A/B'd):
//   opts.win       in-flight window — only WIN entries visible to the pickers
//                  (default Infinity = old behaviour; 64 = the buffer model)
//   opts.lock      age-capped per-bank row-lock (default true). Hold the open
//                  row while it has demand; release on demand==0 OR
//                  oldest-miss-age >= ageMax (the hot-row starvation guard).
//   opts.ageMax    lock age cap in tCK (default 256).
//   opts.pingpong  model the 32-wide 2-batch classify: classification is
//                  registered and refreshed one 32-half per cycle, so a
//                  just-opened row's other-half hits are seen 1 cycle late.
//   opts.queueArch post-mentor residency split (docs/scheduler_queue_arch.md): a
//                  short TCAM classifies then EVICTS each request to a per-bank
//                  in-flight FIFO. TCAM = opts.tcam slots (default 32), each bank
//                  queue opts.bankDepth deep (default 8). Pickers see only the
//                  queue HEADS (one active request per bank). legal()/emit()/arbiter
//                  are unchanged — only the candidate set changes.
//   opts.rawPause  (queueArch) hold a RAW read at admission until the older write
//                  to the same address drains — no bypass, no reorder (default true).
//   opts.promote   (queueArch) row-hit promotion (default true). On eviction, cluster
//                  same-row entries (insert after the last same-row entry, not the tail)
//                  so a row-hit that arrives behind a same-bank miss batches with its
//                  siblings instead of stranding — reopening the row + stalling the
//                  miss's PRE to AGE_MAX. Reorders only across different rows (no hazard).
//
// Run:  node sched_test.js            (self-test suite)
//       node sched_test.js --demo     (small worked trace)

'use strict';

const BL2 = 8;
const PARAMS = {
  toy:   {tCK:5,     RL:3,  WL:1,  tRCD:4,  tRP:4,  tRAS:7,  tCCD_S:8, tCCD_L:8,  tCCD_L_WR:32, tWTR_S:4, tWTR_L:16, tRTP:12, tWR:6,  tWPRE:1, tRTR:2, tPPD:2, tRRD_S:8, tRRD_L:8,  tFAW:32, tRFC:59,  tRFCsb:26},
  b4800: {tCK:0.4167,RL:40, WL:38, tRCD:39, tRP:39, tRAS:77, tCCD_S:8, tCCD_L:12, tCCD_L_WR:32, tWTR_S:6, tWTR_L:24, tRTP:18, tWR:72, tWPRE:2, tRTR:2, tPPD:2, tRRD_S:8, tRRD_L:12, tFAW:32, tRFC:708, tRFCsb:312},
};

const isRD  = t => t === "RD" || t === "RDA";
const isWR  = t => t === "WR" || t === "WRA";
const isCAS = t => isRD(t) || isWR(t);
const isPRE = t => t === "PRE" || t === "PREA";
const lat   = (t, p) => isRD(t) ? p.RL : p.WL;
const tRTW  = p => p.RL + BL2 - p.WL + p.tWPRE;
const rels  = (a, b) => { const sr = a.rank === b.rank, sbg = sr && a.bg === b.bg; return {sr, sbg, sbk: sbg && a.bank === b.bank}; };

// ---- DDR timing constraints (a issued before b) — the independent checker ----
function cons(a, b, p) {
  const {sr, sbg, sbk} = rels(a, b), A = a.type, B = b.type, o = [];
  o.push({min: 2, name: "CA bus"});
  if (sbk) {
    if (A === "ACT" && isCAS(B)) o.push({min: p.tRCD, name: "tRCD ACT→CAS"});
    if (A === "ACT" && isPRE(B)) o.push({min: p.tRAS, name: "tRAS ACT→PRE"});
    if (A === "ACT" && B === "ACT") o.push({min: p.tRAS + p.tRP, name: "tRC ACT→ACT"});
    if (isRD(A) && isPRE(B)) o.push({min: p.tRTP, name: "tRTP RD→PRE"});
    if (isWR(A) && isPRE(B)) o.push({min: p.WL + BL2 + p.tWR, name: "WR→PRE"});
    if (isPRE(A) && B === "ACT") o.push({min: p.tRP, name: "tRP PRE→ACT"});
    if (isRD(A) && B === "ACT") o.push({min: p.tRTP + p.tRP, name: "RD→ACT"});
    if (isWR(A) && B === "ACT") o.push({min: p.WL + BL2 + p.tWR + p.tRP, name: "WR→ACT"});
  }
  if (isCAS(A) && isCAS(B)) {
    if (isRD(A) && isRD(B)) o.push({min: !sr ? p.tCCD_S + p.tRTR : (sbg ? p.tCCD_L : p.tCCD_S), name: "RD→RD"});
    else if (isWR(A) && isWR(B)) o.push({min: !sr ? p.tCCD_S + p.tRTR : (sbg ? p.tCCD_L_WR : p.tCCD_S), name: "WR→WR"});
    else if (isRD(A) && isWR(B)) o.push({min: tRTW(p), name: "tRTW RD→WR"});
    else if (isWR(A) && isRD(B)) o.push({min: !sr ? p.WL + BL2 + p.tRTR : (sbg ? p.WL + BL2 + p.tWTR_L : p.WL + BL2 + p.tWTR_S), name: "WR→RD"});
  }
  if (A === "ACT" && B === "ACT" && !sbk && sr) o.push({min: sbg ? p.tRRD_L : p.tRRD_S, name: sbg ? "tRRD_L" : "tRRD_S"});
  if (isPRE(A) && isPRE(B) && sr) o.push({min: p.tPPD, name: "tPPD"});
  if (sr) {
    if (A === "REF" || A === "PREA") { if (A === "REF") o.push({min: p.tRFC, name: "tRFC"}); }
  }
  return o;
}

// Windowed validation: DDR constraints are local in time (<= tRFC), so only
// compare each command against prior commands within LOOKBACK cycles. O(N*W).
function validate(cmds, p) {
  const v = [], cs = [...cmds].sort((a, b) => a.cycle - b.cycle);
  const LOOKBACK = p.tRFC + p.tRAS + p.tRP + 16;
  for (let j = 0; j < cs.length; j++) {
    const b = cs[j];
    for (let i = j - 1; i >= 0; i--) {
      const a = cs[i], d = b.cycle - a.cycle;
      if (d > LOOKBACK) break;
      for (const c of cons(a, b, p)) if (d < c.min - 1e-6)
        v.push({a, b, name: c.name, need: Math.round(c.min), have: Math.round(d)});
    }
  }
  // tFAW: 4 ACT within tFAW, per rank
  const byR = {};
  cs.filter(c => c.type === "ACT").forEach(c => (byR[c.rank] = byR[c.rank] || []).push(c));
  for (const r in byR) { const A = byR[r]; for (let i = 3; i < A.length; i++) { const d = A[i].cycle - A[i - 3].cycle; if (d < p.tFAW - 1e-6) v.push({a: A[i - 3], b: A[i], name: "tFAW", need: p.tFAW, have: Math.round(d)}); } }
  // DQ collision: bursts must be BL2 apart on the data bus
  const bu = cs.filter(c => isCAS(c.type)).map(c => ({c, s: c.cycle + lat(c.type, p)})).sort((x, y) => x.s - y.s);
  for (let i = 1; i < bu.length; i++) if (bu[i].s < bu[i - 1].s + BL2 - 1e-6)
    v.push({a: bu[i - 1].c, b: bu[i].c, name: "DQ collision", need: BL2, have: Math.round(bu[i].s - bu[i - 1].s)});
  return v;
}

// ------------------------- the greedy scheduler ---------------------------
function runScheduler(queue, bin, opts = {}) {
  const p = PARAMS[bin];
  const policy    = opts.policy    || "greedy";
  const batchMode = opts.batchMode || "adaptive";
  const refAt     = opts.refAt     || 0;
  const WIN       = opts.win       || Infinity;
  const lockOn    = opts.lock !== false;               // age-capped row-lock
  const AGE_MAX   = opts.ageMax    || 256;
  const pingpong  = !!opts.pingpong;
  const queueArch = !!opts.queueArch;                  // admission (short TCAM) + per-bank queues
  const TCAM_SIZE = opts.tcam      || 32;              // searchable admission slots
  const bankDepth = opts.bankDepth || 8;               // per-bank in-flight FIFO depth
  const rawPause  = opts.rawPause !== false;           // block RAW reads at admission (queueArch)
  const wheel     = !!opts.wheel;                       // timing-wheel candidate advance (queueArch): instead of
                                                        // scanning every tCK, jump gc to the soonest ready-time
                                                        // among the bank heads (event-driven). Same policy/pick —
                                                        // only the idle-advance changes, so DQ-busy is identical;
                                                        // the win is fewer scheduler iterations (the scan cost).
  const promote   = opts.promote !== false;            // row-hit promotion: ON by default. cluster same-row
                                                       // in the bank queue (insert after the last
                                                       // same-row entry, not the tail) so a later
                                                       // same-row request batches with its siblings
                                                       // instead of stranding behind an intervening
                                                       // different-row miss. Reorders only across
                                                       // DIFFERENT rows (different addresses → no
                                                       // hazard); same-row order preserved (RAW/WAW).
  // ---- weight arbiter (OQ-20/OQ-21 sweep; default "busy" = the baseline pick order) ----
  // weight(lane) = K·control[lane] + age + (lane==ACT ? servo_mod : 0); argmax over legal.
  // GUARDRAIL: DQ free now AND a legal CAS exists ⇒ CAS wins absolutely (never idle DQ).
  const arbiter   = opts.arbiter   || "busy";          // "busy" | "weighted"
  const K         = opts.K         ?? 1000;            // control-vs-age scale
  const wCtl      = opts.control   || {CAS: 2, ACT: 1, PRE: 0};   // SJF tiers
  const servoOn   = opts.servo !== false;              // DQ-occupancy servo on ACT
  const POOL_LOW  = opts.poolLow   ?? 2;               // ready-CAS pool thin threshold
  const POOL_HIGH = opts.poolHigh  ?? 6;               // ready-CAS pool deep threshold
  const LOOKAHEAD = opts.lookahead ?? 12;             // DQ-freeing horizon (≈tCCD_L)
  const SERVO_BOOST = opts.servoBoost ?? K;           // one control tier of ACT boost
  const SERVO_DAMP  = opts.servoDamp  ?? K;           // one control tier of ACT damp

  const BGN = 4, BKN = 4, NB = BGN * BKN, NR = 2, bidx = q => q.bg * BKN + q.bank;
  const mk = () => ({open: false, row: -1, nAct: 0, nPre: 0, nCas: 0, lockAge: 0});
  const bk  = Array.from({length: NR}, () => Array.from({length: NB}, mk));
  const bgS = Array.from({length: NR}, () => Array.from({length: BGN}, () => ({nCasBg: 0, nActBg: 0})));
  const rkS = Array.from({length: NR}, () => ({nActAny: 0, faw: [], nRdWr: 0, nWrRd: 0}));
  const G = {nCasAny: 0, dqFree: 0, caFree: 0, nPreAny: 0, lastCasBg: -1};

  let toks = queue.map((q, i) => ({...q, id: i, done: false, gid: null, wstate: null, firstSeen: null}));
  let maxWait = 0, sumWait = 0, doneCount = 0;         // fairness metric (waiting tCK to service)
  let activeCount = toks.length;
  let pendR = toks.reduce((a, t) => a + (t.dir === "R" ? 1 : 0), 0), pendW = activeCount - pendR;
  const demand = Array.from({length: NR}, () => Array.from({length: NB}, () => ({})));
  for (const t of toks) demand[t.rank][bidx(t)][t.row] = (demand[t.rank][bidx(t)][t.row] || 0) + 1;

  const liveCmd = t => { const b = bk[t.rank][bidx(t)]; return (b.open && b.row === t.row) ? "CAS" : b.open ? "PRE" : "ACT"; };
  const nextCmd = t => (pingpong && t.wstate) ? t.wstate : liveCmd(t);
  const fawOk = (t, gc) => { const f = rkS[t.rank].faw; return f.length < 3 || gc - f[f.length - 3] >= p.tFAW; };

  function legal(t, c, gc) {
    const r = t.rank, b = bk[r][bidx(t)], g = bgS[r][t.bg], rk = rkS[r];
    if (gc < G.caFree) return false;
    if (c === "ACT") return !b.open && gc >= b.nAct && gc >= g.nActBg && gc >= rk.nActAny && fawOk(t, gc);
    if (c === "PRE") {
      if (!b.open || gc < b.nPre || gc < G.nPreAny) return false;
      const dem = demand[r][bidx(t)][b.row] || 0;
      if (!lockOn) return dem === 0;                    // plain demand-gate
      if (dem === 0) return true;                        // lock released — drained
      return b.lockAge >= AGE_MAX;                       // hot-row hammer — force break
    }
    // CAS: if this bank's lock has aged out (cap fired), stop serving its hits so the
    // burst can finish, tRTP clears, and the starved miss's PRE can force-break in.
    if (lockOn && b.lockAge >= AGE_MAX) return false;
    const l = t.dir === "R" ? p.RL : p.WL;
    return b.open && b.row === t.row && gc >= b.nCas && gc >= g.nCasBg && gc >= G.nCasAny &&
           (gc + l) >= G.dqFree && (t.dir === "R" ? gc >= rk.nWrRd : gc >= rk.nRdWr);
  }

  // timing-wheel ready-time estimate: earliest gc at which t's next command could pass legal().
  // Mirrors the legal() thresholds (timers only; lock/demand gating still enforced by legal()).
  function readyAt(t, c) {
    const r = t.rank, b = bk[r][bidx(t)], g = bgS[r][t.bg], rk = rkS[r];
    let x = G.caFree;
    if (c === "ACT") { x = Math.max(x, b.nAct, g.nActBg, rk.nActAny); const f = rk.faw; if (f.length >= 3) x = Math.max(x, f[f.length - 3] + p.tFAW); }
    else if (c === "PRE") { x = Math.max(x, b.nPre, G.nPreAny); }
    else { const l = t.dir === "R" ? p.RL : p.WL; x = Math.max(x, b.nCas, g.nCasBg, G.nCasAny, G.dqFree - l, t.dir === "R" ? rk.nWrRd : rk.nRdWr); }
    return x;
  }

  const out = [];
  let nid = 1, nextG = 0, iters = 0;
  function emit(t, c, gc) {
    const r = t.rank, b = bk[r][bidx(t)], g = bgS[r][t.bg], rk = rkS[r];
    if (t.gid === null) t.gid = nextG++;
    const type = c === "CAS" ? (t.dir === "R" ? "RD" : "WR") : c, role = c === "CAS" ? "cas" : c === "ACT" ? "act" : "pre";
    out.push({id: nid++, gid: t.gid, role, type, cycle: gc, rank: r, bg: t.bg, bank: t.bank, row: t.row, col: 0});
    G.caFree = gc + 2;
    if (c === "ACT") {
      b.open = true; b.row = t.row; b.lockAge = 0;       // acquire lock on the opened row
      b.nCas = gc + p.tRCD; b.nPre = gc + p.tRAS;
      g.nActBg = gc + p.tRRD_L; rk.nActAny = gc + p.tRRD_S; rk.faw.push(gc);
    } else if (c === "PRE") {
      b.open = false; b.lockAge = 0; b.nAct = gc + p.tRP; G.nPreAny = gc + p.tPPD;
    } else {
      const l = t.dir === "R" ? p.RL : p.WL;
      g.nCasBg = gc + (t.dir === "R" ? p.tCCD_L : p.tCCD_L_WR); G.nCasAny = gc + p.tCCD_S;
      G.dqFree = gc + l + BL2; G.lastCasBg = t.bg;
      if (t.dir === "R") { b.nPre = Math.max(b.nPre, gc + p.tRTP); rk.nRdWr = gc + tRTW(p); }
      else { b.nPre = Math.max(b.nPre, gc + p.WL + BL2 + p.tWR); rk.nWrRd = gc + p.WL + BL2 + p.tWTR_L; }
      t.done = true; activeCount--; if (t.dir === "R") pendR--; else pendW--;
      demand[r][bidx(t)][t.row]--;
      const w = gc - (t.firstSeen ?? gc); if (w > maxWait) maxWait = w; sumWait += w; doneCount++;
    }
  }

  let gc = 0, guard = 0, flips = 0, refs = 0, mode = pendR > 0 ? "R" : "W", stall = 0, gateLoss = 0;
  const STALL = p.tRAS + p.tRP, batch = batchMode !== "off", adaptive = batchMode === "adaptive", FLIP_COST = BL2;
  const doFlip = () => { mode = mode === "R" ? "W" : "R"; flips++; gateLoss = 0; stall = 0; };
  let nextRef = refAt > 0 ? refAt : Infinity, refPhase = 0, preaGc = 0;
  const allBanks = f => { for (let r = 0; r < NR; r++) for (let bi = 0; bi < NB; bi++) f(bk[r][bi]); };
  const jobCost = t => { const b = bk[t.rank][bidx(t)], l = t.dir === "R" ? p.RL : p.WL; return (b.open && b.row === t.row) ? l : b.open ? p.tRP + p.tRCD + l : p.tRCD + l; };
  let head = 0;                                           // first non-done tok (window base)

  // ---- admission (short TCAM) + per-bank in-flight queues (opts.queueArch) --------
  let adm = 0;                                            // next source tok to admit into TCAM
  const tcam = [];                                        // admitted, awaiting classify+evict
  const bq = Array.from({length: NR}, () => Array.from({length: NB}, () => [])); // per-bank FIFO
  // RAW: read blocked while an OLDER, not-yet-emitted write to the same address is in
  // flight. Model has no column, so {rank,bank,row} is the same-address proxy (over-blocks
  // different-column, never reorders — safe for a golden model). Reserved mainly for the
  // split-R/W-queue variant; the unified per-bank FIFO here already program-orders same-bank.
  const rawBlocked = t => {
    if (!(rawPause && t.dir === "R")) return false;
    const r = t.rank, qi = bidx(t);
    for (const w of tcam)     if (w.dir === "W" && w.id < t.id && w.rank === r && bidx(w) === qi && w.row === t.row) return true;
    for (const w of bq[r][qi]) if (w.dir === "W" && w.id < t.id && w.row === t.row) return true;
    return false;
  };
  const admitAndEvict = () => {
    // retire heads whose CAS has emitted, then top up TCAM in arrival order
    for (let r = 0; r < NR; r++) for (let bi = 0; bi < NB; bi++) { const q = bq[r][bi]; while (q.length && q[0].done) q.shift(); }
    while (tcam.length < TCAM_SIZE && adm < toks.length) { const t = toks[adm++]; if (t.firstSeen === null) t.firstSeen = gc; tcam.push(t); }  // aging clock starts at admission (total in-system wait)
    // classify is done at admit; evict to the bank queue when it has room and RAW is clear
    for (let i = 0; i < tcam.length; ) {
      const t = tcam[i];
      if (rawBlocked(t)) { i++; continue; }               // RAW: hold read in TCAM until write drains
      const q = bq[t.rank][bidx(t)];
      if (q.length < bankDepth) {
        if (promote) {                                     // insert after the last same-row entry
          let ins = q.length;
          for (let k = q.length - 1; k >= 0; k--) if (q[k].row === t.row) { ins = k + 1; break; }
          q.splice(ins, 0, t);
        } else q.push(t);                                  // strict FIFO: tail
        tcam.splice(i, 1);
      }
      else i++;                                            // bank queue full → backpressure, stay in TCAM
    }
  };

  // event-driven idle advance: soonest ready-time among the visible heads (else +1).
  const wheelNext = vis => {
    let mn = Infinity;
    for (const t of vis) { const ra = readyAt(t, nextCmd(t)); if (ra > gc && ra < mn) mn = ra; }
    return (mn === Infinity || mn <= gc) ? gc + 1 : mn;
  };

  while ((activeCount > 0 || refPhase !== 0) && guard++ < 20000000) {
    iters++;
    if (gc < G.caFree) { gc = G.caFree; continue; }
    if (refPhase === 0 && gc >= nextRef) refPhase = 1;
    if (refPhase === 1) {
      let anyOpen = false, maxPre = 0;
      allBanks(b => { if (b.open) { anyOpen = true; maxPre = Math.max(maxPre, b.nPre); } });
      if (!anyOpen) refPhase = 2;
      else if (gc >= maxPre) { out.push({id: nid++, gid: null, role: null, type: "PREA", cycle: gc, rank: 0, bg: 0, bank: 0, row: 0}); allBanks(b => { b.open = false; b.nAct = gc + p.tRP; }); G.caFree = gc + 2; preaGc = gc; refPhase = 2; continue; }
      else { gc++; continue; }
    }
    if (refPhase === 2) {
      if (gc >= preaGc + p.tRP) { out.push({id: nid++, gid: null, role: null, type: "REF", cycle: gc, rank: 0, bg: 0, bank: 0, row: 0}); allBanks(b => { b.nAct = gc + p.tRFC; }); G.caFree = gc + 2; nextRef = Infinity; refPhase = 0; refs++; continue; }
      else { gc++; continue; }
    }

    // ---- build the candidate set ----
    let vis;
    if (queueArch) {
      // admission + per-bank queues: only the HEAD of each bank queue is active (a bank
      // serves one row-cycle at a time). Classify happened at admission; pickers see heads.
      admitAndEvict();
      vis = [];
      for (let r = 0; r < NR; r++) for (let bi = 0; bi < NB; bi++) { const q = bq[r][bi]; if (q.length) vis.push(q[0]); }
    } else {
      // window model: first WIN non-done toks by queue order
      while (head < toks.length && toks[head].done) head++;
      vis = [];
      for (let i = head; i < toks.length && vis.length < WIN; i++) if (!toks[i].done) vis.push(toks[i]);
      // ping-pong classify: refresh one 32-entry half of the window
      if (pingpong) {
        const half = gc & 1;                             // even→A(0..31), odd→B(32..63)
        for (let k = 0; k < vis.length; k++) {
          const inA = k < 32;
          if ((half === 0) === inA) vis[k].wstate = liveCmd(vis[k]);
          else if (vis[k].wstate === null) vis[k].wstate = liveCmd(vis[k]); // first-admit seed
        }
      }
    }

    if (policy === "sjw") {                              // baseline shortest-job-winner
      let picked = null, pcmd = null, bestCost = Infinity;
      for (const t of vis) { const c = liveCmd(t); if (!legal(t, c, gc)) continue; const cost = jobCost(t); if (cost < bestCost || (cost === bestCost && (!picked || t.id < picked.id))) { picked = t; pcmd = c; bestCost = cost; } }
      if (picked) emit(picked, pcmd, gc); else { gc++; continue; }
    } else {                                             // greedy busy-first + batch + rotate
      if (batch) { if (mode === "R" && pendR === 0 && pendW > 0) doFlip(); else if (mode === "W" && pendW === 0 && pendR > 0) doFlip(); }
      let cas = null, casScore = Infinity, act = null, pre = null, oppCas = false, readyCas = 0;
      const missWait = Array.from({length: NR}, () => new Array(NB).fill(false));
      for (const t of vis) {
        if (t.firstSeen === null) t.firstSeen = gc;      // waiting clock starts when first visible
        const c = nextCmd(t);
        if (c === "PRE") { const b = bk[t.rank][bidx(t)]; if ((demand[t.rank][bidx(t)][b.row] || 0) > 0) missWait[t.rank][bidx(t)] = true; }
        if (!legal(t, c, gc)) continue;
        if (c === "CAS") { if (batch && t.dir !== mode) { oppCas = true; continue; } readyCas++; const s = (t.bg === G.lastCasBg ? 1e9 : 0) + t.id; if (s < casScore) { cas = t; casScore = s; } }
        else if (c === "ACT") { if (!act || t.id < act.id) act = t; }
        else { if (!pre || t.id < pre.id) pre = t; }
      }
      const age = t => gc - (t.firstSeen ?? gc);
      // age the per-bank lock: a bank with an open row still owing demand while a
      // miss waits is holding the lock — count it toward the AGE_MAX force-break.
      if (lockOn) for (let r = 0; r < NR; r++) for (let bi = 0; bi < NB; bi++) {
        const b = bk[r][bi];
        if (b.open && missWait[r][bi] && (demand[r][bi][b.row] || 0) > 0) b.lockAge++; else b.lockAge = 0;
      }
      const charge = (oppCas && !cas && gc >= G.dqFree);
      // --- pick the command: baseline busy-first, or the weighted arbiter (§6) ---
      let picked = null, pickCmd = null;
      if (arbiter === "weighted") {
        const dqFreeIn = G.dqFree - gc;
        if (cas && dqFreeIn <= 0 && readyCas >= 1) { picked = cas; pickCmd = "CAS"; }   // GUARDRAIL
        else {
          let servoMod = 0;
          if (servoOn) {
            if (readyCas <= POOL_LOW && dqFreeIn > 0 && dqFreeIn <= LOOKAHEAD) servoMod = SERVO_BOOST;
            else if (readyCas >= POOL_HIGH) servoMod = -SERVO_DAMP;
          }
          const cand = [];
          if (cas) cand.push({t: cas, c: "CAS", w: K * wCtl.CAS + age(cas)});
          if (act) cand.push({t: act, c: "ACT", w: K * wCtl.ACT + age(act) + servoMod});
          if (pre) cand.push({t: pre, c: "PRE", w: K * wCtl.PRE + age(pre)});
          if (cand.length) { cand.sort((a, b) => b.w - a.w || a.t.id - b.t.id); picked = cand[0].t; pickCmd = cand[0].c; }
        }
      } else if (cas) { picked = cas; pickCmd = "CAS"; }
      else if (act) { picked = act; pickCmd = "ACT"; }
      else if (pre) { picked = pre; pickCmd = "PRE"; }
      if (picked) { if (charge) gateLoss += 2; stall = 0; emit(picked, pickCmd, gc); }
      else { if (charge) gateLoss++; stall++; if (batch && stall >= STALL && ((mode === "R" && pendW > 0) || (mode === "W" && pendR > 0))) doFlip(); else gc = (wheel && queueArch) ? wheelNext(vis) : gc + 1; continue; }
      if (adaptive && gateLoss >= FLIP_COST && ((mode === "R" && pendW > 0) || (mode === "W" && pendR > 0))) doFlip();
    }
    if (!queueArch && activeCount * 3 < toks.length - head) toks = toks.filter((t, i) => i < head || !t.done), head = 0;
  }

  let bu = 0, s0 = Infinity, s1 = -Infinity;
  for (const c of out) if (isCAS(c.type)) { bu++; const ds = c.cycle + lat(c.type, p); if (ds < s0) s0 = ds; if (ds + BL2 > s1) s1 = ds + BL2; }
  const span = bu ? s1 - s0 : 0, busy = span ? Math.round(100 * bu * BL2 / span) : 0;
  const meanWait = doneCount ? Math.round(sumWait / doneCount) : 0;
  return {cmds: out, busy, span, bursts: bu, flips, refs, unscheduled: activeCount, guardHit: guard >= 20000000, maxWait, meanWait, iters};
}

// ------------------------------ trace generator ---------------------------
function genTrace(N, opts = {}) {
  const rw = opts.readPct ?? 70, stride = opts.stride ?? 8, map = opts.map ?? "interleave";
  const w = {linear: opts.linear ?? 0.6, strided: opts.strided ?? 0.2, random: opts.random ?? 0.2, hot: opts.hot ?? 0};
  const tot = w.linear + w.strided + w.random + w.hot;
  let seed = opts.seed ?? 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const q = [];
  let addr = 0;
  for (let i = 0; i < N; i++) {
    const r = rnd() * tot;
    if (r < w.linear) addr += 1;
    else if (r < w.linear + w.strided) addr += stride;
    else if (r < w.linear + w.strided + w.random) addr = Math.floor(rnd() * 1e6);
    else addr = 0;                                         // hot: same address
    let bg, bank, row;
    if (map === "interleave") { bg = addr & 3; bank = (addr >> 2) & 3; row = (addr >> 4) & 0xffff; }
    else { row = addr & 0xffff; bank = (addr >> 16) & 3; bg = (addr >> 18) & 3; } // row-local
    q.push({dir: rnd() * 100 < rw ? "R" : "W", rank: 0, bg, bank, row});
  }
  return q;
}

// -------------------------------- harness ---------------------------------
function run(name, queue, bin, opts) {
  const r = runScheduler(queue, bin, opts);
  const v = validate(r.cmds, PARAMS[bin]);
  const ok = v.length === 0 && r.unscheduled === 0 && !r.guardHit;
  const tag = ok ? "PASS" : "FAIL";
  console.log(`  [${tag}] ${name.padEnd(34)} busy=${String(r.busy).padStart(3)}%  bursts=${String(r.bursts).padStart(5)}  flips=${String(r.flips).padStart(4)}  viol=${v.length}  unsched=${r.unscheduled}${r.guardHit ? "  GUARD-HIT" : ""}`);
  if (v.length) for (const x of v.slice(0, 4)) console.log(`         x ${x.b.type}@${x.b.cycle} breaks ${x.name} vs ${x.a.type}@${x.a.cycle}: need ${x.need} have ${x.have}`);
  return {r, v, ok};
}

function selfTest() {
  let pass = 0, fail = 0;
  const chk = res => { if (res.ok) pass++; else fail++; return res; };

  console.log("\n== correctness: 0 violations / 0 unscheduled, both bins ==");
  for (const bin of ["toy", "b4800"]) {
    console.log(` bin=${bin}`);
    for (const [nm, o] of [
      ["greedy adaptive", {}],
      ["greedy +win64", {win: 64}],
      ["greedy +win64 +pingpong", {win: 64, pingpong: true}],
      ["greedy +win64 +pp +lock", {win: 64, pingpong: true, lock: true}],
      ["greedy +queueArch", {queueArch: true}],
      ["greedy +queueArch +lock", {queueArch: true, lock: true}],
      ["sjw baseline +win64", {policy: "sjw", win: 64}],
      ["+refresh @2000", {win: 64, refAt: 2000}],
    ]) chk(run(nm, genTrace(3000, {seed: 7}), bin, o));
  }

  console.log("\n== ping-pong claim: 1-cycle staleness is harmless (busy unchanged) ==");
  for (const map of ["interleave", "rowlocal"]) {
    const q = genTrace(4000, {map, seed: 3});
    const base = runScheduler(q, "b4800", {win: 64});
    const pp   = runScheduler(q, "b4800", {win: 64, pingpong: true});
    const d = base.busy - pp.busy;
    const ok = Math.abs(d) <= 1;                          // within 1pt = harmless
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] map=${map.padEnd(10)} base=${base.busy}%  pingpong=${pp.busy}%  Δ=${d}pt (claim: |Δ|≤1)`);
  }

  console.log("\n== row-lock age cap: hot-row hammer must not starve the miss ==");
  // Bank 0: a relentless hot-row-0 stream keeps demand>0 forever, plus one miss
  // (row 1, id 1) that can only be served when the lock force-breaks. The miss sits
  // AFTER the row-0 opener so it must wait behind the lock. Without the age cap it is
  // starved to the tail (served only when the hot stream finally drains); with the
  // cap it is force-served near AGE_MAX.
  const hammer = [];
  hammer.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0});         // id0: opens+hits row 0
  hammer.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 1});         // id1: the starved miss
  for (let i = 0; i < 600; i++) hammer.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0}); // keep demand>0
  const missCyc = res => { const c = res.cmds.find(c => c.type === "RD" && c.row === 1); return c ? c.cycle : Infinity; };
  const noCap = runScheduler(hammer, "toy", {win: 64, lock: true, ageMax: 1e9});
  const cap   = runScheduler(hammer, "toy", {win: 64, lock: true, ageMax: 200});
  const tNo = missCyc(noCap), tCap = missCyc(cap);
  const ok = tCap < 500 && tCap < tNo / 4;                // cap serves the miss far earlier
  if (ok) pass++; else fail++;
  console.log(`  [${ok ? "PASS" : "FAIL"}] miss served @cycle: ageMax=∞ → ${tNo}   ageMax=200 → ${tCap}   (cap must serve early)`);

  console.log("\n== window vs infinite visibility: DQ-busy retained at WIN=64 ==");
  for (const map of ["interleave", "rowlocal"]) {
    const q = genTrace(5000, {map, seed: 9});
    const inf = runScheduler(q, "b4800", {});
    const w64 = runScheduler(q, "b4800", {win: 64});
    console.log(`  [info] map=${map.padEnd(10)} win=∞ busy=${inf.busy}%   win=64 busy=${w64.busy}%   Δ=${inf.busy - w64.busy}pt`);
  }

  console.log("\n== queue-arch: admission + per-bank queues drain fully, DQ-busy retained ==");
  for (const map of ["interleave", "rowlocal"]) {
    const q = genTrace(4000, {map, seed: 5});
    const win = runScheduler(q, "b4800", {win: 64});
    const qa  = runScheduler(q, "b4800", {queueArch: true});
    const ok = qa.unscheduled === 0 && !qa.guardHit && validate(qa.cmds, PARAMS.b4800).length === 0;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] map=${map.padEnd(10)} win64 busy=${win.busy}%  queueArch busy=${qa.busy}%  Δ=${win.busy - qa.busy}pt  unsched=${qa.unscheduled}`);
  }

  console.log("\n== queue-arch backpressure: tiny TCAM + shallow banks still drain (0 unsched) ==");
  {
    const q = genTrace(2000, {map: "rowlocal", seed: 6});
    const qa = runScheduler(q, "b4800", {queueArch: true, tcam: 8, bankDepth: 2});
    const ok = qa.unscheduled === 0 && !qa.guardHit && validate(qa.cmds, PARAMS.b4800).length === 0;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] tcam=8 bankDepth=2  unsched=${qa.unscheduled}  guardHit=${qa.guardHit}  busy=${qa.busy}%`);
  }

  console.log("\n== queue-arch RAW: program order preserved — read never precedes its write ==");
  {
    // write then a younger read to the SAME address (same bank+row). RAW must resolve
    // write-before-read: rawPause holds the read at admission; the unified per-bank FIFO
    // also orders it. Either way the RD must land after the WR — no bypass, no reorder.
    const raw = [
      {dir: "W", rank: 0, bg: 0, bank: 0, row: 0},        // id0: the write
      {dir: "R", rank: 0, bg: 0, bank: 0, row: 0},        // id1: RAW read, must wait
    ];
    const qa = runScheduler(raw, "toy", {queueArch: true, rawPause: true});
    const wr = qa.cmds.find(c => c.type === "WR"), rd = qa.cmds.find(c => c.type === "RD");
    const ok = wr && rd && rd.cycle > wr.cycle && qa.unscheduled === 0;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] WR@${wr ? wr.cycle : "-"}  RD@${rd ? rd.cycle : "-"}  (RD must follow WR)  unsched=${qa.unscheduled}`);
  }

  console.log("\n== weight arbiter: legal + drains, both bins (queueArch) ==");
  for (const bin of ["toy", "b4800"]) {
    const q = genTrace(4000, {map: "interleave", seed: 11});
    const r = runScheduler(q, bin, {queueArch: true, arbiter: "weighted"});
    const ok = validate(r.cmds, PARAMS[bin]).length === 0 && r.unscheduled === 0 && !r.guardHit;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] bin=${bin.padEnd(6)} busy=${r.busy}%  maxWait=${r.maxWait}  meanWait=${r.meanWait}  viol=${validate(r.cmds, PARAMS[bin]).length}`);
  }

  console.log("\n== weight arbiter: low K (age-led) cuts tail-wait vs high K (SJF-led) ==");
  {
    const q = genTrace(4000, {map: "rowlocal", seed: 13, hot: 0.15, random: 0.1, linear: 0.55, strided: 0.2});
    const hiK = runScheduler(q, "b4800", {queueArch: true, arbiter: "weighted", K: 100000});
    const loK = runScheduler(q, "b4800", {queueArch: true, arbiter: "weighted", K: 50});
    const ok = loK.maxWait <= hiK.maxWait && validate(loK.cmds, PARAMS.b4800).length === 0 && loK.unscheduled === 0;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] K=100000 maxWait=${hiK.maxWait} busy=${hiK.busy}%   K=50 maxWait=${loK.maxWait} busy=${loK.busy}%`);
  }

  console.log("\n== row-hit promotion: the hit,miss,hit(same row) case ==");
  {
    // one bank, three requests: rowA, rowB(miss), rowA again. Strict FIFO strands the
    // 2nd rowA behind the rowB miss — the miss closes rowA, so the 2nd rowA reopens it
    // (extra ACT), and the row-lock even stalls the miss's PRE to AGE_MAX. Promotion
    // clusters the two rowA requests, so rowA opens once and the miss follows.
    const q = [
      {dir: "R", rank: 0, bg: 0, bank: 0, row: 0},   // rowA
      {dir: "R", rank: 0, bg: 0, bank: 0, row: 1},   // rowB — the miss
      {dir: "R", rank: 0, bg: 0, bank: 0, row: 0},   // rowA again (arrives behind the miss)
    ];
    const acts = r => r.cmds.filter(c => c.type === "ACT").length;
    const strict  = runScheduler(q, "toy", {queueArch: true, lock: true, promote: false});
    const promo   = runScheduler(q, "toy", {queueArch: true, lock: true, promote: true});
    // promotion must: emit fewer ACTs (rowA opened once) AND finish sooner (no AGE_MAX stall),
    // both legal, both fully drained.
    const legal = r => validate(r.cmds, PARAMS.toy).length === 0 && r.unscheduled === 0;
    const ok = legal(strict) && legal(promo) && acts(promo) < acts(strict) && promo.span < strict.span;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] strict FIFO : ACTs=${acts(strict)}  span=${strict.span}  maxWait=${strict.maxWait}`);
    console.log(`         promotion  : ACTs=${acts(promo)}  span=${promo.span}  maxWait=${promo.maxWait}   (fewer ACTs + shorter span)`);
  }

  console.log("\n== row-hit promotion: row-local trace keeps locality (busy up, tail down) ==");
  for (const seed of [21, 22]) {
    const q = genTrace(4000, {map: "rowlocal", readPct: 75, seed, linear: 0.7, strided: 0.15, random: 0.15});
    const strict = runScheduler(q, "b4800", {queueArch: true, lock: true, promote: false});
    const promo  = runScheduler(q, "b4800", {queueArch: true, lock: true, promote: true});
    const legal = r => validate(r.cmds, PARAMS.b4800).length === 0 && r.unscheduled === 0;
    const ok = legal(strict) && legal(promo) && promo.busy >= strict.busy;
    if (ok) pass++; else fail++;
    console.log(`  [${ok ? "PASS" : "FAIL"}] seed=${seed}  strict busy=${strict.busy}% tail=${strict.maxWait}   promo busy=${promo.busy}% tail=${promo.maxWait}`);
  }
  {
    // adversarial: one bank, hits to rowA interleaved with misses to other rows —
    // the pattern promotion is built for (strict FIFO keeps stranding the rowA hits).
    const adv = [];
    for (let i = 0; i < 900; i++) {
      adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0});         // rowA hit
      if (i % 3 === 0) adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 100 + i}); // a miss, interleaved
      adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0});         // another rowA hit behind it
    }
    const strict = runScheduler(adv, "b4800", {queueArch: true, lock: true, promote: false});
    const promo  = runScheduler(adv, "b4800", {queueArch: true, lock: true, promote: true});
    const actS = strict.cmds.filter(c => c.type === "ACT").length, actP = promo.cmds.filter(c => c.type === "ACT").length;
    const okA = validate(promo.cmds, PARAMS.b4800).length === 0 && promo.unscheduled === 0 && promo.busy >= strict.busy && actP <= actS;
    if (okA) pass++; else fail++;
    console.log(`  [${okA ? "PASS" : "FAIL"}] adversarial interleave:  strict busy=${strict.busy}% ACTs=${actS}   promo busy=${promo.busy}% ACTs=${actP}`);
  }

  console.log("\n== timing wheel vs per-bank FIFO: iterations vs DQ-busy trade (prototype finding) ==");
  // The wheel is event-driven legality: jump gc to the soonest ready-time among the bank heads
  // instead of scanning every tCK. RESULT: on a single saturated bank it matches the FIFO
  // exactly (busy + ACTs) with ~70% fewer iterations; but under DYNAMIC ADMISSION on multi-bank
  // traffic it LOSES DQ-busy — jumping past a cycle skips freshly-evicted row-hits that became
  // legal there, which the per-tCK scan would have caught. So the wheel is NOT policy-neutral;
  // it trades throughput for scan cost. Since timing_reg_file already gives O(1) per-cycle
  // legality (no scan bottleneck), the FIFO + per-cycle scan wins. Invariants asserted: both
  // legal + fully drained, ACTs equal (row-open count is structure-independent), wheel never
  // EXCEEDS FIFO busy, wheel uses fewer iterations.
  {
    const adv = [];
    for (let i = 0; i < 900; i++) { adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0}); if (i % 3 === 0) adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 100 + i}); adv.push({dir: "R", rank: 0, bg: 0, bank: 0, row: 0}); }
    const traces = [["adversarial(1bank)", adv, true], ["interleave", genTrace(4000, {map: "interleave", seed: 31}), false], ["rowlocal", genTrace(4000, {map: "rowlocal", seed: 32, linear: 0.7, strided: 0.15, random: 0.15}), false]];
    for (const [nm, q, singleBank] of traces) {
      const fifo  = runScheduler(q, "b4800", {queueArch: true, promote: true});
      const wheel = runScheduler(q, "b4800", {queueArch: true, promote: true, wheel: true});
      const legal = r => validate(r.cmds, PARAMS.b4800).length === 0 && r.unscheduled === 0;
      const actF = fifo.cmds.filter(c => c.type === "ACT").length, actW = wheel.cmds.filter(c => c.type === "ACT").length;
      // single-bank: exact match. multi-bank: wheel ≤ FIFO busy (documents the throughput cost).
      const busyOk = singleBank ? wheel.busy === fifo.busy : wheel.busy <= fifo.busy;
      const ok = legal(fifo) && legal(wheel) && actW === actF && busyOk && wheel.iters < fifo.iters;
      if (ok) pass++; else fail++;
      const save = fifo.iters ? Math.round(100 * (1 - wheel.iters / fifo.iters)) : 0;
      console.log(`  [${ok ? "PASS" : "FAIL"}] ${nm.padEnd(18)} busy F=${fifo.busy}% W=${wheel.busy}% (Δ${wheel.busy - fifo.busy})  ACTs F=${actF} W=${actW}  iters ${save}% fewer (F=${fifo.iters} W=${wheel.iters})`);
    }
  }

  console.log(`\n== summary: ${pass} pass, ${fail} fail ==\n`);
  process.exit(fail ? 1 : 0);
}

function demo() {
  const q = genTrace(40, {map: "rowlocal", seed: 1});
  const r = runScheduler(q, "toy", {win: 64, pingpong: true, lock: true});
  console.log(`demo: ${r.cmds.length} cmds, ${r.busy}% DQ-busy, ${r.flips} flips`);
  for (const c of r.cmds.slice(0, 24)) console.log(`  @${String(c.cycle).padStart(4)}  ${c.type.padEnd(4)} g${c.bg}b${c.bank} row${c.row}`);
}

module.exports = {runScheduler, genTrace, validate, PARAMS};

if (require.main === module) {                          // only when run directly, not on require()
  if (process.argv.includes("--demo")) demo();
  else selfTest();
}
