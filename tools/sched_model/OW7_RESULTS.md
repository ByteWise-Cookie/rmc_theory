# OW-7 Buffer-Depth Sweep — Results

**Question:** read-buffer vs write-buffer depth. Plan says read=write=64; KB §25 says
`N_WR = 2–3× N_RD`. Which, and is there a read-depth floor (I24: row-miss lookahead ≥
tRCD+tRP ≈ 10 bursts)?

**Method:** `sweep_ow7.js` on the RTL-reference config (`queueArch`, weighted arbiter,
control 2/1/0, K=5000, servo OFF, AGE_MAX=256, tcam=32, bankDepth=8). DDR5-4800B, N=6000,
6 seeds × 2 maps (interleave/rowlocal). New model knobs `rdCap`/`wrCap` = max in-flight
reads/writes = the read/write buffer sizes. Absolute busy is low (synthetic traces, servo
off); the **relative** comparison is the signal. All runs 0 violations, 0 unscheduled.

## Findings

### A. Read-depth floor (wrCap=∞, 70% R)
| rdCap | 4 | 8 | 12 | 16 | 24 | 32 | 48 | 64 |
|-------|---|---|----|----|----|----|----|----|
| busy% | 22 | 30 | 35 | 37 | 40 | **41** | 41 | 39 |
| span(k)| 288 | 201 | 168 | 154 | 143 | 140 | 140 | 147 |

Busy saturates at **rdCap≈32**; **rd64 regresses** (over-buffered reads pile up → more
ACTs, more contention). Floor ≥24. **Reads want shallow buffering.**

### B. Write-depth effect (rdCap=32, 70% R)
| wrCap | 8 | 16 | 32 | 48 | 64 | 96 | 128 |
|-------|---|----|----|----|----|----|-----|
| busy% | 32 | 33 | 37 | 39 | 40 | **41** | 41 |
| readTail | 6873 | 7137 | 8579 | 9616 | 9752 | 10091 | 10355 |

Busy climbs with write depth, saturates ~**wr96**; read tail rises with it. **Writes want
deep buffering** (accumulate + background drain via adaptive batching) — the throughput
lever, at a modest read-tail cost.

### C. Candidate head-to-head (70% R)
| rd/wr | busy% | readMean | span(k) | note |
|-------|-------|----------|---------|------|
| **32/96 (KB 3×)** | **41** | **1026** | 140 | **winner** |
| 32/64 (KB 2×) | 40 | 1048 | 142 | close |
| 48/96 | 41 | 1485 | 140 | ties busy, worse read |
| **64/64 (plan)** | **39** | **1933** | 147 | **worst** — low busy, ~2× read latency |
| 64/128 | 39 | 1918 | 147 | over-buffered reads |
| 48/48 | 39 | 1534 | 143 | — |

Under write-heavy (50% R, C2): same ordering — 32/96 best (busy 37), 64/64 worst (34).

## Verdict

**KB was right; the plan was wrong.** Asymmetric **N_RD=32 / N_WR=96 (3×)** is the sweep
optimum. Symmetric **64/64 is the worst tested point** — lowest throughput *and* highest
read latency. Mechanism: reads are latency-critical (deep read buffer only raises their
queueing latency past the ~24–32 floor); writes are latency-tolerant (deep write buffer
accumulates and drains in background, keeping DQ busy). Exactly KB §25's rationale.

**Design intent (pkg, deferred to RTL-go):** `N_RD_ENTRIES = 32`, `N_WR_ENTRIES = 96`.
The I24 lookahead floor (~10 bursts) is met by tcam(32)+bankDepth(8×16); rdCap only needs
≥24 to feed it — 32 clears it.
