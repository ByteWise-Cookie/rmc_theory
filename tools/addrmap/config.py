"""
addr-map hash optimizer — config layer
fields, widths, constraints. fully user-settable.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import itertools


FIELD_NAMES = ["ch", "subch", "rank", "bg", "bank", "row", "col"]


@dataclass
class FieldSpec:
    name: str
    width: int                 # bits
    fixed_low: bool = False    # must stay at low bits (e.g. col/offset)
    fixed_high: bool = False   # must stay at high bits
    hashable: bool = True      # allow XOR-hash variant search


@dataclass
class MCConfig:
    addr_width: int
    fields: Dict[str, FieldSpec]
    beat_bytes: int = 8                 # bus width bytes per beat
    burst_len: int = 16                 # BL
    density_bits: Optional[int] = None  # optional capacity check (log2 bytes)

    def __post_init__(self):
        total = sum(f.width for f in self.fields.values())
        # offset bits = addr_width - total (low bits consumed by beat/burst)
        self.offset_bits = self.addr_width - total
        if self.offset_bits < 0:
            raise ValueError(
                f"fields exceed addr_width: {total} bits needed > {self.addr_width} available"
            )
        if self.density_bits is not None:
            cap = sum(f.width for f in self.fields.values()) + self.offset_bits
            if cap > self.density_bits:
                raise ValueError(
                    f"address space ({cap}b) exceeds device density ({self.density_bits}b)"
                )

    @property
    def field_names(self) -> List[str]:
        return list(self.fields.keys())

    def total_units(self, name: str) -> int:
        return 1 << self.fields[name].width


def make_config(
    addr_width: int,
    ch: int = 0, subch: int = 0, rank: int = 0,
    bg: int = 0, bank: int = 0, row: int = 0, col: int = 0,
    beat_bytes: int = 8, burst_len: int = 16,
    density_bits: Optional[int] = None,
) -> MCConfig:
    """Convenience builder. Widths in bits; 0 = field not present."""
    widths = dict(ch=ch, subch=subch, rank=rank, bg=bg, bank=bank, row=row, col=col)
    fields = {}
    for name, w in widths.items():
        if w <= 0:
            continue
        fixed_low = name == "col"
        fields[name] = FieldSpec(name=name, width=w, fixed_low=fixed_low,
                                  hashable=(name not in ("col",)))
    return MCConfig(addr_width=addr_width, fields=fields,
                     beat_bytes=beat_bytes, burst_len=burst_len,
                     density_bits=density_bits)
