"""
Pluggable traffic generators. Each yields a list/array of byte addresses.
"""
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
import os
import csv


@dataclass
class TrafficSpec:
    name: str
    kind: str             # "linear" | "strided" | "random" | "locality" | "trace"
    n: int = 100_000
    addr_width: int = 32
    stride: int = 64       # bytes, for strided
    working_set_bytes: int = 1 << 20   # for locality
    locality_p: float = 0.9            # prob of staying in working set
    seed: int = 0
    trace_path: Optional[str] = None


def gen_linear(spec: TrafficSpec) -> np.ndarray:
    base = np.random.default_rng(spec.seed).integers(0, 1 << 12)
    return (base + np.arange(spec.n) * spec.stride if False else
            base + np.arange(spec.n) * 64).astype(np.int64) & ((1 << spec.addr_width) - 1)


def gen_strided(spec: TrafficSpec) -> np.ndarray:
    rng = np.random.default_rng(spec.seed)
    base = rng.integers(0, 1 << 12)
    addrs = base + np.arange(spec.n) * spec.stride
    return addrs.astype(np.int64) & ((1 << spec.addr_width) - 1)


def gen_random_uniform(spec: TrafficSpec) -> np.ndarray:
    rng = np.random.default_rng(spec.seed)
    max_addr = 1 << spec.addr_width
    addrs = rng.integers(0, max_addr, size=spec.n, dtype=np.int64)
    return addrs & (max_addr - 1)


def gen_random_locality(spec: TrafficSpec) -> np.ndarray:
    """Working-set model: with prob p stay within a hot window, else jump."""
    rng = np.random.default_rng(spec.seed)
    max_addr = 1 << spec.addr_width
    ws_bytes = min(spec.working_set_bytes, max_addr)
    addrs = np.empty(spec.n, dtype=np.int64)
    cur_base = rng.integers(0, max_addr - ws_bytes) if max_addr > ws_bytes else 0
    for i in range(spec.n):
        if rng.random() < spec.locality_p:
            off = rng.integers(0, ws_bytes)
            addrs[i] = (cur_base + off) & (max_addr - 1)
        else:
            cur_base = rng.integers(0, max(1, max_addr - ws_bytes))
            addrs[i] = cur_base
    return addrs


def gen_trace(spec: TrafficSpec) -> np.ndarray:
    """Load a real memory trace if a usable file is provided/found.
    Expected: one address (hex or dec) per line, or CSV with an 'addr' column.
    Falls back to random_uniform if nothing usable is found."""
    candidates = []
    if spec.trace_path:
        candidates.append(spec.trace_path)
    candidates += [
        "/home/claude/addrmap/traces/sample.trace",
        "/home/claude/addrmap/traces/sample.csv",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            addrs = []
            try:
                if path.endswith(".csv"):
                    with open(path, newline="") as f:
                        reader = csv.DictReader(f)
                        col = "addr" if "addr" in reader.fieldnames else reader.fieldnames[0]
                        for row in reader:
                            addrs.append(int(row[col], 0))
                else:
                    with open(path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            addrs.append(int(line, 0))
                if addrs:
                    arr = np.array(addrs[: spec.n], dtype=np.int64)
                    return arr & ((1 << spec.addr_width) - 1)
            except Exception:
                pass
    # fallback: no public trace bundled/found -> synth locality model
    fallback = TrafficSpec(**{**vars(spec), "kind": "locality"})
    return gen_random_locality(fallback)


GENERATORS = {
    "linear": gen_linear,
    "strided": gen_strided,
    "random": gen_random_uniform,
    "locality": gen_random_locality,
    "trace": gen_trace,
}


def generate(spec: TrafficSpec) -> np.ndarray:
    fn = GENERATORS.get(spec.kind)
    if fn is None:
        raise ValueError(f"unknown traffic kind: {spec.kind}")
    return fn(spec)
