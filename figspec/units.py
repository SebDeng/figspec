"""Length parsing and conversion. Internal unit is pt (1/72 inch)."""
import re

PT_PER_UNIT = {"pt": 1.0, "mm": 72.0 / 25.4, "cm": 720.0 / 25.4, "in": 72.0}
_LENGTH_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([a-z]*)\s*$")

def parse_length(text: str, default_unit: str = "pt") -> float:
    m = _LENGTH_RE.match(text.lower())
    if not m:
        raise ValueError(f"Cannot parse length: {text!r}")
    value, unit = float(m.group(1)), (m.group(2) or default_unit)
    if unit not in PT_PER_UNIT:
        raise ValueError(f"Unknown unit {unit!r} in {text!r} (use pt/mm/cm/in)")
    return value * PT_PER_UNIT[unit]

def pt_to_mm(pt: float) -> float:
    return pt * 25.4 / 72.0

def mm_to_pt(mm: float) -> float:
    return mm * 72.0 / 25.4
