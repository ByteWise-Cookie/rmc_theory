# Scheduler Microarchitecture — where tokens live, what the pipeline carries

**Status:** architecture decision doc. Pins the hardware shape of the dynamic greedy
scheduler from [[scheduler_dynamic_design]] before any RTL. Answers the open
question: *are the pipeline stages buffers holding whole tokens, or does a request
live in the existing watermark/status/TCAM tables?*

---

## 0. The question

> Is stage N going to be buffers holding the entire token + metadata? Or should a new
> request be added into the watermark logic so it works with the already-existing
> validate + status registers?

## Decision: **the request lives in the table; the pipeline carries an index, not the token.**

A request is allocated a **slot** in the existing outstanding-request tables
(watermark alloc → status reg + TCAM entry) on arrival, lives there until it retires,
and is selected **in place**. The scheduler stages are **not** token buffers — they
are combinational *read → select → emit* logic that passes a small **entry index**
(+ decoded command fields) down registered pipeline stages. The token never marches.

### Why not marching token buffers

1. **Out-of-order needs full visibility.** The arbiter must see *all* ready requests
   every cycle to keep DQ busy (pick the one that fills the next data slot). A
   conveyor hides requests inside stage registers — you can only see the few in the
   pipe, so you can't pick the globally-best command. Datapath-busy dies.
2. **A stalled token blocks the pipe.** If stage-2 holds a token waiting for its ACT
   to become legal, everything behind it stalls → bus bubbles. The whole point
   (§3.4 of the design doc) is that a not-ready request must **step aside**, which a
   flat table gives for free (just don't nominate it) and a conveyor does not.
3. **Area.** N deep stages × full-token width (addr + age + state + data ptr) is far
   more flops than one table + a few index-wide pipe registers.

The token is therefore **virtual**: it *is* `status_reg[idx] + tcam[idx] + a small
work-state field`. Everything operates on `idx`.

---

## 1. Mapping to blocks (reuse first)

| Concern (design doc) | HW structure | Existing skeleton block | Action |
|---|---|---|---|
| token alloc / free / backpressure | watermark allocator | `wr_watermark_mgr`, `rd_watermark_mgr` | **reuse** |
| token metadata: valid, status, **age** | status reg file | `wr_status_reg`, `rd_status_reg` | reuse **+ add work-state field** |
| token address, **row-hit classify** | address CAM search | `wr_tcam`, `rd_tcam` | **reuse** (search = classify) |
| remaining work (PRE?/ACT?/CAS) | 2-bit state per entry | — | **add** to status reg |
| resource deadlines (scoreboard) | per-bank/BG/rank counters | replaces heavy `per_bank_fsm_table` | **new (thin)** |
| S1/S2/S3 pickers | combinational priority select | `scheduler.sv` stages | **rework** |
| S4 CA-mux + DFI emit | registered command + mux | `scheduler.sv` S4 + `dfi` | **rework** |
| refresh/ZQ authority (S0) | tREFI counters + override | `maintenance_engine` + `gc_counter` | reuse + wire override |

**Net:** we *reuse* the watermark + status + TCAM as the token store (your
instinct), *add* one thin scoreboard, and *rework* the selection stages. We do **not**
add a separate token FIFO or per-stage token buffers.

### Answering the watermark half directly

Yes — a new request enters through the **watermark allocator**, which hands it a
status/TCAM slot and a per-slot **age counter** (the starvation source). The moment
it's allocated it is visible to the pickers. `validate`/`status` you already have
become the token's live state; the scheduler's new scoreboard + pickers read those
slots. No new intake path.

---

## 2. What actually flows between pipeline stages

Only this, registered stage-to-stage (tens of bits, not the token):

```
pipe_reg = { valid, entry_idx[log2(N)], cmd_type[3], rank, bg, bank, row[ROW_BITS] }
```

`row`/addr can even be re-read from `status[idx]`/TCAM instead of carried — carry the
**index**, decode at emit. The token body stays in the table the whole time.

---

## 3. The pipeline is read-select-emit (not a conveyor)

Each stage combinationally scans the **shared table + scoreboard** and nominates one
candidate **index** per class; a not-ready entry is simply not nominated (steps
aside, stays in table — no stall):

```
S0  Refresh/maint mgr : owns per-rank tREFI down-counter + postpone credit;
                        asserts OVERRIDE when refresh/ZQ urgent (correctness first).
S1  Classify + PRE pick: TCAM search tags each entry row-hit/miss/idle (sets work-
                        state); nominate best PRE index (close-policy / miss path).
S2  ACT pick          : scoreboard legality (tRCD chain, tRRD, tFAW); nominate best
                        ACT index (age-boosted lookahead for demanded idle banks).
S3  CAS pick          : nominate best CAS index — busy-first, BG-rotate, batch-mode
                        gated (read window vs write window).
S4  CA mux + emit      : priority pick { REF(S0 override) > CAS busy-fill > ACT/PRE
                        lookahead > REF due }; drive DFI; COMMIT scoreboard update;
                        pop work-state; free slot (watermark) on CAS-complete.
```

The three pickers run **in parallel** (not a token walking S1→S2→S3); S4 is the
single arbiter that respects the 1-command-per-2-tCK DDR5 CA bus. This is the
non-blocking reframe of your S1=PRE/S2=ACT/S3=CAS.

---

## 4. The scoreboard (the one genuinely new structure)

Thin registers — replaces the 16-state per-bank FSM + per-rank FSM tables:

```
bank[N_BANKS] : { open[1], row[ROW_BITS], next_act, next_pre, next_cas }   // GC_WIDTH each
bg[N_BG]      : { next_cas_bg, next_act_bg }
rank[N_RANKS] : { next_act_any, faw_ring[4], next_rd, next_wr, next_ref }
global        : { next_cas_any, dq_free, last_dir, ca_free }
```

Update rules on emit are exactly the JS engine's `emit()` (tRCD/tRAS/tRP/tCCD/tWTR…).
`next_pre` must take **max** over its writers (ACT's tRAS vs CAS's tRTP/tWR) — this
was a real bug caught in the JS model; the RTL must do the same.

---

## 5. Bare-metal behavioral SV vs deliberate microarch

"Just code the algo in SV and let synthesis figure it out" **does not work here**:
- TCAM search, N-way arbitration, a per-bank scoreboard, and a refresh override are
  structural choices synthesis will not infer well — you'd get a giant combinational
  cloud (timing failure) or a naive FSM (poor throughput).
- You must specify: which arrays are **CAM vs SRAM vs flops**, the **pipeline depth**,
  how many candidates each picker evaluates per cycle (arbiter width), and the CA-bus
  serialization.

So: the **JS scheduler is the golden reference model**. The RTL is a deliberate
structural implementation whose emitted command stream must match the model
cycle-for-cycle on the same trace (the bench is the checker). That's the shortcut
"take a shot at the hardware first" — decide the structures here, validate against
the model, then write matching RTL.

---

## 6. Retirement & data path (closing the loop)

- **CAS-complete → retire:** on RD, data returns RL later → capture into ROB slot →
  free the rd status/TCAM slot (watermark). On WR, data drains from WDB → free wr slot.
- The **work-state** field per entry is the shrinking work-list: `NEED_PRE →
  NEED_ACT → NEED_CAS → DONE`, advanced by S4 on each emit for that index. Row-hit
  classify jumps straight to `NEED_CAS`.

---

## 7. Open microarch decisions

- Picker width: evaluate all N entries combinationally, or a windowed subset? (timing
  vs optimality). Start all-N for small N; revisit.
- Scoreboard `next_*` compare width vs GC wrap (use the handoff's `(gc-next)[MSB]`
  trick).
- Refresh: all-bank REF (drain+PREA+REF) vs per-bank REFsb (less disruptive) —
  policy in S0. Modeled next in the JS engine.
- Where age/starvation forces a batch-mode flip (fairness vs turnaround).

pkg untouched. RTL not started — this pins the shape so the eventual `scheduler.sv`
is a deliberate structure, checked against the JS golden model.
