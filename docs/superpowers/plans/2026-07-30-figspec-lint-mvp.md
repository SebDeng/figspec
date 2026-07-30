# figspec lint MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `figspec lint` — a CLI that opens a finished figure PDF, computes *effective* (post-scaling) font sizes and line widths from the PDF transform stack, and reports violations as text, JSON, and an annotated PNG.

**Architecture:** Three isolated layers: `figspec/pdf/` extracts geometric facts (a graphics-state machine walking `pikepdf.parse_content_stream`, recursing into Form XObjects — the Illustrator-placed-panel case); `figspec/lint/` judges those facts against thresholds and formats findings; `figspec/cli.py` wires argv to the pipeline. Hand-built PDFs (via pikepdf, no matplotlib) serve both `--self-test` and unit tests; matplotlib+pypdf synthetic assemblies serve integration tests.

**Tech Stack:** Python ≥3.10; runtime deps: pikepdf, pypdfium2, Pillow. Dev deps: pytest, pypdf, matplotlib.

## Global Constraints

- Package name `figspec`, command `figspec lint` (argparse subcommands). Entry point: `figspec = "figspec.cli:main"`.
- License Apache-2.0. All code, CLI text, comments in English.
- Runtime dependencies EXACTLY: `pikepdf`, `pypdfium2`, `Pillow`. matplotlib/pypdf are dev-only.
- Defaults: `--min-font 5.0` (pt), `--min-linewidth 0.25` (pt), width tolerance ±2 mm, raster floor 300 dpi (no flag).
- Exit codes: 0 = ready, 1 = not ready, 2 = input/usage error. `--strict` promotes WARN to not-ready.
- The CLI NEVER prompts interactively.
- Finding schema keys: `check_id`, `level` (PASS/WARN/FAIL), `message`, `evidence` (list of str) + extensions `page`, `bbox_mm`, `nominal_pt`, `scale`, `effective_pt`.
- Internal unit is pt (1 pt = 1/72 in; 1 mm = 72/25.4 pt). PDF y-axis points up; bbox tuples are `(x0, y0, x1, y1)` in pt, PDF coordinates.
- All test/venv commands run from repo root `/Users/dengyusong/Desktop/FigSpec` using `.venv/bin/...` explicitly (shell state does not persist).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `.gitignore`, `figspec/__init__.py`, `figspec/cli.py` (stub), `tests/test_cli.py`

**Interfaces:**
- Produces: installed editable package; `figspec.__version__ = "0.1.0.dev0"`; `figspec.cli.main(argv: list[str] | None) -> int`.

- [ ] **Step 1: Write files**

`pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "figspec"
version = "0.1.0.dev0"
description = "Lint finished figure PDFs for effective (post-scaling) font sizes and line widths"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
authors = [{ name = "SebDeng" }]
keywords = ["matplotlib", "figure", "lint", "pdf", "publication"]
dependencies = ["pikepdf>=9", "pypdfium2>=4", "Pillow>=10"]

[project.optional-dependencies]
dev = ["pytest>=8", "pypdf>=4", "matplotlib>=3.8"]

[project.scripts]
figspec = "figspec.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["figspec"]
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
dist/
tests/data/
*.lint.png
*.lint.json
```

`figspec/__init__.py`:
```python
__version__ = "0.1.0.dev0"
```

`figspec/cli.py` (stub, replaced in Task 12):
```python
import argparse
from figspec import __version__

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="figspec")
    parser.add_argument("--version", action="version", version=f"figspec {__version__}")
    parser.parse_args(argv)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`tests/test_cli.py`:
```python
import subprocess, sys

def test_version_runs():
    out = subprocess.run([sys.executable, "-m", "figspec.cli", "--version"],
                         capture_output=True, text=True)
    assert out.returncode == 0
    assert "figspec" in out.stdout
```

LICENSE: `curl -sL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE` (verify first line contains "Apache License").

- [ ] **Step 2: Create venv, install, run test**

Run: `python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]" && .venv/bin/pytest tests/ -q`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml LICENSE .gitignore figspec/ tests/
git commit -m "chore: scaffold figspec package"
```

---

### Task 2: Unit parsing (`figspec/units.py`)

**Files:**
- Create: `figspec/units.py`, `tests/test_units.py`

**Interfaces:**
- Produces: `parse_length(text: str, default_unit: str = "pt") -> float` (returns pt; raises `ValueError` on garbage); `pt_to_mm(pt: float) -> float`; `mm_to_pt(mm: float) -> float`.

- [ ] **Step 1: Write the failing test** (`tests/test_units.py`)

```python
import pytest
from figspec.units import parse_length, pt_to_mm, mm_to_pt

def test_parse_units():
    assert parse_length("6pt") == 6.0
    assert parse_length("183mm") == pytest.approx(518.74, abs=0.01)
    assert parse_length("1in") == 72.0
    assert parse_length("1.5 cm") == pytest.approx(42.52, abs=0.01)

def test_default_unit():
    assert parse_length("183", default_unit="mm") == pytest.approx(518.74, abs=0.01)
    assert parse_length("6", default_unit="pt") == 6.0

def test_roundtrip_and_errors():
    assert pt_to_mm(mm_to_pt(89.0)) == pytest.approx(89.0)
    with pytest.raises(ValueError):
        parse_length("abc")
    with pytest.raises(ValueError):
        parse_length("10 furlongs")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_units.py -q` — Expected: ImportError/ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/units.py`)

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_units.py -q` — Expected: 3 passed.

- [ ] **Step 5: Commit** — `git add figspec/units.py tests/test_units.py && git commit -m "feat: length unit parsing"`

---

### Task 3: Matrix math (`figspec/pdf/geometry.py`)

**Files:**
- Create: `figspec/pdf/__init__.py` (empty), `figspec/pdf/geometry.py`, `tests/test_geometry.py`

**Interfaces:**
- Produces: `Mat(a, b, c, d, e, f)` frozen dataclass, PDF row-vector convention. `m1 @ m2` = apply m1 first then m2. `.apply(x, y) -> (x', y')`, `.vertical_scale() -> float` (length of image of unit vector (0,1)), `.singular_values() -> (s_max, s_min)`, classmethod `Mat.from_seq(seq)` accepting any 6-element numeric sequence (incl. pikepdf Array values via `float()`).

- [ ] **Step 1: Write the failing test** (`tests/test_geometry.py`)

```python
import math
import pytest
from figspec.pdf.geometry import Mat

def test_identity_and_apply():
    assert Mat().apply(3, 4) == (3, 4)
    assert Mat(2, 0, 0, 2, 10, 0).apply(1, 1) == (12, 2)

def test_compose_scale_then_translate():
    m = Mat(0.5, 0, 0, 0.5, 0, 0) @ Mat(1, 0, 0, 1, 100, 50)
    assert m.apply(10, 10) == (105.0, 55.0)

def test_vertical_scale():
    assert Mat(0.4, 0, 0, 0.4, 0, 0).vertical_scale() == pytest.approx(0.4)
    rot90 = Mat(0, 1, -1, 0, 0, 0)  # 90-degree rotation
    assert rot90.vertical_scale() == pytest.approx(1.0)
    aniso = Mat(2.0, 0, 0, 0.3, 0, 0)
    assert aniso.vertical_scale() == pytest.approx(0.3)

def test_singular_values():
    s_max, s_min = Mat(2.0, 0, 0, 0.5, 0, 0).singular_values()
    assert (s_max, s_min) == (pytest.approx(2.0), pytest.approx(0.5))
    c, s = math.cos(0.7), math.sin(0.7)
    s_max, s_min = Mat(c, s, -s, c, 0, 0).singular_values()
    assert s_max == pytest.approx(1.0) and s_min == pytest.approx(1.0)

def test_from_seq():
    assert Mat.from_seq([1, 0, 0, 1, 5, 6]) == Mat(1, 0, 0, 1, 5, 6)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_geometry.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/pdf/geometry.py`)

```python
"""2D affine transforms, PDF row-vector convention: (x,y) -> (a*x+c*y+e, b*x+d*y+f)."""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class Mat:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @classmethod
    def from_seq(cls, seq) -> "Mat":
        a, b, c, d, e, f = (float(v) for v in seq)
        return cls(a, b, c, d, e, f)

    def __matmul__(self, o: "Mat") -> "Mat":
        # self applied first, then o (row vectors: v' = v @ self @ o)
        return Mat(
            self.a * o.a + self.b * o.c,
            self.a * o.b + self.b * o.d,
            self.c * o.a + self.d * o.c,
            self.c * o.b + self.d * o.d,
            self.e * o.a + self.f * o.c + o.e,
            self.e * o.b + self.f * o.d + o.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def vertical_scale(self) -> float:
        return math.hypot(self.c, self.d)

    def singular_values(self) -> tuple[float, float]:
        t = self.a * self.a + self.b * self.b + self.c * self.c + self.d * self.d
        det = self.a * self.d - self.b * self.c
        root = math.sqrt(max(t * t - 4 * det * det, 0.0))
        return (math.sqrt(max((t + root) / 2, 0.0)), math.sqrt(max((t - root) / 2, 0.0)))
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_geometry.py -q` → 5 passed.

- [ ] **Step 5: Commit** — `git add figspec/pdf/ tests/test_geometry.py && git commit -m "feat: PDF affine matrix helpers"`

---

### Task 4: Hand-built sample PDFs (`figspec/selftest/samples.py`)

These are runtime-dependency-only fixtures (pikepdf, no matplotlib) used by both unit tests and `--self-test`. Ground truth: good.pdf = 7 pt text + 6 pt rotated text + 0.75 pt line on an 89 mm page; bad.pdf = `0.4 cm-scale` then 8 pt text (effective 3.2) + 0.5 pt line (effective 0.2) on a 183 mm page; form.pdf = text at 10 pt inside a Form XObject with /Matrix 0.5 placed under a 0.6 CTM (effective 3.0).

**Files:**
- Create: `figspec/selftest/__init__.py` (empty), `figspec/selftest/samples.py`, `tests/test_samples.py`

**Interfaces:**
- Produces: `write_samples(dirpath: Path) -> dict[str, Path]` with keys `"good"`, `"bad"`, `"form"`. Expected-value constants: `GOOD_SIZES = {7.0, 6.0}`, `BAD_EFFECTIVE_FONT = 3.2`, `BAD_EFFECTIVE_LINE = 0.2`, `FORM_EFFECTIVE_FONT = 3.0`.

- [ ] **Step 1: Write the failing test** (`tests/test_samples.py`)

```python
import pikepdf
from figspec.selftest.samples import write_samples

def test_samples_are_valid_pdfs(tmp_path):
    paths = write_samples(tmp_path)
    assert set(paths) == {"good", "bad", "form"}
    for p in paths.values():
        with pikepdf.open(p) as pdf:
            assert len(pdf.pages) == 1

def test_good_page_is_89mm(tmp_path):
    paths = write_samples(tmp_path)
    with pikepdf.open(paths["good"]) as pdf:
        box = pdf.pages[0].MediaBox
        assert abs(float(box[2]) - 252.28) < 0.5  # 89 mm in pt
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_samples.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/selftest/samples.py`)

```python
"""Hand-authored sample PDFs with exactly known geometry (no matplotlib needed)."""
from pathlib import Path
import pikepdf

GOOD_SIZES = {7.0, 6.0}
BAD_EFFECTIVE_FONT = 3.2   # 8 pt * 0.4 cm-scale
BAD_EFFECTIVE_LINE = 0.2   # 0.5 w * 0.4
FORM_EFFECTIVE_FONT = 3.0  # 10 pt * 0.5 form matrix * 0.6 ctm

_GOOD = b"""q
BT /F1 7 Tf 1 0 0 1 20 60 Tm (Good 7pt label) Tj ET
BT /F1 6 Tf 0 1 -1 0 240 20 Tm (Rotated 6pt) Tj ET
0.75 w 20 30 m 200 30 l S
Q"""

_BAD = b"""q
0.4 0 0 0.4 10 10 cm
BT /F1 8 Tf 1 0 0 1 20 120 Tm (Scaled tiny text) Tj ET
0.5 w 20 30 m 400 30 l S
Q"""

_FORM_INNER = b"BT /F1 10 Tf 1 0 0 1 5 5 Tm (Inner form text) Tj ET"
_FORM_PAGE = b"q 0.6 0 0 0.6 20 20 cm /Fm1 Do Q"

def _helvetica() -> pikepdf.Dictionary:
    return pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
    )

def _simple_pdf(stream: bytes, width_pt: float, height_pt: float, path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(width_pt, height_pt))
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=_helvetica()))
    page.Contents = pdf.make_stream(stream)
    pdf.save(path)

def _form_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    form = pdf.make_stream(_FORM_INNER)
    form.Type = pikepdf.Name.XObject
    form.Subtype = pikepdf.Name.Form
    form.BBox = pikepdf.Array([0, 0, 100, 50])
    form.Matrix = pikepdf.Array([0.5, 0, 0, 0.5, 0, 0])
    form.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=_helvetica()))
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm1=form))
    page.Contents = pdf.make_stream(_FORM_PAGE)
    pdf.save(path)

def write_samples(dirpath: Path) -> dict[str, Path]:
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    good, bad, form = dirpath / "good.pdf", dirpath / "bad.pdf", dirpath / "form.pdf"
    _simple_pdf(_GOOD, 89 * 72 / 25.4, 200, good)    # 89 mm wide
    _simple_pdf(_BAD, 183 * 72 / 25.4, 200, bad)     # 183 mm wide
    _form_pdf(form)
    return {"good": good, "bad": bad, "form": form}
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_samples.py -q` → 2 passed.

- [ ] **Step 5: Commit** — `git add figspec/selftest/ tests/test_samples.py && git commit -m "feat: hand-built sample PDFs with known ground truth"`

---

### Task 5: Font metadata (`figspec/pdf/fonts.py`)

**Files:**
- Create: `figspec/pdf/fonts.py`, `tests/test_fonts.py`

**Interfaces:**
- Produces:
  - `FontInfo` dataclass: `name: str`, `code_size: int` (1 or 2), `widths: dict[int, float]` (code → advance per 1.0 font size, text-space), `default_width: float` (0.5), `to_unicode: dict[int, str] | None`, `latin_fallback: bool`.
  - `load_font(fontdict: pikepdf.Object) -> FontInfo` — handles Type1/TrueType (/FirstChar+/Widths ÷1000), Type3 (/Widths × FontMatrix[0]), Type0/CID (/DescendantFonts[0] /W and /DW ÷1000, 2-byte codes), parses /ToUnicode bfchar+bfrange.
  - `decode_codes(fi: FontInfo, data: bytes) -> list[tuple[int, str]]` — (code, unicode-or-empty) pairs; latin-1 fallback for simple fonts without ToUnicode.

- [ ] **Step 1: Write the failing test** (`tests/test_fonts.py`)

```python
import pikepdf
from figspec.pdf.fonts import load_font, decode_codes

def _simple_font(pdf):
    return pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.TrueType,
        BaseFont=pikepdf.Name("/Test"), FirstChar=65, LastChar=67,
        Widths=pikepdf.Array([500, 600, 700]),
    )

def test_simple_font_widths():
    pdf = pikepdf.Pdf.new()
    fi = load_font(_simple_font(pdf))
    assert fi.code_size == 1
    assert fi.widths[65] == 0.5 and fi.widths[67] == 0.7
    assert decode_codes(fi, b"ABC") == [(65, "A"), (66, "B"), (67, "C")]  # latin-1 fallback

def test_type3_widths_use_fontmatrix():
    pdf = pikepdf.Pdf.new()
    f = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type3,
        FontMatrix=pikepdf.Array([0.0005, 0, 0, 0.0005, 0, 0]),
        FirstChar=65, LastChar=65, Widths=pikepdf.Array([1000]),
    )
    fi = load_font(f)
    assert fi.widths[65] == 0.5  # 1000 glyph units * 0.0005

def test_tounicode_bfchar_and_bfrange():
    pdf = pikepdf.Pdf.new()
    cmap = (b"begincmap\n"
            b"2 beginbfchar\n<0041> <0058>\n<0042> <0059>\nendbfchar\n"
            b"1 beginbfrange\n<0050> <0052> <0061>\nendbfrange\n"
            b"endcmap")
    f = _simple_font(pdf)
    f.ToUnicode = pdf.make_stream(cmap)
    fi = load_font(f)
    assert fi.to_unicode[0x41] == "X"
    assert fi.to_unicode[0x51] == "b"  # 0x50->a, 0x51->b, 0x52->c

def test_cid_font_w_array():
    pdf = pikepdf.Pdf.new()
    desc = pikepdf.Dictionary(
        Subtype=pikepdf.Name.CIDFontType2, DW=1000,
        W=pikepdf.Array([3, pikepdf.Array([400, 500]), 10, 12, 600]),
    )
    f = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        DescendantFonts=pikepdf.Array([desc]),
    )
    fi = load_font(f)
    assert fi.code_size == 2
    assert fi.widths[3] == 0.4 and fi.widths[4] == 0.5
    assert fi.widths[11] == 0.6
    assert fi.default_width == 1.0
    assert [c for c, _ in decode_codes(fi, b"\x00\x03\x00\x0b")] == [3, 11]
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_fonts.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/pdf/fonts.py`)

```python
"""Font metadata: advance widths and ToUnicode decoding (best effort)."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

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
```

Note the deliberate helper: at top of file, after imports, add
```python
import pikepdf
pikepdf_Array_types = (pikepdf.Array, list)
```
(the /W array's inner element is a pikepdf.Array; `isinstance` works for pikepdf.Array).

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_fonts.py -q` → 4 passed. If `isinstance(items[i+1], pikepdf.Array)` fails in practice, replace the check with `hasattr(items[i+1], "__len__") and not isinstance(items[i+1], (int, float))` and re-run.

- [ ] **Step 5: Commit** — `git add figspec/pdf/fonts.py tests/test_fonts.py && git commit -m "feat: font widths and ToUnicode decoding"`

---

### Task 6: Interpreter — text runs (`figspec/pdf/interpreter.py`)

**Files:**
- Create: `figspec/pdf/interpreter.py`, `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `Mat` (Task 3), `load_font`/`decode_codes`/`FontInfo` (Task 5), `write_samples` (Task 4).
- Produces (consumed by checks/annotate/cli):
  - `TextRun(page_index: int, text: str, font_name: str, nominal_pt: float, effective_pt: float, scale: float, bbox_pt: tuple)`
  - `StrokePath(page_index: int, nominal_w_pt: float, effective_w_pt: float, bbox_pt: tuple)` (Task 7)
  - `PlacedImage(page_index: int, px_w: int, px_h: int, effective_dpi: float, bbox_pt: tuple)` (Task 7)
  - `PageInfo(index: int, width_pt: float, height_pt: float)`
  - `DocumentContent(pages: list[PageInfo], text_runs: list[TextRun], strokes: list[StrokePath], images: list[PlacedImage], parse_errors: list[tuple[int, str]])`
  - `extract(path: str | Path) -> DocumentContent` — raises `LintInputError(msg)` for missing/encrypted/broken files.

- [ ] **Step 1: Write the failing test** (`tests/test_interpreter.py`)

```python
import pytest
from figspec.pdf.interpreter import extract
from figspec.selftest.samples import write_samples, BAD_EFFECTIVE_FONT

@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    return write_samples(tmp_path_factory.mktemp("samples"))

def test_good_text_runs(samples):
    doc = extract(samples["good"])
    sizes = sorted(r.effective_pt for r in doc.text_runs)
    assert sizes == [pytest.approx(6.0), pytest.approx(7.0)]
    rot = next(r for r in doc.text_runs if r.nominal_pt == 6.0)
    assert rot.effective_pt == pytest.approx(6.0)  # rotation must not shrink size
    assert "Good 7pt label" in {r.text for r in doc.text_runs}

def test_bad_text_scaled(samples):
    doc = extract(samples["bad"])
    (run,) = doc.text_runs
    assert run.nominal_pt == pytest.approx(8.0)
    assert run.scale == pytest.approx(0.4)
    assert run.effective_pt == pytest.approx(BAD_EFFECTIVE_FONT)

def test_bbox_sane(samples):
    doc = extract(samples["good"])
    run = next(r for r in doc.text_runs if r.nominal_pt == 7.0)
    x0, y0, x1, y1 = run.bbox_pt
    assert x1 > x0 and y1 > y0
    assert x0 == pytest.approx(20, abs=1) and y0 == pytest.approx(60 - 7 * 0.25, abs=2)

def test_page_info(samples):
    doc = extract(samples["bad"])
    assert doc.pages[0].width_pt == pytest.approx(183 * 72 / 25.4, abs=0.5)

def test_missing_file_raises():
    from figspec.pdf.interpreter import LintInputError
    with pytest.raises(LintInputError):
        extract("/nonexistent/nope.pdf")
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_interpreter.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/pdf/interpreter.py`) — text machinery only this task; stroke/image/XObject handlers land in Tasks 7–8 but the operator dispatch skeleton is written now:

```python
"""Graphics-state machine over pikepdf.parse_content_stream.

Extracts geometric facts (text runs, stroked paths, placed images) with
*effective* (device-space) sizes. Judgement happens in figspec.lint.checks.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from pathlib import Path
import pikepdf
from figspec.pdf.geometry import Mat
from figspec.pdf.fonts import FontInfo, load_font, decode_codes

class LintInputError(Exception):
    """File cannot be read as a PDF (missing, encrypted, corrupt)."""

@dataclass
class TextRun:
    page_index: int
    text: str
    font_name: str
    nominal_pt: float
    effective_pt: float
    scale: float
    bbox_pt: tuple

@dataclass
class StrokePath:
    page_index: int
    nominal_w_pt: float
    effective_w_pt: float
    bbox_pt: tuple

@dataclass
class PlacedImage:
    page_index: int
    px_w: int
    px_h: int
    effective_dpi: float
    bbox_pt: tuple

@dataclass
class PageInfo:
    index: int
    width_pt: float
    height_pt: float

@dataclass
class DocumentContent:
    pages: list[PageInfo] = field(default_factory=list)
    text_runs: list[TextRun] = field(default_factory=list)
    strokes: list[StrokePath] = field(default_factory=list)
    images: list[PlacedImage] = field(default_factory=list)
    parse_errors: list[tuple[int, str]] = field(default_factory=list)

@dataclass
class _GState:
    ctm: Mat = field(default_factory=Mat)
    line_width: float = 1.0

@dataclass
class _TState:
    font: FontInfo | None = None
    size: float = 0.0
    char_spacing: float = 0.0
    word_spacing: float = 0.0
    h_scale: float = 1.0
    leading: float = 0.0
    rise: float = 0.0
    render_mode: int = 0

def _num(x) -> float:
    return float(x)

def _bbox_union(points) -> tuple:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))

class _Walker:
    def __init__(self, doc: DocumentContent, page_index: int):
        self.doc = doc
        self.page_index = page_index

    def walk(self, container, resources, ctm: Mat, form_stack: frozenset):
        gs = _GState(ctm=ctm)
        stack: list[_GState] = []
        ts = _TState()
        tm = Mat()
        tlm = Mat()
        fonts: dict[str, FontInfo] = {}
        path_pts: list[tuple] = []
        in_text = False

        def font_for(name: str) -> FontInfo:
            if name not in fonts:
                try:
                    fonts[name] = load_font(resources["/Font"][name])
                except Exception:
                    fonts[name] = FontInfo(name=name.lstrip("/"))
            return fonts[name]

        for instr in pikepdf.parse_content_stream(container):
            if isinstance(instr, pikepdf.ContentStreamInlineImage):
                continue  # inline images: out of MVP scope
            op = str(instr.operator)
            ops = instr.operands

            if op == "q":
                stack.append(replace(gs))
            elif op == "Q":
                if stack:
                    gs = stack.pop()
            elif op == "cm":
                gs.ctm = Mat.from_seq(ops) @ gs.ctm
            elif op == "w":
                gs.line_width = _num(ops[0])
            elif op == "gs":
                self._apply_extgstate(gs, resources, ops)
            elif op == "BT":
                in_text, tm, tlm = True, Mat(), Mat()
            elif op == "ET":
                in_text = False
            elif op == "Tf":
                ts.font, ts.size = font_for(str(ops[0])), _num(ops[1])
            elif op == "Td":
                tlm = Mat(1, 0, 0, 1, _num(ops[0]), _num(ops[1])) @ tlm
                tm = tlm
            elif op == "TD":
                ts.leading = -_num(ops[1])
                tlm = Mat(1, 0, 0, 1, _num(ops[0]), _num(ops[1])) @ tlm
                tm = tlm
            elif op == "Tm":
                tm = tlm = Mat.from_seq(ops)
            elif op == "T*":
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = tlm
            elif op == "TL":
                ts.leading = _num(ops[0])
            elif op == "Tc":
                ts.char_spacing = _num(ops[0])
            elif op == "Tw":
                ts.word_spacing = _num(ops[0])
            elif op == "Tz":
                ts.h_scale = _num(ops[0]) / 100.0
            elif op == "Ts":
                ts.rise = _num(ops[0])
            elif op == "Tr":
                ts.render_mode = int(ops[0])
            elif op == "Tj":
                tm = self._show(bytes(ops[0]), ts, tm, gs)
            elif op == "'":
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = self._show(bytes(ops[0]), ts, tlm, gs)
            elif op == '"':
                ts.word_spacing, ts.char_spacing = _num(ops[0]), _num(ops[1])
                tlm = Mat(1, 0, 0, 1, 0, -ts.leading) @ tlm
                tm = self._show(bytes(ops[2]), ts, tlm, gs)
            elif op == "TJ":
                for item in ops[0]:
                    if isinstance(item, pikepdf.String):
                        tm = self._show(bytes(item), ts, tm, gs)
                    else:
                        dx = -_num(item) / 1000.0 * ts.size * ts.h_scale
                        tm = Mat(1, 0, 0, 1, dx, 0) @ tm
            # path + XObject operators land in Tasks 7-8:
            elif op in ("m", "l", "re", "c", "v", "y", "h",
                        "S", "s", "B", "B*", "b", "b*", "f", "F", "f*", "n"):
                path_pts = self._path_op(op, ops, gs, path_pts)
            elif op == "Do":
                self._do_xobject(str(ops[0]), resources, gs, form_stack)

    def _show(self, data: bytes, ts: _TState, tm: Mat, gs: _GState) -> Mat:
        if ts.font is None or ts.size == 0:
            return tm
        pairs = decode_codes(ts.font, data)
        advance = 0.0
        for code, _ in pairs:
            w = ts.font.widths.get(code, ts.font.default_width)
            advance += w * ts.size + ts.char_spacing
            if code == 32 and ts.font.code_size == 1:
                advance += ts.word_spacing
        advance *= ts.h_scale

        combined = tm @ gs.ctm
        scale = combined.vertical_scale()
        if ts.render_mode not in (3, 7):  # skip invisible / clip-only text
            corners = [
                combined.apply(0, ts.rise - 0.25 * ts.size),
                combined.apply(advance, ts.rise - 0.25 * ts.size),
                combined.apply(0, ts.rise + 0.85 * ts.size),
                combined.apply(advance, ts.rise + 0.85 * ts.size),
            ]
            text = "".join(u for _, u in pairs)
            self.doc.text_runs.append(TextRun(
                page_index=self.page_index,
                text=text if text.strip() else "(undecoded text)",
                font_name=ts.font.name,
                nominal_pt=ts.size,
                effective_pt=ts.size * scale,
                scale=scale,
                bbox_pt=_bbox_union(corners),
            ))
        return Mat(1, 0, 0, 1, advance, 0) @ tm

    def _apply_extgstate(self, gs, resources, ops):
        pass  # Task 8

    def _path_op(self, op, ops, gs, path_pts):
        return path_pts  # Task 7

    def _do_xobject(self, name, resources, gs, form_stack):
        pass  # Tasks 7-8

def _page_resources(page) -> pikepdf.Object:
    res = page.get("/Resources")
    return res if res is not None else pikepdf.Dictionary()

def extract(path) -> DocumentContent:
    path = Path(path)
    doc = DocumentContent()
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError as e:
        raise LintInputError(f"{path}: encrypted PDF (password required)") from e
    except Exception as e:
        raise LintInputError(f"{path}: cannot open as PDF: {e}") from e
    with pdf:
        for i, page in enumerate(pdf.pages):
            box = [float(v) for v in page.MediaBox]
            doc.pages.append(PageInfo(index=i, width_pt=box[2] - box[0], height_pt=box[3] - box[1]))
            try:
                _Walker(doc, i).walk(page, _page_resources(page), Mat(), frozenset())
            except Exception as e:
                doc.parse_errors.append((i, f"{type(e).__name__}: {e}"))
    return doc
```

Note on `resources["/Font"][name]`: `name` arrives as `"/F1"` from `str(ops[0])`; pikepdf Dictionary supports string-key subscripting with the leading slash.

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_interpreter.py tests/ -q` → all pass. Debug notes: if `isinstance(item, pikepdf.String)` fails inside TJ, use `if not isinstance(item, (int, float)) and str(type(item)).find("String") >= 0` diagnosis first, then adjust; pikepdf ≥9 supports the isinstance check.

- [ ] **Step 5: Commit** — `git add figspec/pdf/interpreter.py tests/test_interpreter.py && git commit -m "feat: content-stream interpreter with effective text sizes"`

---

### Task 7: Interpreter — strokes and images

**Files:**
- Modify: `figspec/pdf/interpreter.py` (fill `_path_op`, image branch of `_do_xobject`)
- Test: append to `tests/test_interpreter.py`

**Interfaces:**
- Consumes/Produces: as declared in Task 6 (`StrokePath`, `PlacedImage` now actually emitted).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_interpreter.py`)

```python
def test_good_stroke(samples):
    doc = extract(samples["good"])
    (s,) = doc.strokes
    assert s.nominal_w_pt == pytest.approx(0.75)
    assert s.effective_w_pt == pytest.approx(0.75)

def test_bad_stroke_scaled(samples):
    doc = extract(samples["bad"])
    (s,) = doc.strokes
    assert s.effective_w_pt == pytest.approx(0.2)
    x0, y0, x1, y1 = s.bbox_pt
    assert x0 == pytest.approx(10 + 20 * 0.4) and x1 == pytest.approx(10 + 400 * 0.4)

def test_image_dpi(tmp_path):
    import pikepdf
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(300, 300))
    img = pdf.make_stream(b"\x00" * (10 * 10),
                          Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                          Width=10, Height=10, ColorSpace=pikepdf.Name.DeviceGray,
                          BitsPerComponent=8)
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im1=img))
    # 10 px image drawn 144 pt (= 2 in) wide -> 5 dpi
    page.Contents = pdf.make_stream(b"q 144 0 0 144 10 10 cm /Im1 Do Q")
    p = tmp_path / "img.pdf"
    pdf.save(p)
    doc = extract(p)
    (im,) = doc.images
    assert im.px_w == 10 and im.effective_dpi == pytest.approx(5.0)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_interpreter.py -q` → new tests FAIL (no strokes/images emitted).

- [ ] **Step 3: Implement** — replace the two stubs in `_Walker`:

```python
    def _path_op(self, op, ops, gs, path_pts):
        nums = [_num(v) for v in ops]
        if op == "m" or op == "l":
            path_pts.append(gs.ctm.apply(nums[0], nums[1]))
        elif op == "c":
            for i in range(0, 6, 2):
                path_pts.append(gs.ctm.apply(nums[i], nums[i + 1]))
        elif op == "v" or op == "y":
            for i in range(0, 4, 2):
                path_pts.append(gs.ctm.apply(nums[i], nums[i + 1]))
        elif op == "re":
            x, y, w, h = nums
            for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                path_pts.append(gs.ctm.apply(px, py))
        elif op == "h":
            pass
        elif op in ("S", "s", "B", "B*", "b", "b*"):
            if path_pts:
                _, s_min = gs.ctm.singular_values()
                self.doc.strokes.append(StrokePath(
                    page_index=self.page_index,
                    nominal_w_pt=gs.line_width,
                    effective_w_pt=gs.line_width * s_min,
                    bbox_pt=_bbox_union(path_pts),
                ))
            return []
        elif op in ("f", "F", "f*", "n"):
            return []
        return path_pts

    def _do_xobject(self, name, resources, gs, form_stack):
        try:
            xobj = resources["/XObject"][name]
        except Exception:
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
            px_w, px_h = int(xobj.Width), int(xobj.Height)
            ex = (gs.ctm.a ** 2 + gs.ctm.b ** 2) ** 0.5   # device length of unit x edge, pt
            ey = (gs.ctm.c ** 2 + gs.ctm.d ** 2) ** 0.5
            dpi_x = px_w / (ex / 72.0) if ex > 1e-9 else float("inf")
            dpi_y = px_h / (ey / 72.0) if ey > 1e-9 else float("inf")
            corners = [gs.ctm.apply(x, y) for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))]
            self.doc.images.append(PlacedImage(
                page_index=self.page_index, px_w=px_w, px_h=px_h,
                effective_dpi=min(dpi_x, dpi_y), bbox_pt=_bbox_union(corners),
            ))
        elif subtype == "/Form":
            pass  # Task 8
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/ -q` → all pass.

- [ ] **Step 5: Commit** — `git add -u tests/ figspec/ && git commit -m "feat: effective line widths and placed-image DPI"`

---

### Task 8: Interpreter — Form XObject recursion, ExtGState, parse errors

**Files:**
- Modify: `figspec/pdf/interpreter.py`
- Test: append to `tests/test_interpreter.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_interpreter.py`)

```python
def test_form_xobject_recursion(samples):
    from figspec.selftest.samples import FORM_EFFECTIVE_FONT
    doc = extract(samples["form"])
    (run,) = doc.text_runs
    assert run.effective_pt == pytest.approx(FORM_EFFECTIVE_FONT)  # 10 * 0.5 * 0.6
    assert run.scale == pytest.approx(0.3)

def test_extgstate_linewidth(tmp_path):
    import pikepdf
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    egs = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, LW=2.5)
    page.Resources = pikepdf.Dictionary(ExtGState=pikepdf.Dictionary(G1=egs))
    page.Contents = pdf.make_stream(b"q /G1 gs 10 10 m 100 10 l S Q")
    p = tmp_path / "egs.pdf"
    pdf.save(p)
    doc = extract(p)
    assert doc.strokes[0].nominal_w_pt == pytest.approx(2.5)

def test_broken_page_degrades(tmp_path):
    import pikepdf
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    page.Contents = pdf.make_stream(b"BT /NoSuchFont 8 Tf (x) Tj ET 5 5 m 50 5 l S")
    p = tmp_path / "broken.pdf"
    pdf.save(p)
    doc = extract(p)          # must not raise
    assert len(doc.strokes) == 1  # remaining content still extracted
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_interpreter.py -q` → form/extgstate tests FAIL.

- [ ] **Step 3: Implement** — fill remaining stubs in `_Walker`:

```python
    def _apply_extgstate(self, gs, resources, ops):
        try:
            egs = resources["/ExtGState"][str(ops[0])]
            lw = egs.get("/LW")
            if lw is not None:
                gs.line_width = _num(lw)
        except Exception:
            pass
```

and in `_do_xobject`, replace the `/Form` branch:

```python
        elif subtype == "/Form":
            key = (xobj.objgen if xobj.is_indirect else id(xobj))
            if key in form_stack:
                return  # cycle guard
            matrix = xobj.get("/Matrix")
            inner_ctm = (Mat.from_seq(matrix) if matrix is not None else Mat()) @ gs.ctm
            inner_res = xobj.get("/Resources")
            if inner_res is None:
                inner_res = resources
            self.walk(xobj, inner_res, inner_ctm, form_stack | {key})
```

`_do_xobject`'s signature already takes `form_stack`; `walk` already passes it through. Also make the no-such-font path robust: `font_for` already falls back to a bare `FontInfo`, and `extract` wraps each page in try/except appending to `parse_errors` — verify `test_broken_page_degrades` passes without changes (the missing font must not abort the page walk).

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/ -q` → all pass.

- [ ] **Step 5: Commit** — `git add -u figspec/ tests/ && git commit -m "feat: form xobject recursion and extgstate line width"`

---

### Task 9: Checks (`figspec/lint/checks.py`)

**Files:**
- Create: `figspec/lint/__init__.py` (empty), `figspec/lint/checks.py`, `tests/test_checks.py`

**Interfaces:**
- Consumes: `DocumentContent`, `TextRun`, `StrokePath`, `PlacedImage`, `PageInfo` (Task 6).
- Produces:
  - `LintConfig(min_font_pt=5.0, min_linewidth_pt=0.25, width_pt=None, width_tol_mm=2.0, min_raster_dpi=300.0)`
  - `Finding(check_id, level, message, evidence, page=None, boxes_pt=[], bbox_mm=None, nominal_pt=None, scale=None, effective_pt=None)`
  - `run_checks(doc: DocumentContent, cfg: LintConfig) -> list[Finding]` — always emits one finding per check_id minimum (PASS if clean); violation grouping key = `(page, round(nominal,1), round(scale,3))`.

- [ ] **Step 1: Write the failing test** (`tests/test_checks.py`)

```python
import pytest
from figspec.pdf.interpreter import DocumentContent, PageInfo, TextRun, StrokePath, PlacedImage
from figspec.lint.checks import LintConfig, run_checks
from figspec.units import mm_to_pt

def _doc(**kw):
    base = dict(pages=[PageInfo(0, mm_to_pt(183), 300)], text_runs=[], strokes=[],
                images=[], parse_errors=[])
    base.update(kw)
    return DocumentContent(**base)

def _run(text, nominal, scale, page=0):
    return TextRun(page, text, "Helvetica", nominal, nominal * scale, scale,
                   (10, 10, 60, 20))

def by_id(findings):
    out = {}
    for f in findings:
        out.setdefault(f.check_id, []).append(f)
    return out

def test_font_fail_and_grouping():
    doc = _doc(text_runs=[_run("a", 8.0, 0.4), _run("b", 8.0, 0.4), _run("ok", 7.0, 1.0)])
    fs = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert len(fs) == 1                      # two same-size violations grouped
    f = fs[0]
    assert f.level == "FAIL"
    assert f.effective_pt == pytest.approx(3.2)
    assert f.nominal_pt == 8.0 and f.scale == pytest.approx(0.4)
    assert len(f.boxes_pt) == 2
    assert "3.2" in f.message

def test_font_pass():
    doc = _doc(text_runs=[_run("ok", 7.0, 1.0)])
    (f,) = by_id(run_checks(doc, LintConfig()))["FONT-EFFECTIVE"]
    assert f.level == "PASS"

def test_linewidth_and_zero_w():
    doc = _doc(strokes=[StrokePath(0, 0.5, 0.2, (0, 0, 10, 10)),
                        StrokePath(0, 0.0, 0.0, (0, 0, 10, 10))])
    fs = by_id(run_checks(doc, LintConfig()))["LINEWIDTH-EFFECTIVE"]
    assert all(f.level == "FAIL" for f in fs)
    assert any("thinnest" in f.message for f in fs)

def test_final_width():
    doc = _doc()
    cfg = LintConfig(width_pt=mm_to_pt(183))
    (f,) = by_id(run_checks(doc, cfg))["FINAL-WIDTH"]
    assert f.level == "PASS"
    cfg = LintConfig(width_pt=mm_to_pt(89))
    (f,) = by_id(run_checks(doc, cfg))["FINAL-WIDTH"]
    assert f.level == "WARN"
    assert "183.0" in f.message and "89.0" in f.message

def test_text_present_and_raster():
    doc = _doc(images=[PlacedImage(0, 100, 100, 50.0, (0, 0, 144, 144))])
    d = by_id(run_checks(doc, LintConfig()))
    assert d["TEXT-PRESENT"][0].level == "WARN"
    assert d["RASTER-DPI"][0].level == "WARN"
    assert "50" in d["RASTER-DPI"][0].message

def test_page_parse_warn():
    doc = _doc(parse_errors=[(0, "ValueError: boom")])
    assert by_id(run_checks(doc, LintConfig()))["PAGE-PARSE"][0].level == "WARN"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_checks.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/lint/checks.py`)

```python
"""Judgement layer: thresholds applied to extracted geometry."""
from __future__ import annotations
from dataclasses import dataclass, field
from figspec.pdf.interpreter import DocumentContent
from figspec.units import pt_to_mm

EPS = 0.01

@dataclass
class LintConfig:
    min_font_pt: float = 5.0
    min_linewidth_pt: float = 0.25
    width_pt: float | None = None
    width_tol_mm: float = 2.0
    min_raster_dpi: float = 300.0

@dataclass
class Finding:
    check_id: str
    level: str  # PASS | WARN | FAIL
    message: str
    evidence: list[str] = field(default_factory=list)
    page: int | None = None
    boxes_pt: list[tuple] = field(default_factory=list)
    bbox_mm: tuple | None = None
    nominal_pt: float | None = None
    scale: float | None = None
    effective_pt: float | None = None

def _union_mm(boxes) -> tuple | None:
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    return tuple(round(pt_to_mm(v), 2) for v in (x0, y0, x1, y1))

def _check_font(doc, cfg):
    bad = [r for r in doc.text_runs if r.effective_pt < cfg.min_font_pt - EPS]
    if not bad:
        yield Finding("FONT-EFFECTIVE", "PASS",
                      f"All text at or above {cfg.min_font_pt:g} pt effective")
        return
    groups: dict[tuple, list] = {}
    for r in bad:
        groups.setdefault((r.page_index, round(r.nominal_pt, 1), round(r.scale, 3)), []).append(r)
    for (page, nominal, scale), runs in sorted(groups.items()):
        eff = nominal * scale
        ev = [f"page {page + 1}: {r.text!r} nominal {r.nominal_pt:g} pt x scale "
              f"{r.scale:.3f} = {r.effective_pt:.2f} pt" for r in runs[:3]]
        if len(runs) > 3:
            ev.append(f"...and {len(runs) - 3} more runs at this size")
        yield Finding(
            "FONT-EFFECTIVE", "FAIL",
            f"Text effective size {eff:.2f} pt below {cfg.min_font_pt:g} pt minimum "
            f"({len(runs)} run(s))",
            evidence=ev, page=page, boxes_pt=[r.bbox_pt for r in runs],
            bbox_mm=_union_mm([r.bbox_pt for r in runs]),
            nominal_pt=nominal, scale=scale, effective_pt=round(eff, 2),
        )

def _check_linewidth(doc, cfg):
    bad = [s for s in doc.strokes if s.effective_w_pt < cfg.min_linewidth_pt - EPS]
    if not bad:
        yield Finding("LINEWIDTH-EFFECTIVE", "PASS",
                      f"All stroked lines at or above {cfg.min_linewidth_pt:g} pt effective")
        return
    groups: dict[tuple, list] = {}
    for s in bad:
        scale = (s.effective_w_pt / s.nominal_w_pt) if s.nominal_w_pt > 0 else 1.0
        groups.setdefault((s.page_index, round(s.nominal_w_pt, 2), round(scale, 3)), []).append(s)
    for (page, nominal, scale), strokes in sorted(groups.items()):
        eff = strokes[0].effective_w_pt
        if nominal == 0:
            msg = (f"{len(strokes)} stroke(s) use line width 0 "
                   f"(PDF 'thinnest renderable line'; prints unpredictably)")
        else:
            msg = (f"Stroke effective width {eff:.2f} pt below "
                   f"{cfg.min_linewidth_pt:g} pt minimum ({len(strokes)} stroke(s))")
        yield Finding(
            "LINEWIDTH-EFFECTIVE", "FAIL", msg,
            evidence=[f"page {page + 1}: nominal {nominal:g} pt x scale {scale:.3f} "
                      f"= {eff:.2f} pt"],
            page=page, boxes_pt=[s.bbox_pt for s in strokes],
            bbox_mm=_union_mm([s.bbox_pt for s in strokes]),
            nominal_pt=nominal, scale=scale, effective_pt=round(eff, 2),
        )

def _check_width(doc, cfg):
    if cfg.width_pt is None or not doc.pages:
        return
    actual_mm = pt_to_mm(doc.pages[0].width_pt)
    target_mm = pt_to_mm(cfg.width_pt)
    if abs(actual_mm - target_mm) <= cfg.width_tol_mm:
        yield Finding("FINAL-WIDTH", "PASS",
                      f"Page width {actual_mm:.1f} mm matches target {target_mm:.1f} mm")
    else:
        yield Finding("FINAL-WIDTH", "WARN",
                      f"Page width {actual_mm:.1f} mm does not match target "
                      f"{target_mm:.1f} mm (tolerance +/-{cfg.width_tol_mm:g} mm)")

def _check_text_present(doc, cfg):
    if doc.text_runs:
        yield Finding("TEXT-PRESENT", "PASS",
                      f"{len(doc.text_runs)} text run(s) found")
    else:
        yield Finding("TEXT-PRESENT", "WARN",
                      "No text objects found: text may be outlined (converted to paths) "
                      "or the figure may be a pure bitmap; font checks cannot run")

def _check_raster(doc, cfg):
    if not doc.images:
        yield Finding("RASTER-DPI", "PASS", "No raster images placed")
        return
    bad = [im for im in doc.images if im.effective_dpi < cfg.min_raster_dpi - EPS]
    if not bad:
        yield Finding("RASTER-DPI", "PASS",
                      f"All {len(doc.images)} raster image(s) at or above "
                      f"{cfg.min_raster_dpi:g} dpi effective")
        return
    for im in bad:
        yield Finding(
            "RASTER-DPI", "WARN",
            f"Raster image {im.px_w}x{im.px_h}px displayed at "
            f"{im.effective_dpi:.0f} dpi effective (below {cfg.min_raster_dpi:g} dpi)",
            page=im.page_index, boxes_pt=[im.bbox_pt], bbox_mm=_union_mm([im.bbox_pt]),
            effective_pt=None,
        )

def _check_parse_errors(doc, cfg):
    for page, msg in doc.parse_errors:
        yield Finding("PAGE-PARSE", "WARN",
                      f"Page {page + 1} only partially analyzed",
                      evidence=[msg], page=page)

def run_checks(doc: DocumentContent, cfg: LintConfig) -> list:
    findings = []
    for chk in (_check_font, _check_linewidth, _check_width,
                _check_text_present, _check_raster, _check_parse_errors):
        findings.extend(chk(doc, cfg))
    return findings
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_checks.py -q` → 6 passed.

- [ ] **Step 5: Commit** — `git add figspec/lint/ tests/test_checks.py && git commit -m "feat: lint checks with grouping"`

---

### Task 10: Report rendering (`figspec/lint/report.py`)

**Files:**
- Create: `figspec/lint/report.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `Finding` (Task 9), `figspec.__version__`.
- Produces:
  - `summarize(findings, strict: bool) -> dict` — `{"ready": bool, "strict": bool, "counts": {"PASS": n, "WARN": n, "FAIL": n}}`; ready = no FAIL and (not strict or no WARN).
  - `render_text(source: str, findings, summary, max_evidence: int = 10) -> str`
  - `render_json(source: str, findings, summary) -> dict` (JSON-serializable; findings sorted FAIL→WARN→PASS; omits `boxes_pt`)
  - `exit_code(summary) -> int` (0 or 1)

- [ ] **Step 1: Write the failing test** (`tests/test_report.py`)

```python
import json
from figspec.lint.checks import Finding
from figspec.lint.report import summarize, render_text, render_json, exit_code

F = [Finding("FONT-EFFECTIVE", "FAIL", "Text effective size 3.20 pt below 5 pt minimum",
             evidence=["page 1: 'x' nominal 8 pt x scale 0.400 = 3.20 pt"],
             page=0, nominal_pt=8.0, scale=0.4, effective_pt=3.2),
     Finding("FINAL-WIDTH", "WARN", "Page width mismatch"),
     Finding("RASTER-DPI", "PASS", "No raster images placed")]

def test_summarize_and_exit():
    s = summarize(F, strict=False)
    assert s == {"ready": False, "strict": False, "counts": {"PASS": 1, "WARN": 1, "FAIL": 1}}
    assert exit_code(s) == 1
    ok = summarize([F[2]], strict=False)
    assert ok["ready"] and exit_code(ok) == 0
    warn_only = summarize([F[1]], strict=True)
    assert not warn_only["ready"]

def test_render_text():
    out = render_text("fig.pdf", F, summarize(F, strict=False))
    assert "figspec lint fig.pdf" in out
    assert "[FAIL] FONT-EFFECTIVE" in out
    assert "verdict: FIX BEFORE SUBMISSION" in out
    assert "summary: 1 pass, 1 warn, 1 fail" in out

def test_render_json_roundtrip():
    d = render_json("fig.pdf", F, summarize(F, strict=False))
    j = json.loads(json.dumps(d))
    assert j["tool"]["name"] == "figspec"
    assert j["findings"][0]["check_id"] == "FONT-EFFECTIVE"  # FAIL sorts first
    assert j["findings"][0]["effective_pt"] == 3.2
    assert "boxes_pt" not in j["findings"][0]

def test_evidence_truncation():
    f = Finding("FONT-EFFECTIVE", "FAIL", "m", evidence=[f"e{i}" for i in range(30)])
    out = render_text("x.pdf", [f], summarize([f], False), max_evidence=10)
    assert "e9" in out and "e10" not in out
    assert "20 more evidence lines in --json output" in out
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_report.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/lint/report.py`)

```python
"""Finding formatting: terminal text and machine-readable JSON."""
from __future__ import annotations
from dataclasses import asdict
from figspec import __version__

_ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}

def summarize(findings, strict: bool) -> dict:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for f in findings:
        counts[f.level] += 1
    ready = counts["FAIL"] == 0 and (not strict or counts["WARN"] == 0)
    return {"ready": ready, "strict": strict, "counts": counts}

def render_text(source: str, findings, summary, max_evidence: int = 10) -> str:
    lines = [f"figspec lint {source}"]
    for f in sorted(findings, key=lambda f: (_ORDER[f.level], f.check_id)):
        lines.append(f"[{f.level}] {f.check_id}: {f.message}")
        shown = f.evidence[:max_evidence]
        for ev in shown:
            lines.append(f"  - {ev}")
        hidden = len(f.evidence) - len(shown)
        if hidden > 0:
            lines.append(f"  ({hidden} more evidence lines in --json output)")
    c = summary["counts"]
    lines.append(f"summary: {c['PASS']} pass, {c['WARN']} warn, {c['FAIL']} fail")
    lines.append("verdict: " + ("READY FOR SUBMISSION" if summary["ready"]
                                else "FIX BEFORE SUBMISSION"))
    lines.append("note: figspec lint checks the finished artifact geometry; "
                 "it does not validate scientific content")
    return "\n".join(lines)

def render_json(source: str, findings, summary) -> dict:
    items = []
    for f in sorted(findings, key=lambda f: (_ORDER[f.level], f.check_id)):
        d = asdict(f)
        d.pop("boxes_pt", None)
        if d.get("page") is not None:
            d["page"] = d["page"] + 1  # 1-indexed for humans/agents
        items.append(d)
    return {"source": source,
            "tool": {"name": "figspec", "version": __version__},
            "summary": summary,
            "findings": items}

def exit_code(summary) -> int:
    return 0 if summary["ready"] else 1
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_report.py -q` → 4 passed.

- [ ] **Step 5: Commit** — `git add figspec/lint/report.py tests/test_report.py && git commit -m "feat: text and JSON report rendering"`

---

### Task 11: Annotated PNG (`figspec/lint/annotate.py`)

**Files:**
- Create: `figspec/lint/annotate.py`, `tests/test_annotate.py`

**Interfaces:**
- Consumes: `Finding.boxes_pt`/`page`/`level`/`effective_pt` (Task 9); sample PDFs (Task 4).
- Produces: `annotate(pdf_path, findings, out_path: Path, dpi: float = 150) -> list[Path]` — renders each page that has findings-with-boxes; first output at `out_path`, page N>1 at `<stem>-pN<suffix>`; returns written paths (empty list if nothing to draw). Colors: FAIL `(220, 38, 38)`, WARN `(217, 119, 6)`.

- [ ] **Step 1: Write the failing test** (`tests/test_annotate.py`)

```python
from PIL import Image
from figspec.pdf.interpreter import extract
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.annotate import annotate, FAIL_COLOR
from figspec.selftest.samples import write_samples

def test_annotate_bad_sample(tmp_path):
    paths = write_samples(tmp_path)
    doc = extract(paths["bad"])
    findings = run_checks(doc, LintConfig())
    out = tmp_path / "bad.lint.png"
    written = annotate(paths["bad"], findings, out)
    assert written == [out] and out.exists()
    img = Image.open(out).convert("RGB")
    colors = {c for _, c in img.getcolors(maxcolors=1 << 20)}
    assert FAIL_COLOR in colors  # red boxes drawn

def test_annotate_clean_sample_writes_nothing(tmp_path):
    paths = write_samples(tmp_path)
    doc = extract(paths["good"])
    findings = run_checks(doc, LintConfig())
    written = annotate(paths["good"], findings, tmp_path / "good.lint.png")
    assert written == []
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_annotate.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/lint/annotate.py`)

```python
"""Render violation boxes onto page rasters."""
from __future__ import annotations
from pathlib import Path
import pypdfium2 as pdfium
from PIL import ImageDraw

FAIL_COLOR = (220, 38, 38)
WARN_COLOR = (217, 119, 6)

def annotate(pdf_path, findings, out_path, dpi: float = 150) -> list[Path]:
    out_path = Path(out_path)
    drawable = [f for f in findings if f.boxes_pt and f.page is not None
                and f.level in ("FAIL", "WARN")]
    if not drawable:
        return []
    pages = sorted({f.page for f in drawable})
    written: list[Path] = []
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        scale = dpi / 72.0
        for n, page_index in enumerate(pages):
            page = doc[page_index]
            _, page_h = page.get_size()
            img = page.render(scale=scale).to_pil().convert("RGB")
            draw = ImageDraw.Draw(img)
            for f in (f for f in drawable if f.page == page_index):
                color = FAIL_COLOR if f.level == "FAIL" else WARN_COLOR
                for (x0, y0, x1, y1) in f.boxes_pt:
                    px = (x0 * scale, (page_h - y1) * scale,
                          x1 * scale, (page_h - y0) * scale)
                    draw.rectangle(px, outline=color, width=2)
                label_y = max((page_h - max(b[3] for b in f.boxes_pt)) * scale - 14, 0)
                label_x = min(b[0] for b in f.boxes_pt) * scale
                tag = (f"{f.effective_pt:g} pt ✗" if f.effective_pt is not None
                       else f.check_id)
                draw.text((label_x, label_y), tag, fill=color)
            target = out_path if n == 0 else out_path.with_name(
                f"{out_path.stem}-p{page_index + 1}{out_path.suffix}")
            img.save(target)
            written.append(target)
    finally:
        doc.close()
    return written
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_annotate.py -q` → 2 passed.

- [ ] **Step 5: Commit** — `git add figspec/lint/annotate.py tests/test_annotate.py && git commit -m "feat: annotated PNG output"`

---

### Task 12: CLI wiring (`figspec/cli.py`)

**Files:**
- Modify: `figspec/cli.py` (replace stub)
- Test: replace `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str] | None = None) -> int` implementing the spec CLI. `--json` → const `"-"` (stdout, human report to stderr); `--json PATH` → file. `--annotate` → const `"AUTO"` → `<input>.lint.png`. `--width` parsed with default unit mm. Exit 2 on usage/input errors with message on stderr.

- [ ] **Step 1: Write the failing test** (replace `tests/test_cli.py`)

```python
import json
import pytest
from figspec.cli import main
from figspec.selftest.samples import write_samples

@pytest.fixture()
def samples(tmp_path):
    return write_samples(tmp_path)

def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "figspec" in capsys.readouterr().out

def test_lint_bad_exits_1(samples, capsys):
    rc = main(["lint", str(samples["bad"])])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] FONT-EFFECTIVE" in out
    assert "FIX BEFORE SUBMISSION" in out

def test_lint_good_ready(samples, capsys):
    rc = main(["lint", str(samples["good"]), "--width", "89"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[PASS] FINAL-WIDTH" in out
    assert "READY FOR SUBMISSION" in out

def test_strict_promotes_warn(samples):
    # good.pdf vs wrong width target -> WARN -> strict makes it exit 1
    assert main(["lint", str(samples["good"]), "--width", "183"]) == 0
    assert main(["lint", str(samples["good"]), "--width", "183", "--strict"]) == 1

def test_json_stdout(samples, capsys):
    rc = main(["lint", str(samples["bad"]), "--json"])
    cap = capsys.readouterr()
    data = json.loads(cap.out)          # stdout is pure JSON
    assert data["summary"]["ready"] is False
    assert "FIX BEFORE SUBMISSION" in cap.err  # human report moved to stderr
    assert rc == 1

def test_json_file(samples, tmp_path, capsys):
    p = tmp_path / "r.json"
    main(["lint", str(samples["bad"]), "--json", str(p)])
    assert json.loads(p.read_text())["tool"]["name"] == "figspec"
    assert "FIX BEFORE" in capsys.readouterr().out  # human report stays on stdout

def test_annotate_auto_path(samples):
    main(["lint", str(samples["bad"]), "--annotate"])
    assert samples["bad"].with_suffix(".lint.png").exists()

def test_missing_file_exits_2(capsys):
    assert main(["lint", "/nonexistent/x.pdf"]) == 2
    assert "cannot open" in capsys.readouterr().err

def test_min_font_flag(samples):
    assert main(["lint", str(samples["good"]), "--min-font", "8"]) == 1  # 6pt/7pt text now fails
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_cli.py -q` → failures (stub has no `lint`).

- [ ] **Step 3: Implement** (replace `figspec/cli.py`)

```python
"""figspec command line interface."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from figspec import __version__
from figspec.units import parse_length

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="figspec")
    parser.add_argument("--version", action="version", version=f"figspec {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    lint = sub.add_parser("lint", help="Check a finished figure PDF for effective "
                                       "font sizes and line widths")
    lint.add_argument("pdf", nargs="?", help="Finished figure PDF")
    lint.add_argument("--width", help="Expected figure width, e.g. 183mm (default unit: mm)")
    lint.add_argument("--min-font", type=float, default=5.0, metavar="PT",
                      help="Minimum effective font size in pt (default: 5)")
    lint.add_argument("--min-linewidth", type=float, default=0.25, metavar="PT",
                      help="Minimum effective stroke width in pt (default: 0.25)")
    lint.add_argument("--json", nargs="?", const="-", default=None, metavar="PATH",
                      help="Write JSON report to PATH, or stdout if no PATH given")
    lint.add_argument("--annotate", nargs="?", const="AUTO", default=None, metavar="PATH",
                      help="Write annotated PNG (default: <input>.lint.png)")
    lint.add_argument("--strict", action="store_true",
                      help="Treat WARN findings as not ready")
    lint.add_argument("--self-test", action="store_true",
                      help="Run built-in self test and exit")
    return parser

def _run_lint(args) -> int:
    from figspec.pdf.interpreter import LintInputError, extract
    from figspec.lint.checks import LintConfig, run_checks
    from figspec.lint.report import exit_code, render_json, render_text, summarize

    if args.self_test:
        from figspec.selftest import run_selftest
        return run_selftest()
    if not args.pdf:
        print("error: missing PDF argument (or use --self-test)", file=sys.stderr)
        return 2
    cfg = LintConfig(min_font_pt=args.min_font, min_linewidth_pt=args.min_linewidth)
    if args.width:
        try:
            cfg.width_pt = parse_length(args.width, default_unit="mm")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    try:
        doc = extract(args.pdf)
    except LintInputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = run_checks(doc, cfg)
    summary = summarize(findings, strict=args.strict)

    human = render_text(args.pdf, findings, summary)
    if args.json == "-":
        print(json.dumps(render_json(args.pdf, findings, summary), indent=2))
        print(human, file=sys.stderr)
    else:
        if args.json:
            Path(args.json).write_text(
                json.dumps(render_json(args.pdf, findings, summary), indent=2))
        print(human)
    if args.annotate:
        from figspec.lint.annotate import annotate
        out = (Path(args.pdf).with_suffix(".lint.png")
               if args.annotate == "AUTO" else Path(args.annotate))
        written = annotate(args.pdf, findings, out)
        for p in written:
            print(f"annotated: {p}", file=sys.stderr)
    return exit_code(summary)

def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "lint":
        return _run_lint(args)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `run_selftest` lands in Task 13; until then `--self-test` raises ImportError — acceptable mid-plan state, no test covers it yet.

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_cli.py tests/ -q` → all pass except nothing; full suite green.

- [ ] **Step 5: Commit** — `git add figspec/cli.py tests/test_cli.py && git commit -m "feat: figspec lint CLI"`

---

### Task 13: Self test (`figspec/selftest/__init__.py`)

**Files:**
- Modify: `figspec/selftest/__init__.py`
- Test: append to `tests/test_cli.py`

**Interfaces:**
- Produces: `run_selftest() -> int` — synthesizes samples in a temp dir, asserts: good.pdf → ready; bad.pdf → FONT-EFFECTIVE FAIL at ≈3.2 pt and LINEWIDTH-EFFECTIVE FAIL at ≈0.2 pt; form.pdf → FONT-EFFECTIVE FAIL at ≈3.0 pt. Prints one `[ok]/[FAIL]` line per assertion; returns 0 iff all hold.

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli.py`)

```python
def test_self_test(capsys):
    rc = main(["lint", "--self-test"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[ok]" in out and "[FAIL]" not in out
    assert "self-test passed" in out
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_cli.py::test_self_test -q` → ImportError for `run_selftest`.

- [ ] **Step 3: Implement** (`figspec/selftest/__init__.py`)

```python
"""Built-in self test: synthesizes known-ground-truth PDFs and lints them."""
from __future__ import annotations
import tempfile
from pathlib import Path

def run_selftest() -> int:
    from figspec.lint.checks import LintConfig, run_checks
    from figspec.lint.report import summarize
    from figspec.pdf.interpreter import extract
    from figspec.selftest.samples import (
        BAD_EFFECTIVE_FONT, BAD_EFFECTIVE_LINE, FORM_EFFECTIVE_FONT, write_samples)

    results: list[tuple[str, bool]] = []

    def expect(label: str, cond: bool):
        results.append((label, cond))

    with tempfile.TemporaryDirectory() as td:
        paths = write_samples(Path(td))
        cfg = LintConfig()

        good = run_checks(extract(paths["good"]), cfg)
        expect("good sample is ready", summarize(good, strict=False)["ready"])

        bad = run_checks(extract(paths["bad"]), cfg)
        font = [f for f in bad if f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL"]
        line = [f for f in bad if f.check_id == "LINEWIDTH-EFFECTIVE" and f.level == "FAIL"]
        expect("bad sample: tiny text detected",
               bool(font) and abs(font[0].effective_pt - BAD_EFFECTIVE_FONT) < 0.05)
        expect("bad sample: thin line detected",
               bool(line) and abs(line[0].effective_pt - BAD_EFFECTIVE_LINE) < 0.05)

        form = run_checks(extract(paths["form"]), cfg)
        ffont = [f for f in form if f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL"]
        expect("form xobject: nested scaling detected",
               bool(ffont) and abs(ffont[0].effective_pt - FORM_EFFECTIVE_FONT) < 0.05)

    ok = all(c for _, c in results)
    for label, cond in results:
        print(f"[{'ok' if cond else 'FAIL'}] {label}")
    print("self-test " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/test_cli.py -q && .venv/bin/figspec lint --self-test` → tests pass; CLI prints 4 `[ok]` lines.

- [ ] **Step 5: Commit** — `git add -u figspec/ tests/ && git commit -m "feat: built-in self test"`

---

### Task 14: matplotlib integration fixtures and tests

**Files:**
- Create: `tests/fixtures.py`, `tests/conftest.py`, `tests/test_integration.py`

**Interfaces:**
- Consumes: public API only (`extract`, `run_checks`, `LintConfig`, `main`).
- Produces: pytest fixture `mpl_dir` (session-scoped tmp dir with generated PDFs).

- [ ] **Step 1: Write fixtures** (`tests/fixtures.py`)

```python
"""Synthetic ground-truth figures: matplotlib panels + pypdf scaled assembly."""
from pathlib import Path

def make_panel(path: Path, fontsize: float = 7.0, fonttype: int = 42,
               linewidth: float = 0.5) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "pdf.fonttype": fonttype, "font.size": fontsize,
        "axes.labelsize": fontsize, "xtick.labelsize": fontsize,
        "ytick.labelsize": fontsize, "axes.linewidth": linewidth,
        "xtick.major.width": linewidth, "ytick.major.width": linewidth,
    })
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    ax.plot([0, 1, 2], [0, 1, 0], linewidth=linewidth)
    ax.set_xlabel("Vds (V)")
    ax.set_ylabel("Current (uA)")
    fig.savefig(path)
    plt.close(fig)

def make_textpath_panel(path: Path) -> None:
    """All text converted to paths -> zero text objects."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.patches import PathPatch
    from matplotlib.textpath import TextPath
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.set_axis_off()
    tp = TextPath((0.1, 0.5), "Outlined", size=0.2)
    ax.add_patch(PathPatch(tp, facecolor="black", linewidth=0))
    ax.set_xlim(0, 2); ax.set_ylim(0, 1)
    fig.savefig(path)
    plt.close(fig)

def make_raster_panel(path: Path, px: int = 100, inches: float = 2.0) -> None:
    """A px-by-px image displayed at `inches` -> effective dpi = px / inches."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig = plt.figure(figsize=(inches, inches))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.imshow(np.random.default_rng(0).random((px, px)), interpolation="none")
    fig.savefig(path, dpi=72)
    plt.close(fig)

def compose_scaled(panel: Path, out: Path, scale: float,
                   page_w_mm: float = 183.0, page_h_mm: float = 120.0) -> None:
    """Simulate Illustrator 'place + scale' with pypdf."""
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf import PageObject
    reader = PdfReader(str(panel))
    src = reader.pages[0]
    w, h = page_w_mm * 72 / 25.4, page_h_mm * 72 / 25.4
    page = PageObject.create_blank_page(width=w, height=h)
    page.merge_transformed_page(src, Transformation().scale(scale).translate(20, 20))
    writer = PdfWriter()
    writer.add_page(page)
    with open(out, "wb") as fh:
        writer.write(fh)
```

`tests/conftest.py`:
```python
import pytest
from tests.fixtures import (compose_scaled, make_panel, make_raster_panel,
                            make_textpath_panel)

@pytest.fixture(scope="session")
def mpl_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("mpl")
    make_panel(d / "panel42.pdf", fontsize=7.0, fonttype=42)
    make_panel(d / "panel3.pdf", fontsize=7.0, fonttype=3)
    compose_scaled(d / "panel42.pdf", d / "assembled045.pdf", scale=0.45)
    make_textpath_panel(d / "outlined.pdf")
    make_raster_panel(d / "raster.pdf", px=100, inches=2.0)  # 50 dpi effective
    return d
```

Also add to `pyproject.toml` (so `from tests.fixtures import ...` resolves):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```
and create empty `tests/__init__.py`.

- [ ] **Step 2: Write the failing tests** (`tests/test_integration.py`)

```python
import pytest
from figspec.cli import main
from figspec.lint.checks import LintConfig, run_checks
from figspec.pdf.interpreter import extract

def _sizes(doc):
    return [r.effective_pt for r in doc.text_runs]

def test_unscaled_panel_all_7pt(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    assert doc.text_runs, "matplotlib panel must contain text objects"
    assert all(6.8 <= s <= 7.2 for s in _sizes(doc)), sorted(_sizes(doc))

def test_text_decoded(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    assert any("Vds" in r.text for r in doc.text_runs)

def test_rotated_ylabel_not_shrunk(mpl_dir):
    doc = extract(mpl_dir / "panel42.pdf")
    # ylabel is rotated 90 degrees; a wrong formula would report ~0 or inflated size
    spread = max(_sizes(doc)) - min(_sizes(doc))
    assert spread < 0.4

def test_scaled_assembly_detects_315(mpl_dir):
    doc = extract(mpl_dir / "assembled045.pdf")
    assert min(_sizes(doc)) == pytest.approx(3.15, abs=0.1)
    findings = run_checks(doc, LintConfig())
    assert any(f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL" for f in findings)

def test_fonttype3_matches_fonttype42(mpl_dir):
    s42 = sorted(_sizes(extract(mpl_dir / "panel42.pdf")))
    s3 = sorted(_sizes(extract(mpl_dir / "panel3.pdf")))
    assert min(s42) == pytest.approx(min(s3), abs=0.1)
    assert max(s42) == pytest.approx(max(s3), abs=0.1)

def test_outlined_panel_warns_text_present(mpl_dir):
    doc = extract(mpl_dir / "outlined.pdf")
    assert not doc.text_runs
    findings = run_checks(doc, LintConfig())
    assert any(f.check_id == "TEXT-PRESENT" and f.level == "WARN" for f in findings)

def test_raster_dpi_warn(mpl_dir):
    doc = extract(mpl_dir / "raster.pdf")
    assert doc.images
    assert doc.images[0].effective_dpi == pytest.approx(50, abs=5)

def test_clean_panel_cli_ready(mpl_dir):
    assert main(["lint", str(mpl_dir / "panel42.pdf")]) == 0

def test_assembled_cli_fails(mpl_dir):
    assert main(["lint", str(mpl_dir / "assembled045.pdf"), "--width", "183"]) == 1
```

- [ ] **Step 3: Run** — `.venv/bin/pytest tests/test_integration.py -q`
Expected: PASS if Tasks 5–8 are correct. Likely real-bug surface: matplotlib Type 3 advance widths (FontMatrix scale) and tick-label CID widths. Debug protocol: print `[(r.text, r.nominal_pt, r.effective_pt) for r in doc.text_runs]`, fix `figspec/pdf/fonts.py` width scaling — do NOT widen test tolerances beyond the values written above.

- [ ] **Step 4: Run full suite** — `.venv/bin/pytest tests/ -q` → all pass.

- [ ] **Step 5: Commit** — `git add tests/ pyproject.toml && git commit -m "test: matplotlib+pypdf integration ground-truth suite"`

---

### Task 15: README and final verification

**Files:**
- Create: `README.md`, `README.zh-CN.md`

- [ ] **Step 1: Write `README.md`** (English; structure below, fill with the real CLI output captured from a fresh run of `figspec lint --self-test` and a bad-sample run — no invented output):

````markdown
# figspec

Lint finished figure PDFs for **effective** (post-scaling) font sizes and line widths.

When a matplotlib panel is placed into Illustrator and scaled to fit, a nominal
7 pt label can silently become a 3 pt label. Illustrator's font panel still
shows 7 pt. figspec opens the *finished* PDF, multiplies every text object's
font size through the full PDF transform stack (including Form XObjects —
i.e. placed, scaled panels), and reports what will actually print.

## Install

```bash
pip install figspec
```

## Use

```bash
figspec lint final.pdf --width 183mm
figspec lint final.pdf --json report.json --annotate
figspec lint --self-test
```

## Checks

| check_id | what it verifies | level |
|---|---|---|
| FONT-EFFECTIVE | effective text size >= --min-font (default 5 pt) | FAIL |
| LINEWIDTH-EFFECTIVE | effective stroke width >= --min-linewidth (default 0.25 pt) | FAIL |
| FINAL-WIDTH | page width matches --width (+/- 2 mm) | WARN |
| TEXT-PRESENT | document contains text objects (not outlined/rasterized) | WARN |
| RASTER-DPI | placed bitmaps >= 300 dpi at displayed size | WARN |

Exit codes: 0 ready, 1 findings, 2 input error. `--strict` promotes WARN.
JSON findings use `{check_id, level, message, evidence}` plus
`page/bbox_mm/nominal_pt/scale/effective_pt`.

Part of the FigSpec toolchain (layout spec -> exact-size generation -> artifact
lint). The `figspec.json` layout spec and generator are on the roadmap.

License: Apache-2.0
````

`README.zh-CN.md`: same structure in Chinese (translate faithfully; keep code blocks identical).

- [ ] **Step 2: Full verification**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/figspec lint --self-test && .venv/bin/figspec --version`
Expected: full suite green; self-test prints 4 `[ok]` lines and "self-test passed".

- [ ] **Step 3: Commit** — `git add README.md README.zh-CN.md && git commit -m "docs: bilingual README"`

---

## Self-Review Notes (completed during planning)

- **Spec coverage:** §1 CLI/five checks → Tasks 9, 12; §2 math (SVD, Form XObject, w=0, Type3) → Tasks 3, 6–8; §4 report contract/exit codes/JSON stdout-vs-file → Tasks 10, 12; §5 test matrix items 1–6 → Tasks 4 (hand-built), 14 (matplotlib: scaled 0.45 ✓, fonttype 3/42 parity ✓, rotated ✓, TextPath ✓, raster ✓, clean-pass ✓); §6 error handling → Tasks 6, 8, 12; §7 packaging/README → Tasks 1, 15. `--self-test` → Task 13. UserUnit (§2, "rare but cheap") deliberately deferred post-MVP: pages with /UserUnit are vanishingly rare in figure exports; noted here so it is a conscious cut, not an omission.
- **Type consistency check:** `Finding.boxes_pt` (checks→annotate), `effective_pt` naming, `LintInputError`, `write_samples` keys, `run_selftest` — verified consistent across tasks.
- **Known risk points flagged in-task:** pikepdf `isinstance(String/Array)` behavior (Tasks 5–6 include fallback instructions); matplotlib font subtype variance (Task 14 debug protocol).
