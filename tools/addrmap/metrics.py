"""
Metrics computed per (placement, traffic) pair.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List
from collections import deque
from placement import Placement


@dataclass
class Metrics:
    row_hit_rate: float
    row_miss_rate: float
    bank_conflict_rate: float
    ch_balance_std: float
    subch_balance_std: float
    rank_balance_std: float
    bg_balance_std: float
    bank_balance_std: float
    avg_parallelism: float          # avg distinct (ch,subch,rank,bg,bank) touched per window
    window: int = 32


def _balance_std(counts: Dict[int, int], n_units: int) -> float:
    if n_units <= 1:
        return 0.0
    arr = np.zeros(n_units, dtype=np.float64)
    for k, v in counts.items():
        arr[k % n_units] += v
    if arr.sum() == 0:
        return 0.0
    mean = arr.mean()
    if mean == 0:
        return 0.0
    return float(arr.std() / mean)   # coefficient of variation; 0 = perfectly balanced


def evaluate(placement: Placement, addrs: np.ndarray, window: int = 32) -> Metrics:
    cfg = placement.config

    # decode all addresses vectorized via per-bit extraction (fast enough for sim sizes)
    n = len(addrs)
    decoded = {name: np.zeros(n, dtype=np.int64) for name in placement.fields}

    for name, fp in placement.fields.items():
        direct = np.zeros(n, dtype=np.int64)
        for i, bit in enumerate(fp.mask_bits()):
            direct |= ((addrs >> bit) & 1) << i
        if fp.mode == "xor" and fp.xor_src_low_bit is not None:
            xorv = np.zeros(n, dtype=np.int64)
            for i in range(fp.width):
                xorv |= ((addrs >> (fp.xor_src_low_bit + i)) & 1) << i
            direct ^= xorv
        decoded[name] = direct

    has_bg = "bg" in decoded
    has_bank = "bank" in decoded
    has_row = "row" in decoded
    has_ch = "ch" in decoded
    has_subch = "subch" in decoded
    has_rank = "rank" in decoded

    n_bank_groups = cfg.total_units("bg") if has_bg else 1
    n_banks = cfg.total_units("bank") if has_bank else 1
    n_total_banks = n_bank_groups * n_banks

    bank_key = np.zeros(n, dtype=np.int64)
    if has_bg:
        bank_key = decoded["bg"] * n_banks
    if has_bank:
        bank_key = bank_key + decoded["bank"]

    rows = decoded["row"] if has_row else np.zeros(n, dtype=np.int64)

    open_row = {}     # bank_key -> last row open
    row_hits = 0
    row_misses = 0
    bank_conflicts = 0   # different row request to a bank that's "still busy" heuristically
    last_access_bank = -1

    for i in range(n):
        bk = int(bank_key[i])
        r = int(rows[i])
        if bk in open_row:
            if open_row[bk] == r:
                row_hits += 1
            else:
                row_misses += 1
                if bk == last_access_bank:
                    bank_conflicts += 1
            open_row[bk] = r
        else:
            row_misses += 1
            open_row[bk] = r
        last_access_bank = bk

    total = row_hits + row_misses
    row_hit_rate = row_hits / total if total else 0.0
    row_miss_rate = row_misses / total if total else 0.0
    bank_conflict_rate = bank_conflicts / total if total else 0.0

    def counts_of(arr):
        u, c = np.unique(arr, return_counts=True)
        return dict(zip(u.tolist(), c.tolist()))

    ch_std = _balance_std(counts_of(decoded["ch"]), cfg.total_units("ch")) if has_ch else 0.0
    subch_std = _balance_std(counts_of(decoded["subch"]), cfg.total_units("subch")) if has_subch else 0.0
    rank_std = _balance_std(counts_of(decoded["rank"]), cfg.total_units("rank")) if has_rank else 0.0
    bg_std = _balance_std(counts_of(decoded["bg"]), cfg.total_units("bg")) if has_bg else 0.0
    bank_std = _balance_std(counts_of(bank_key), n_total_banks) if (has_bg or has_bank) else 0.0

    # parallelism: distinct bank_key values touched within sliding window
    par_sum = 0
    dq = deque(maxlen=window)
    seen_counts = {}
    distinct = 0
    for i in range(n):
        bk = int(bank_key[i])
        if len(dq) == window:
            old = dq[0]
            seen_counts[old] -= 1
            if seen_counts[old] == 0:
                distinct -= 1
                del seen_counts[old]
        dq.append(bk)
        if bk not in seen_counts:
            seen_counts[bk] = 0
            distinct += 1
        seen_counts[bk] += 1
        par_sum += distinct
    avg_parallelism = par_sum / n if n else 0.0

    return Metrics(
        row_hit_rate=row_hit_rate,
        row_miss_rate=row_miss_rate,
        bank_conflict_rate=bank_conflict_rate,
        ch_balance_std=ch_std,
        subch_balance_std=subch_std,
        rank_balance_std=rank_std,
        bg_balance_std=bg_std,
        bank_balance_std=bank_std,
        avg_parallelism=avg_parallelism,
        window=window,
    )
