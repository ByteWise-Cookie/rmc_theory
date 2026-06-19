"""
Placement generator: enumerates valid bit-field orderings and
direct-slice vs XOR-hash variants per field, respecting fixed constraints.
"""
import itertools
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from config import MCConfig, FieldSpec


@dataclass
class FieldPlacement:
    name: str
    width: int
    low_bit: int                      # start bit position (0 = LSB)
    mode: str = "direct"               # "direct" or "xor"
    xor_src_low_bit: Optional[int] = None  # second operand bit position for XOR hash

    def mask_bits(self) -> List[int]:
        return list(range(self.low_bit, self.low_bit + self.width))


@dataclass
class Placement:
    name: str                          # human id, e.g. "ord3_xor_bg"
    offset_bits: int
    order: Tuple[str, ...]              # field order, low->high after offset
    fields: Dict[str, FieldPlacement]
    config: MCConfig

    def decode(self, addr: int) -> Dict[str, int]:
        """Decode a byte address into field values per this placement."""
        out = {}
        for name, fp in self.fields.items():
            direct_val = 0
            for i, bit in enumerate(fp.mask_bits()):
                direct_val |= ((addr >> bit) & 1) << i
            if fp.mode == "xor" and fp.xor_src_low_bit is not None:
                xor_val = 0
                for i in range(fp.width):
                    xor_val |= ((addr >> (fp.xor_src_low_bit + i)) & 1) << i
                direct_val ^= xor_val
            out[name] = direct_val
        return out


def _valid_orderings(fields: Dict[str, FieldSpec]) -> List[Tuple[str, ...]]:
    """All permutations of non-fixed fields; fixed_low fields pinned at position 0
    of the order (closest to offset), fixed_high pinned at the end."""
    names = list(fields.keys())
    low_fixed = [n for n in names if fields[n].fixed_low]
    high_fixed = [n for n in names if fields[n].fixed_high]
    free = [n for n in names if n not in low_fixed and n not in high_fixed]

    orderings = []
    for perm in itertools.permutations(free):
        orderings.append(tuple(low_fixed) + perm + tuple(high_fixed))
    return orderings


def _place_fields(order: Tuple[str, ...], fields: Dict[str, FieldSpec],
                   offset_bits: int) -> Dict[str, FieldPlacement]:
    placed = {}
    cur = offset_bits
    for name in order:
        w = fields[name].width
        placed[name] = FieldPlacement(name=name, width=w, low_bit=cur)
        cur += w
    return placed


def generate_placements(cfg: MCConfig, max_hash_variants: int = 3,
                         max_orderings: Optional[int] = None) -> List[Placement]:
    """
    Enumerate orderings x hash variants.
    Direct-slice baseline for every ordering, plus up to `max_hash_variants`
    XOR-hash variants per hashable field (XOR with a high address segment),
    capped to keep search tractable.
    """
    orderings = _valid_orderings(cfg.fields)
    if max_orderings is not None:
        orderings = orderings[:max_orderings]

    placements: List[Placement] = []

    for oi, order in enumerate(orderings):
        base_fields = _place_fields(order, cfg.fields, cfg.offset_bits)
        placements.append(Placement(
            name=f"ord{oi}_direct",
            offset_bits=cfg.offset_bits,
            order=order,
            fields={k: FieldPlacement(**vars(v)) for k, v in base_fields.items()},
            config=cfg,
        ))

        hashable = [n for n in order if cfg.fields[n].hashable]
        total_bits = cfg.offset_bits + sum(f.width for f in cfg.fields.values())

        variant_count = 0
        for hname in hashable:
            if variant_count >= max_hash_variants:
                break
            hfield = base_fields[hname]
            # XOR source: a same-width segment from the row field's high bits
            # (classic technique: fold row address into bank/bg select to
            # break up sequential-stride aliasing)
            row_fp = base_fields.get("row")
            if row_fp is None:
                continue
            src_low = row_fp.low_bit + max(0, row_fp.width - hfield.width)
            if src_low + hfield.width > total_bits:
                continue
            if src_low == hfield.low_bit:
                continue

            new_fields = {k: FieldPlacement(**vars(v)) for k, v in base_fields.items()}
            new_fields[hname] = FieldPlacement(
                name=hname, width=hfield.width, low_bit=hfield.low_bit,
                mode="xor", xor_src_low_bit=src_low,
            )
            placements.append(Placement(
                name=f"ord{oi}_xor_{hname}",
                offset_bits=cfg.offset_bits,
                order=order,
                fields=new_fields,
                config=cfg,
            ))
            variant_count += 1

    return placements
