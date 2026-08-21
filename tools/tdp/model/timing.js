// tdp — timing table: command widths, representative timing floors, and derivation.
//
// SOURCE / DISCLAIMER: the numbers below are *representative* DDR5 values consistent with
// JEDEC JESD79-5 ns/nCK floors and common speed-bin conventions. They are NOT a substitute
// for a signed-off datasheet, and every one is editable in the UI. Where a value has a
// well-known basis it is cited inline. Nothing here is authoritative; treat as defaults.
//
// All scheduler-internal time is counted in CK (DRAM clock). ns is a derived view via tCK.

// ---- command widths on the CA bus, in CK -----------------------------------------------
// DDR5 2-cycle commands (ACT/RD/WR/MRW) occupy 2 CK; 1-cycle commands occupy 1 CK.
// This is a table, not literals scattered in code — override per-config if ever needed.
export const CMD_WIDTH_CK = {
  ACT:   2,
  RD:    2,
  WR:    2,
  RDA:   2,   // read + auto-precharge
  WRA:   2,   // write + auto-precharge
  PRE:   1,
  PREab: 1,   // all-bank precharge
  REFab: 1,   // all-bank refresh
  REFsb: 1,   // same-bank refresh (DDR5)
  MRW:   2,
  ZQCS:  1,
  NOP:   1,
};

// commands that put READ data on the bus / WRITE data on the bus (for turnaround + data lane)
export const IS_READ  = t => t === "RD" || t === "RDA";
export const IS_WRITE = t => t === "WR" || t === "WRA";
export const IS_CAS   = t => IS_READ(t) || IS_WRITE(t);
export const IS_ACT   = t => t === "ACT";
export const IS_PRE   = t => t === "PRE" || t === "PREab";
export const IS_REF   = t => t === "REFab" || t === "REFsb";

// ---- representative timing floors -------------------------------------------------------
// Each param derives as CK = max(ckFloor, ceil(nsFloor / tCK)). A param may have either or
// both floors. `derived` params are computed from other params (documented in deriveTimings).
// Floors chosen to reproduce the verified DDR5-4800B set (40-40-40) used elsewhere in this
// repo; other bins scale by tCK. Representative — editable.
export const TIMING_FLOORS = {
  //                 ckFloor   nsFloor   note
  tRCD:    { ns: 16.67 },              // ACT -> CAS
  tRP:     { ns: 16.67 },              // PRE -> ACT
  tRAS:    { ns: 32.0  },              // ACT -> PRE (min row open)
  // tRC derived = tRAS + tRP
  tRTP:    { ck: 12, ns: 7.5 },        // RD -> PRE
  tWR:     { ns: 30.0 },               // write-data-end -> PRE
  tRRD_S:  { ck: 8 },                  // ACT->ACT diff BG (BL16)
  tRRD_L:  { ck: 8, ns: 5.0 },         // ACT->ACT same BG
  tFAW:    { ck: 32 },                 // 4-activate window (page-size dependent; representative)
  tCCD_S:  { ck: 8 },                  // CAS->CAS diff BG (= BL/2 for BL16)
  tCCD_L:  { ck: 8, ns: 5.0 },         // CAS->CAS same BG (read)
  tCCD_S_WR:{ ck: 8 },                 // WR->WR diff BG
  tCCD_L_WR:{ ck: 32, ns: 20.0 },      // WR->WR same BG
  tWTR_S:  { ck: 4, ns: 2.5 },         // WR->RD diff BG (from write-data-end)
  tWTR_L:  { ck: 16, ns: 10.0 },       // WR->RD same BG
  // tRTW derived = tCL + BL/2 - tCWL + 2 (representative rounding)
  tRTRS:   { ck: 2 },                  // rank-to-rank CAS turnaround (PHY/ODT — representative)
  tPPD:    { ck: 2 },                  // PRE->PRE
  tPREab:  { ck: 1 },                  // PREab command effect (representative)
  tREFI:   { ns: 3900.0 },             // average refresh interval (32ms / 8192)
  tRFC1:   { ns: 295.0 },              // 16Gb all-bank refresh (representative)
  tRFC2:   { ns: 160.0 },              // FGR 2x
  tRFCsb:  { ns: 130.0 },              // same-bank refresh
  tREFSBRD:{ ck: 8 },                  // REFsb->valid access to other banks (representative)
  tZQCS:   { ck: 128 },                // ZQ short (representative)
  tZQoper: { ns: 1000.0 },             // ZQ operation (representative)
  tMRD:    { ck: 16 },                 // MRW -> MRW / valid
  tMOD:    { ck: 24, ns: 15.0 },       // MRW -> non-MRW
};

// per-bin CL / CWL (representative bin labels; CWL = CL - 2 per common DDR5 convention).
export const BIN_CAS = {
  4800: { tCL: 40, tCWL: 38 },
  5600: { tCL: 46, tCWL: 44 },
  6400: { tCL: 52, tCWL: 50 },
  8000: { tCL: 64, tCWL: 62 },
};

export const nsToCk = (ns, tCK) => Math.ceil(ns / tCK - 1e-9);
export const ckToNs = (ck, tCK) => +(ck * tCK).toFixed(4);

// Derive the full CK timing table for a given tCK (ns) + BL + CAS pair.
// Returns a flat {param: ck} object. Every value is an integer CK.
export function deriveTimings(tCK, { tCL, tCWL }, BL = 16) {
  const t = {};
  for (const [k, f] of Object.entries(TIMING_FLOORS)) {
    const byNs = f.ns != null ? nsToCk(f.ns, tCK) : 0;
    const byCk = f.ck != null ? f.ck : 0;
    t[k] = Math.max(byNs, byCk);
  }
  t.tCL = tCL;
  t.tCWL = tCWL;
  t.tRC = t.tRAS + t.tRP;                       // derived
  t.tRTW = t.tCL + BL / 2 - t.tCWL + 2;         // derived (representative)
  return t;
}

// grouping for the UI param editor (§2.3)
export const PARAM_GROUPS = {
  Speed:      ["DATA_RATE_MTS", "tCK", "RATIO"],
  Core:       ["tRCD", "tRP", "tRAS", "tRC", "tRTP", "tWR"],
  Activate:   ["tRRD_S", "tRRD_L", "tFAW"],
  CAS:        ["tCCD_S", "tCCD_L", "tCCD_S_WR", "tCCD_L_WR", "tCL", "tCWL"],
  Turnaround: ["tWTR_S", "tWTR_L", "tRTW", "tRTRS"],
  Precharge:  ["tPPD", "tPREab"],
  Refresh:    ["tREFI", "tRFC1", "tRFC2", "tRFCsb", "tREFSBRD", "REF_MODE"],
  Misc:       ["tZQCS", "tZQoper", "tMRD", "tMOD"],
};
