"""Font metadata: advance widths and ToUnicode decoding (best effort)."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

import pikepdf
pikepdf_Array_types = (pikepdf.Array, list)

@dataclass
class FontInfo:
    name: str = "unknown"
    code_size: int = 1
    widths: dict[int, float] = field(default_factory=dict)
    default_width: float = 0.5
    to_unicode: dict[int, str] | None = None
    latin_fallback: bool = True

_HEX = re.compile(rb"<([0-9A-Fa-f]+)>")

def _parse_tounicode(data: bytes) -> dict[int, str]:
    out: dict[int, str] = {}

    def _dst_to_str(hexs: bytes) -> str:
        raw = bytes.fromhex(hexs.decode("ascii"))
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for m in re.finditer(rb"beginbfchar(.*?)endbfchar", data, re.S):
        toks = _HEX.findall(m.group(1))
        for src, dst in zip(toks[0::2], toks[1::2]):
            out[int(src, 16)] = _dst_to_str(dst)
    for m in re.finditer(rb"beginbfrange(.*?)endbfrange", data, re.S):
        body = m.group(1)
        # form: <lo> <hi> [<d1> <d2> ...]
        for lo, hi, arr in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", body, re.S):
            dsts = _HEX.findall(arr)
            for i, dst in enumerate(dsts):
                out[int(lo, 16) + i] = _dst_to_str(dst)
        body = re.sub(rb"<[0-9A-Fa-f]+>\s*<[0-9A-Fa-f]+>\s*\[.*?\]", b"", body, flags=re.S)
        # form: <lo> <hi> <dst>
        toks = _HEX.findall(body)
        for lo, hi, dst in zip(toks[0::3], toks[1::3], toks[2::3]):
            base = int(dst, 16)
            for i in range(int(hi, 16) - int(lo, 16) + 1):
                out[int(lo, 16) + i] = chr(base + i)
    return out

def load_font(fontdict) -> FontInfo:
    fi = FontInfo()
    subtype = str(fontdict.get("/Subtype", ""))
    fi.name = str(fontdict.get("/BaseFont", "/unknown")).lstrip("/")
    tu = fontdict.get("/ToUnicode")
    if tu is not None:
        try:
            fi.to_unicode = _parse_tounicode(tu.read_bytes())
        except Exception:
            fi.to_unicode = None

    if subtype == "/Type0":
        fi.code_size = 2
        fi.latin_fallback = False
        fi.default_width = 1.0
        try:
            desc = fontdict.DescendantFonts[0]
            fi.default_width = float(desc.get("/DW", 1000)) / 1000.0
            w = desc.get("/W")
            if w is not None:
                items = list(w)
                i = 0
                while i < len(items):
                    first = int(items[i])
                    if i + 1 < len(items) and isinstance(items[i + 1], pikepdf_Array_types):
                        for j, width in enumerate(items[i + 1]):
                            fi.widths[first + j] = float(width) / 1000.0
                        i += 2
                    else:
                        last, width = int(items[i + 1]), float(items[i + 2]) / 1000.0
                        for code in range(first, last + 1):
                            fi.widths[code] = width
                        i += 3
        except Exception:
            pass
        return fi

    # Simple fonts: Type1 / TrueType / Type3
    scale = 0.001
    if subtype == "/Type3":
        try:
            scale = abs(float(fontdict.FontMatrix[0]))
        except Exception:
            scale = 0.001
    try:
        first = int(fontdict.FirstChar)
        for i, w in enumerate(fontdict.Widths):
            fi.widths[first + i] = float(w) * scale
    except Exception:
        pass
    return fi

def decode_codes(fi: FontInfo, data: bytes) -> list[tuple[int, str]]:
    codes: list[int] = []
    if fi.code_size == 2:
        for i in range(0, len(data) - 1, 2):
            codes.append((data[i] << 8) | data[i + 1])
    else:
        codes = list(data)
    out = []
    for c in codes:
        if fi.to_unicode and c in fi.to_unicode:
            out.append((c, fi.to_unicode[c]))
        elif fi.latin_fallback and fi.code_size == 1:
            out.append((c, bytes([c]).decode("latin-1")))
        else:
            out.append((c, ""))
    return out
