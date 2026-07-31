# Designer Batch C (M1 前奏) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** External-panel assets with effective-DPI indicator, an archetype template library, matplotlib snippet export, and wireframe layout-preview export — per the approved spec `docs/superpowers/specs/2026-07-30-designer-batch-c-design.md`.

**Architecture:** All reusable logic lands in the `figspec` package (templates, snippet, asset path helpers, effective-DPI math) so the MCP server can consume it later; the Designer (`designer/figspec_designer`) only wires UI. The layout tree stays pure data (no Qt in `figspec/`); PanelNode gains optional `asset`/`asset_px` fields serialized in the `designer.tree` sidecar, and spec export marks such panels `"type": "external"`.

**Tech Stack:** Python 3.13, PySide6, pytest + pytest-qt (designer tests run with `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen`).

## Global Constraints

- `figspec/` package must stay Qt-free — `templates.py`, `snippet.py`, and all `figspec/layout/*` changes import nothing from PySide6.
- 兼容铁律: old figspec.json files (no `min_effective_dpi` in constraints, no `type`/`asset`/`asset_px` on panels, no asset fields in the sidecar tree) must parse unchanged. New keys are OMITTED when absent — a generated panel's dict must NOT contain `"type"`, `"asset"`, or `"asset_px"` keys at all.
- Constraints gains `min_effective_dpi: int = 300` (spec-mandated default 300).
- Effective DPI = `min(asset_px[0]/(w_mm/25.4), asset_px[1]/(h_mm/25.4))`; traffic light: green when `>= min_effective_dpi`, amber when `>= 0.67 * min_effective_dpi`, red below.
- Accepted asset extensions: png, jpg, jpeg, tif, tiff (case-insensitive).
- Saved specs store asset paths RELATIVE to the spec file's directory when possible; unsaved documents hold absolute paths; clipboard export (`Copy JSON`) keeps absolute paths.
- Templates: exactly 4 archetypes with keys `quantitative_grid`, `hero_left`, `image_plate`, `asymmetric`.
- `MIN_PANEL_MM = 5.0` and all batch-A guards stay untouched.
- Test commands: `.venv/bin/pytest tests/ -q` (figspec) and `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` (designer). All pre-existing tests must stay green (118 figspec / 108 designer at branch time).

## File Structure

- `figspec/layout/tree.py` — PanelNode `asset`/`asset_px` fields + sidecar (de)serialization (modify)
- `figspec/layout/ops.py` — `set_asset` pure op (modify)
- `figspec/layout/flatten.py` — `effective_dpi` helper (modify)
- `figspec/spec.py` — Constraints.min_effective_dpi; PanelSpec optional `type`/`asset`/`asset_px`; build/parse round-trip (modify)
- `figspec/document.py` — external export/restore, `relativize_assets`, `resolve_asset`, `to_json(base_dir=...)` (modify)
- `figspec/templates.py` — archetype library (create)
- `figspec/snippet.py` — matplotlib snippet generator (create)
- `designer/figspec_designer/ui/panel_widget.py` — drag-drop, thumbnail paint, missing-asset state (modify)
- `designer/figspec_designer/ui/canvas.py` — thumbnail loading, asset_dropped forwarding (modify)
- `designer/figspec_designer/ui/sidebar.py` — asset block + DPI light + Remove Asset + snippet button (modify)
- `designer/figspec_designer/ui/main_window.py` — wiring for all of the above + menus (modify)
- `designer/figspec_designer/ui/preview_export.py` — wireframe render (create)
- `designer/figspec_designer/ui/template_dialog.py` — New from Template dialog (create)
- `designer/figspec_designer/ui/theme.py` — QSS for DPI light, missing badge, on-image letter chip (modify)

---

### Task 1: figspec model layer for external panels

**Files:**
- Modify: `figspec/layout/tree.py`, `figspec/layout/ops.py`, `figspec/layout/flatten.py`, `figspec/spec.py`, `figspec/document.py`, `designer/figspec_designer/model/flatten.py` (shim re-export)
- Test: `tests/test_external_panels.py` (create)

**Interfaces:**
- Consumes: existing `PanelNode`, `to_dict`/`from_dict`, `build_spec`/`parse_spec`, `DesignerDocument`.
- Produces (later tasks rely on these EXACT signatures):
  - `PanelNode(asset: str | None = None, asset_px: tuple[int, int] | None = None)` (new optional fields)
  - `ops.set_asset(root: Node, panel_id: str, asset: str | None, asset_px: tuple[int, int] | None) -> Node`
  - `flatten.effective_dpi(asset_px: tuple[int, int], w_mm: float, h_mm: float) -> float`
  - `Constraints.min_effective_dpi: int = 300`
  - `document.relativize_assets(tree: Node, base_dir) -> Node`
  - `document.resolve_asset(asset: str, base_dir) -> Path | None`
  - `DesignerDocument.to_json(base_dir=None) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_external_panels.py`:

```python
import json
from pathlib import Path

import pytest

from figspec.document import DesignerDocument, relativize_assets, resolve_asset
from figspec.layout import ops
from figspec.layout.flatten import effective_dpi
from figspec.layout.tree import PanelNode, SplitNode, from_dict, iter_panels, to_dict
from figspec.spec import Constraints, parse_spec


def _two_panel_tree():
    return SplitNode("row", (0.5, 0.5),
                     (PanelNode(id="aaaa1111"), PanelNode(id="bbbb2222")))


def test_set_asset_and_clear():
    tree = _two_panel_tree()
    t2 = ops.set_asset(tree, "aaaa1111", "/abs/img.png", (2000, 1000))
    panel = next(p for p in iter_panels(t2) if p.id == "aaaa1111")
    assert panel.asset == "/abs/img.png"
    assert panel.asset_px == (2000, 1000)
    # other panel untouched
    other = next(p for p in iter_panels(t2) if p.id == "bbbb2222")
    assert other.asset is None
    # clear
    t3 = ops.set_asset(t2, "aaaa1111", None, None)
    panel3 = next(p for p in iter_panels(t3) if p.id == "aaaa1111")
    assert panel3.asset is None and panel3.asset_px is None


def test_set_asset_errors():
    tree = _two_panel_tree()
    with pytest.raises(KeyError):
        ops.set_asset(tree, "nope", "/a.png", (10, 10))
    with pytest.raises(ValueError):
        ops.set_asset(tree, "aaaa1111", "/a.png", None)
    with pytest.raises(ValueError):
        ops.set_asset(tree, "aaaa1111", None, (10, 10))


def test_sidecar_roundtrip_with_asset():
    tree = ops.set_asset(_two_panel_tree(), "aaaa1111", "img/a.png", (800, 600))
    d = to_dict(tree)
    back = from_dict(d)
    panel = next(p for p in iter_panels(back) if p.id == "aaaa1111")
    assert panel.asset == "img/a.png"
    assert panel.asset_px == (800, 600)  # tuple, not list
    # panel WITHOUT asset serializes with no asset keys
    plain = to_dict(tree)["children"][1]
    assert "asset" not in plain and "asset_px" not in plain


def test_effective_dpi():
    # 2000px over 89mm = 2000 / 3.504in = 570.8 dpi; height axis smaller
    dpi = effective_dpi((2000, 1000), 89.0, 89.0)
    assert dpi == pytest.approx(1000 / (89.0 / 25.4), rel=1e-6)
    with pytest.raises(ValueError):
        effective_dpi((100, 100), 0.0, 10.0)


def test_constraints_min_effective_dpi_default_and_compat():
    assert Constraints().min_effective_dpi == 300
    # old-style constraints dict (no key) still parses
    old = {"figspec_version": "0.1",
           "target": {"journal_preset": "custom", "figure_width_mm": 100.0,
                      "figure_height_mm": 60.0},
           "constraints": {"min_font_pt": 5.0, "max_font_pt": 8.0,
                           "min_linewidth_pt": 0.5},
           "panels": []}
    _t, c, _p, _d = parse_spec(old)
    assert c.min_effective_dpi == 300


def test_spec_export_external_vs_generated():
    doc = DesignerDocument.default()
    doc.tree = ops.set_asset(
        SplitNode("row", (0.5, 0.5),
                  (PanelNode(id="p1"), PanelNode(id="p2"))),
        "p1", "/abs/stem.tif", (4096, 4096))
    spec = doc.to_spec_dict()
    by_label = {p["label"]: p for p in spec["panels"]}
    ext = by_label["a"]
    assert ext["type"] == "external"
    assert ext["asset"] == "/abs/stem.tif"
    assert ext["asset_px"] == [4096, 4096]
    gen = by_label["b"]
    assert "type" not in gen and "asset" not in gen and "asset_px" not in gen
    # round-trip through parse (unknown-key tolerance for the new fields)
    _t, _c, panels, designer = parse_spec(spec)
    assert designer is not None
    # sidecar restore keeps asset
    doc2 = DesignerDocument.from_spec_dict(spec)
    p1 = next(p for p in iter_panels(doc2.tree) if p.id == "p1")
    assert p1.asset == "/abs/stem.tif" and p1.asset_px == (4096, 4096)


def test_relativize_and_resolve(tmp_path):
    img = tmp_path / "figs" / "a.png"
    img.parent.mkdir()
    img.write_bytes(b"fake")
    tree = ops.set_asset(_two_panel_tree(), "aaaa1111", str(img), (10, 10))
    rel = relativize_assets(tree, tmp_path)
    panel = next(p for p in iter_panels(rel) if p.id == "aaaa1111")
    assert panel.asset == "figs/a.png"
    # already-relative path passes through
    rel2 = relativize_assets(rel, tmp_path)
    assert next(p for p in iter_panels(rel2) if p.id == "aaaa1111").asset == "figs/a.png"
    # resolve: relative + base_dir -> absolute existing path
    assert resolve_asset("figs/a.png", tmp_path) == img
    # missing file / no base_dir -> None
    assert resolve_asset("figs/missing.png", tmp_path) is None
    assert resolve_asset("figs/a.png", None) is None
    assert resolve_asset(str(img), None) == img  # absolute needs no base


def test_to_json_relativizes_only_with_base_dir(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"fake")
    doc = DesignerDocument.default()
    doc.tree = ops.set_asset(PanelNode(id="p1"), "p1", str(img), (10, 10))
    # no base_dir: absolute path kept (clipboard path)
    data = json.loads(doc.to_json())
    assert data["panels"][0]["asset"] == str(img)
    # base_dir: relative in both panels list and sidecar
    data2 = json.loads(doc.to_json(base_dir=tmp_path))
    assert data2["panels"][0]["asset"] == "a.png"
    assert data2["designer"]["tree"]["asset"] == "a.png"
    # in-memory tree still absolute (to_json must not mutate)
    assert next(iter_panels(doc.tree)).asset == str(img)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_external_panels.py -q`
Expected: FAIL (ImportError / TypeError: unexpected keyword `asset`).

- [ ] **Step 3: Implement**

`figspec/layout/tree.py` — extend PanelNode and (de)serialization:

```python
@dataclass(frozen=True)
class PanelNode:
    id: str
    content_hint: str = ""
    aspect_lock: float | None = None
    asset: str | None = None
    asset_px: tuple[int, int] | None = None
```

In `to_dict`, after the `aspect_lock` line:

```python
        if node.asset is not None:
            d["asset"] = node.asset
            d["asset_px"] = list(node.asset_px)
```

In `from_dict`'s panel branch:

```python
        raw_px = d.get("asset_px")
        return PanelNode(id=d["id"], content_hint=d.get("content_hint", ""),
                         aspect_lock=d.get("aspect_lock"),
                         asset=d.get("asset"),
                         asset_px=tuple(int(v) for v in raw_px) if raw_px else None)
```

`figspec/layout/ops.py` — add (mirror the `set_content_hint` rebuild pattern; use `dataclasses.replace`, already imported or add it):

```python
def set_asset(root: Node, panel_id: str, asset: str | None,
              asset_px: tuple[int, int] | None) -> Node:
    """Attach (or, with None/None, detach) an external image asset."""
    if (asset is None) != (asset_px is None):
        raise ValueError("asset and asset_px must be set or cleared together")
    found = False

    def rec(node: Node) -> Node:
        nonlocal found
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                found = True
                px = tuple(int(v) for v in asset_px) if asset_px is not None else None
                return replace(node, asset=asset, asset_px=px)
            return node
        return replace(node, children=tuple(rec(c) for c in node.children))

    out = rec(root)
    if not found:
        raise KeyError(panel_id)
    return out
```

`figspec/layout/flatten.py` — add:

```python
def effective_dpi(asset_px: tuple[int, int], w_mm: float, h_mm: float) -> float:
    """Rendered DPI of an external asset in a panel: the SMALLER axis wins."""
    if w_mm <= 0 or h_mm <= 0:
        raise ValueError("panel dimensions must be positive")
    return min(asset_px[0] / (w_mm / 25.4), asset_px[1] / (h_mm / 25.4))
```

`designer/figspec_designer/model/flatten.py` — the shim imports names EXPLICITLY; extend its single import line to also re-export `effective_dpi`:

```python
from figspec.layout.flatten import (PanelRect, assign_labels, derive,  # noqa: F401
                                    effective_dpi, flatten)
```

`figspec/spec.py`:

```python
@dataclass
class Constraints:
    min_font_pt: float = 5.0
    max_font_pt: float = 8.0
    min_linewidth_pt: float = 0.5
    min_effective_dpi: int = 300


@dataclass
class PanelSpec:
    label: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    w_px: int
    h_px: int
    figsize_in: tuple[float, float]
    content_hint: str = ""
    type: str | None = None
    asset: str | None = None
    asset_px: tuple[int, int] | None = None
```

In `build_spec`, replace the panels list comprehension with a helper that omits the new keys when None (compat rule):

```python
def _panel_dict(p: PanelSpec) -> dict:
    d = {**asdict(p), "figsize_in": [p.figsize_in[0], p.figsize_in[1]]}
    for key in ("type", "asset", "asset_px"):
        if d[key] is None:
            del d[key]
    if "asset_px" in d:
        d["asset_px"] = list(d["asset_px"])
    return d
```

…and `"panels": [_panel_dict(p) for p in panels]`. In `parse_spec`, the panel construction becomes:

```python
        panels = [
            PanelSpec(**{
                **p,
                "figsize_in": tuple(p["figsize_in"]),
                **({"asset_px": tuple(p["asset_px"])} if p.get("asset_px") else {}),
            })
            for p in raw_panels
        ]
```

`figspec/document.py` — add imports (`import os`, `from pathlib import Path`, extend the tree import with `Node`), then:

```python
def relativize_assets(tree: Node, base_dir) -> Node:
    """Return a tree whose absolute asset paths are rewritten relative to
    base_dir (best effort — unconvertible paths pass through unchanged)."""
    out = tree
    for p in iter_panels(tree):
        if p.asset and Path(p.asset).is_absolute():
            try:
                rel = os.path.relpath(p.asset, base_dir)
            except ValueError:
                continue
            out = ops.set_asset(out, p.id, rel, p.asset_px)
    return out


def resolve_asset(asset: str, base_dir) -> Path | None:
    """Absolute or base_dir-relative asset path -> existing Path, else None."""
    p = Path(asset)
    if not p.is_absolute():
        if base_dir is None:
            return None
        p = Path(base_dir) / p
    return p if p.exists() else None
```

(`from figspec.layout import ops` at top.) In `DesignerDocument.to_spec_dict`, build an asset map next to `hints` and emit external fields:

```python
        assets = {p.id: (p.asset, p.asset_px) for p in iter_panels(self.tree)}
```

…and inside the loop, after computing `derive(...)`:

```python
            asset, asset_px = assets[rect.panel_id]
            panels.append(PanelSpec(
                label=labels[rect.panel_id],
                x_mm=rect.x_mm, y_mm=rect.y_mm, w_mm=rect.w_mm, h_mm=rect.h_mm,
                w_px=w_px, h_px=h_px, figsize_in=figsize,
                content_hint=hints[rect.panel_id],
                type="external" if asset else None,
                asset=asset, asset_px=asset_px,
            ))
```

Replace `to_json` with:

```python
    def to_json(self, base_dir=None) -> str:
        doc = self
        if base_dir is not None:
            doc = DesignerDocument(relativize_assets(self.tree, base_dir),
                                   self.target, self.constraints)
        return json.dumps(doc.to_spec_dict(), indent=2) + "\n"
```

- [ ] **Step 4: Run the new tests, then both full suites**

Run: `.venv/bin/pytest tests/test_external_panels.py -q` → all pass.
Run: `.venv/bin/pytest tests/ -q` → no regressions.
Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → no regressions (designer re-export shims pick the changes up automatically).

- [ ] **Step 5: Commit**

```bash
git add figspec/layout/tree.py figspec/layout/ops.py figspec/layout/flatten.py figspec/spec.py figspec/document.py tests/test_external_panels.py
git commit -m "feat: external-panel asset model, min_effective_dpi, path helpers"
```

---

### Task 2: Archetype template library (`figspec/templates.py`)

**Files:**
- Create: `figspec/templates.py`
- Test: `tests/test_templates.py`

**Interfaces:**
- Consumes: `figspec.layout.tree` (`SplitNode`, `new_panel`).
- Produces: `TEMPLATES: dict[str, Template]` with keys `quantitative_grid`, `hero_left`, `image_plate`, `asymmetric`; `Template` frozen dataclass with `key: str`, `title: str`, `description: str`, `build: Callable[[], Node]`. `build()` returns a FRESH tree each call (new uuids).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_templates.py`:

```python
from figspec.layout.flatten import assign_labels, flatten
from figspec.layout.tree import SplitNode, iter_panels
from figspec.templates import TEMPLATES


def _panel_count(key):
    return len(list(iter_panels(TEMPLATES[key].build())))


def test_registry_keys_and_metadata():
    assert set(TEMPLATES) == {"quantitative_grid", "hero_left",
                              "image_plate", "asymmetric"}
    for key, t in TEMPLATES.items():
        assert t.key == key
        assert t.title and t.description


def test_panel_counts():
    assert _panel_count("quantitative_grid") == 6
    assert _panel_count("hero_left") == 3
    assert _panel_count("image_plate") == 12
    assert _panel_count("asymmetric") == 4


def test_quantitative_grid_shape():
    tree = TEMPLATES["quantitative_grid"].build()
    assert isinstance(tree, SplitNode) and tree.orientation == "column"
    assert len(tree.children) == 2
    for row in tree.children:
        assert row.orientation == "row" and len(row.children) == 3
        assert all(abs(r - 1 / 3) < 1e-9 for r in row.ratios)


def test_hero_left_ratios():
    tree = TEMPLATES["hero_left"].build()
    assert tree.orientation == "row"
    assert tree.ratios == (0.6, 0.4)
    right = tree.children[1]
    assert right.orientation == "column" and len(right.children) == 2


def test_asymmetric_labels_read_top_then_bottom():
    tree = TEMPLATES["asymmetric"].build()
    rects = flatten(tree, 183.0, 100.0, 4.0)
    labels = set(assign_labels(rects).values())
    assert labels == {"a", "b", "c", "d"}


def test_build_returns_fresh_ids():
    t = TEMPLATES["hero_left"]
    ids1 = {p.id for p in iter_panels(t.build())}
    ids2 = {p.id for p in iter_panels(t.build())}
    assert ids1.isdisjoint(ids2)


def test_all_templates_respect_min_panel_on_default_page():
    # 183 x 100 mm, 4 mm gutter (nature_double defaults) — no panel < 5 mm
    for t in TEMPLATES.values():
        rects = flatten(t.build(), 183.0, 100.0, 4.0)
        assert all(r.w_mm >= 5.0 and r.h_mm >= 5.0 for r in rects), t.key
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_templates.py -q`
Expected: FAIL (ModuleNotFoundError: figspec.templates).

- [ ] **Step 3: Implement `figspec/templates.py`**

```python
"""Archetype layout templates, shared by the Designer and (later) the MCP
server. build() returns a fresh tree — new panel ids — on every call."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from figspec.layout.tree import Node, SplitNode, new_panel


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    description: str
    build: Callable[[], Node]


def _row(cols: int) -> SplitNode:
    return SplitNode("row", tuple(1 / cols for _ in range(cols)),
                     tuple(new_panel() for _ in range(cols)))


def _grid(rows: int, cols: int) -> Node:
    if rows == 1:
        return _row(cols)
    return SplitNode("column", tuple(1 / rows for _ in range(rows)),
                     tuple(_row(cols) for _ in range(rows)))


def _hero_left() -> Node:
    right = SplitNode("column", (0.5, 0.5), (new_panel(), new_panel()))
    return SplitNode("row", (0.6, 0.4), (new_panel(), right))


def _asymmetric() -> Node:
    return SplitNode("column", (0.5, 0.5), (new_panel(), _row(3)))


TEMPLATES: dict[str, Template] = {
    "quantitative_grid": Template(
        "quantitative_grid", "Quantitative grid",
        "2 × 3 equal grid — parameter sweeps, spectra series.",
        lambda: _grid(2, 3)),
    "hero_left": Template(
        "hero_left", "Hero left",
        "Full-height feature panel (60%) with two stacked companions.",
        _hero_left),
    "image_plate": Template(
        "image_plate", "Image plate",
        "3 × 4 micrograph plate — pair with a small gutter.",
        lambda: _grid(3, 4)),
    "asymmetric": Template(
        "asymmetric", "Asymmetric",
        "Full-width hero row over three equal panels.",
        _asymmetric),
}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_templates.py tests/ -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add figspec/templates.py tests/test_templates.py
git commit -m "feat: archetype template library (figspec.templates)"
```

---

### Task 3: matplotlib snippet (`figspec/snippet.py`) + Designer wiring

**Files:**
- Create: `figspec/snippet.py`
- Modify: `designer/figspec_designer/ui/main_window.py` (File menu + `copy_snippet`), `designer/figspec_designer/ui/sidebar.py` (button + signal)
- Test: `tests/test_snippet.py`, extend `designer/tests/test_batch_c_ui.py` (create)

**Interfaces:**
- Consumes: a spec dict as produced by `DesignerDocument.to_spec_dict()`.
- Produces: `generate_snippet(spec: dict, name: str = "Untitled") -> str`; Sidebar signal `snippet_copy_requested = Signal()`; `MainWindow.copy_snippet()`.

- [ ] **Step 1: Write the failing figspec test**

Create `tests/test_snippet.py`:

```python
from figspec.document import DesignerDocument
from figspec.snippet import generate_snippet


def test_snippet_content():
    doc = DesignerDocument.default()
    spec = doc.to_spec_dict()
    text = generate_snippet(spec, name="fig1.json")
    assert text.startswith("# Generated by FigSpec Designer from fig1.json")
    assert "regenerate after layout changes" in text
    assert "import matplotlib.pyplot as plt" in text
    assert '"font.size": 5.0' in text
    assert '"axes.linewidth": 0.5' in text
    assert '"pdf.fonttype": 42' in text
    assert '"svg.fonttype": "none"' in text
    # per-panel block for panel a (default doc = single full-page panel)
    p = spec["panels"][0]
    assert f"figsize=({p['figsize_in'][0]}, {p['figsize_in'][1]})" in text
    assert f"dpi={spec['target']['dpi']}" in text
    assert 'fig_a.savefig("panel_a.pdf")' in text
    assert f"# panel a: {p['w_mm']} × {p['h_mm']} mm" in text


def test_snippet_includes_content_hint():
    doc = DesignerDocument.default()
    spec = doc.to_spec_dict()
    spec["panels"][0]["content_hint"] = "STEM image"
    text = generate_snippet(spec)
    assert "STEM image" in text
    assert "from Untitled" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_snippet.py -q`
Expected: FAIL (ModuleNotFoundError: figspec.snippet).

- [ ] **Step 3: Implement `figspec/snippet.py`**

```python
"""figspec.json -> matplotlib starter code. Pure string generation, shared
by the Designer and (later) the MCP server. Interim tool: retires once M1
server-side rendering lands."""
from __future__ import annotations


def generate_snippet(spec: dict, name: str = "Untitled") -> str:
    c = spec["constraints"]
    dpi = spec["target"]["dpi"]
    font = c["min_font_pt"]
    lines = [
        f"# Generated by FigSpec Designer from {name} — "
        "regenerate after layout changes",
        "import matplotlib.pyplot as plt",
        "",
        "plt.rcParams.update({",
        f'    "font.size": {font},',
        f'    "axes.labelsize": {font},',
        f'    "xtick.labelsize": {font},',
        f'    "ytick.labelsize": {font},',
        f'    "legend.fontsize": {font},',
        f'    "axes.linewidth": {c["min_linewidth_pt"]},',
        '    "pdf.fonttype": 42,',
        '    "svg.fonttype": "none",',
        "})",
        "",
    ]
    for p in spec["panels"]:
        var = p["label"]
        hint = f" — {p['content_hint']}" if p.get("content_hint") else ""
        fw, fh = p["figsize_in"]
        lines += [
            f"# panel {var}: {p['w_mm']} × {p['h_mm']} mm{hint}",
            f"fig_{var}, ax_{var} = plt.subplots(figsize=({fw}, {fh}), dpi={dpi})",
            f'fig_{var}.savefig("panel_{var}.pdf")',
            "",
        ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run figspec tests**

Run: `.venv/bin/pytest tests/test_snippet.py tests/ -q` → pass.

- [ ] **Step 5: Wire the Designer**

`designer/figspec_designer/ui/sidebar.py`: add signal `snippet_copy_requested = Signal()` next to `placement_copy_requested`; add a button directly under `btn_copy_placement`:

```python
        self.btn_copy_snippet = QPushButton("Copy matplotlib Snippet")
        self.btn_copy_snippet.setObjectName("copySnippetButton")
        outer.addWidget(self.btn_copy_snippet)
```

…and connect it where `btn_copy_placement` is connected:

```python
        self.btn_copy_snippet.clicked.connect(self.snippet_copy_requested.emit)
```

`designer/figspec_designer/ui/main_window.py`: import `from figspec.snippet import generate_snippet`; in `_make_menus` after the "Copy Placement Table" action:

```python
        act(file_menu, "Copy matplotlib Snippet", None, self.copy_snippet)
```

…in `__init__` next to the other sidebar connections:

```python
        self.sidebar.snippet_copy_requested.connect(self.copy_snippet)
```

…and next to `copy_placement_table`:

```python
    def copy_snippet(self) -> None:
        name = self.current_path.name if self.current_path else "Untitled"
        QApplication.clipboard().setText(
            generate_snippet(self.doc.to_spec_dict(), name))
        self.statusBar().showMessage("matplotlib snippet copied", 3000)
```

- [ ] **Step 6: Write the failing UI test**

Create `designer/tests/test_batch_c_ui.py`. There is NO shared `main_window` fixture — tests construct `MainWindow()` directly (the conftest's two autouse fixtures already isolate QSettings and patch `confirm_discard` to True, so windows are safe to build and close):

```python
"""Batch C UI tests: snippet, assets, DPI light, preview export, templates."""
from PySide6.QtWidgets import QApplication

from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def test_copy_snippet_button(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.sidebar.btn_copy_snippet.click()
    text = QApplication.clipboard().text()
    assert text.startswith("# Generated by FigSpec Designer from Untitled")
    assert "plt.rcParams.update" in text
```

- [ ] **Step 7: Run designer tests**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → pass.

- [ ] **Step 8: Commit**

```bash
git add figspec/snippet.py tests/test_snippet.py designer/figspec_designer/ui/sidebar.py designer/figspec_designer/ui/main_window.py designer/tests/test_batch_c_ui.py
git commit -m "feat: matplotlib snippet export (figspec.snippet + Designer wiring)"
```

---

### Task 4: Drag-drop assets + canvas thumbnails + missing-asset state

**Files:**
- Modify: `designer/figspec_designer/ui/panel_widget.py`, `designer/figspec_designer/ui/canvas.py`, `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/theme.py`
- Test: extend `designer/tests/test_batch_c_ui.py`

**Interfaces:**
- Consumes: `ops.set_asset`, `document.resolve_asset` (Task 1).
- Produces:
  - `PanelWidget(..., thumb: QPixmap | None = None, asset_missing: bool = False)`; `PanelWidget.ASSET_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}`; signal `asset_dropped = Signal(str, str)` (panel_id, absolute file path)
  - `Canvas.asset_dropped = Signal(str, str)` (forwarded); `Canvas.set_document(doc, base_dir=None)`
  - `MainWindow._on_asset_dropped(panel_id, path)`, `MainWindow._asset_base_dir() -> Path | None`

- [ ] **Step 1: Write the failing tests**

Append to `designer/tests/test_batch_c_ui.py`:

```python
def _make_png(tmp_path, w=400, h=300, name="asset.png"):
    from PySide6.QtGui import QImage
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    path = tmp_path / name
    img.save(str(path))
    return path


def test_asset_drop_sets_external_state(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    panel = next(iter_panels(win.doc.tree))
    assert panel.asset == str(png)
    assert panel.asset_px == (400, 300)
    assert win.dirty
    # canvas widget shows a thumbnail
    widget = win.canvas.panel_widgets()[pid]
    assert widget._thumb is not None


def test_asset_drop_unreadable_file(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    bad = tmp_path / "not_an_image.png"
    bad.write_bytes(b"garbage")
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(bad))
    assert next(iter_panels(win.doc.tree)).asset is None  # rejected, no crash


def test_missing_asset_flagged(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    png.unlink()  # asset vanishes from disk
    win.refresh()
    widget = win.canvas.panel_widgets()[pid]
    assert widget.property("assetMissing") is True
    assert widget._thumb is None


def test_drag_enter_accepts_image_urls(qtbot, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    widget = win.canvas.panel_widgets()[pid]
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "x.TIF"))])
    assert widget._accepts_mime(mime)  # case-insensitive ext
    mime2 = QMimeData()
    mime2.setUrls([QUrl.fromLocalFile(str(tmp_path / "x.pdf"))])
    assert not widget._accepts_mime(mime2)
```

(`Canvas.panel_widgets()` is the existing id→widget accessor at `canvas.py:38` — a method returning a dict, not an attribute.)

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_c_ui.py -q`
Expected: FAIL (no `_on_asset_dropped`, no `_thumb`).

- [ ] **Step 3: Implement PanelWidget drag-drop + thumbnail**

`panel_widget.py`:

```python
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
```

Constructor gains kwargs `thumb: "QPixmap | None" = None, asset_missing: bool = False`; store `self._thumb = thumb`; call `self.setAcceptDrops(True)`; set `self.setProperty("assetMissing", bool(asset_missing))`. Add signal `asset_dropped = Signal(str, str)`. When `asset_missing`, reuse the aspect-badge pattern: add a small `QLabel("missing asset", self)` with `setObjectName("missingBadge")`, visible only when missing, placed in the top bar next to `aspect_badge`. When `thumb` is set, give the letter a legibility chip: `self.label_widget.setProperty("onImage", True)`.

```python
    @staticmethod
    def _accepts_mime(mime) -> bool:
        if not mime.hasUrls():
            return False
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return False
        from pathlib import Path
        return Path(urls[0].toLocalFile()).suffix.lower() in ASSET_EXTS

    def dragEnterEvent(self, event) -> None:
        if self._accepts_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self._accepts_mime(event.mimeData()):
            self.asset_dropped.emit(
                self.panel_id, event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)  # QSS card background/border first
        if self._thumb is None or self._thumb.isNull():
            return
        from PySide6.QtGui import QPainter
        scaled = self._thumb.scaled(self.size(), Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
        painter = QPainter(self)
        painter.drawPixmap((self.width() - scaled.width()) // 2,
                           (self.height() - scaled.height()) // 2, scaled)
        painter.end()
```

- [ ] **Step 4: Implement Canvas forwarding + thumbnail loading**

`canvas.py`: add `asset_dropped = Signal(str, str)` next to `panel_action` (canvas.py:20); add `self._asset_base = None` in `__init__`; `set_document` (canvas.py:44) becomes:

```python
    def set_document(self, doc: DesignerDocument, base_dir=None) -> None:
        self._doc = doc
        self._asset_base = base_dir
        self._rebuild()
```

The construction point is `_build_node`'s PanelNode branch (canvas.py:104-111) — it already receives the `PanelNode`, so no extra lookup is needed:

```python
        if isinstance(node, PanelNode):
            violated = self._aspect_violated(node, rects)
            thumb, missing = self._load_thumb(node)
            w = PanelWidget(node.id, labels.get(node.id, "?"),
                            aspect_violated=violated,
                            thumb=thumb, asset_missing=missing)
            w.action.connect(self.panel_action.emit)
            w.asset_dropped.connect(self.asset_dropped.emit)
            panel_shadow(w)
            self._panels[node.id] = w
            return w
```

Add (with `QPixmap` added to the `PySide6.QtGui` imports — canvas.py currently imports none):

```python
    _THUMB_MAX = 1200  # px cap: canvas preview never needs full-res assets

    def _load_thumb(self, node: PanelNode):
        """(QPixmap|None, missing: bool) for a panel's asset, if any."""
        if node.asset is None:
            return None, False
        from figspec.document import resolve_asset
        path = resolve_asset(node.asset, self._asset_base)
        if path is None:
            return None, True
        pix = QPixmap(str(path))
        if pix.isNull():
            return None, True
        if pix.width() > self._THUMB_MAX:
            pix = pix.scaledToWidth(self._THUMB_MAX, Qt.SmoothTransformation)
        return pix, False
```

(The existing `apply_selection`/`apply_swap_armed` re-application at the end of `_rebuild` (canvas.py:98-99) stays untouched.)

- [ ] **Step 5: Implement MainWindow wiring**

`main_window.py` `__init__`: `self.canvas.asset_dropped.connect(self._on_asset_dropped)`. In `refresh()`:

```python
        self.canvas.set_document(self.doc, base_dir=self._asset_base_dir())
```

Add:

```python
    def _asset_base_dir(self) -> Path | None:
        return self.current_path.parent if self.current_path else None

    def _on_asset_dropped(self, panel_id: str, file_path: str) -> None:
        from PySide6.QtGui import QImageReader
        size = QImageReader(file_path).size()
        if not size.isValid():
            self.statusBar().showMessage("Cannot read image file", 3000)
            return
        try:
            self._push_tree(ops.set_asset(self.doc.tree, panel_id, file_path,
                                          (size.width(), size.height())))
        except KeyError:
            self.statusBar().showMessage("Panel no longer exists", 3000)
```

`save_json` must relativize (spec rule):

```python
    def save_json(self, path) -> None:
        Path(path).write_text(self.doc.to_json(base_dir=Path(path).parent))
```

`export_json_text` (clipboard) stays `self.doc.to_json()` — absolute paths.

- [ ] **Step 6: Theme additions**

`theme.py` QSS block (near the existing `PanelWidget[...]` rules):

```css
QLabel#missingBadge {{
    background: {AMBER_BG}; color: {AMBER_INK}; border-radius: 4px;
    padding: 1px 6px; font-size: 10px;
}}
PanelWidget[assetMissing="true"] {{ border: 1px solid {AMBER_BG}; }}
QLabel#panelLetter[onImage="true"] {{
    background: rgba(255, 255, 255, 0.75); border-radius: 6px;
}}
```

(Tokens `AMBER_BG`/`AMBER_INK` exist at `theme.py:16-17`; the QSS is one f-string, so literal braces are doubled — match the existing `aspectBadge` rule at `theme.py:37`.)

- [ ] **Step 7: Run designer tests + smoke**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → all pass.
Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` → clean exit.

- [ ] **Step 8: Commit**

```bash
git add designer/figspec_designer/ui/panel_widget.py designer/figspec_designer/ui/canvas.py designer/figspec_designer/ui/main_window.py designer/figspec_designer/ui/theme.py designer/tests/test_batch_c_ui.py
git commit -m "feat: drag-drop external assets with canvas thumbnails"
```

---

### Task 5: Sidebar asset block + effective-DPI traffic light

**Files:**
- Modify: `designer/figspec_designer/ui/sidebar.py`, `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/theme.py`
- Test: extend `designer/tests/test_batch_c_ui.py`

**Interfaces:**
- Consumes: `flatten.effective_dpi`, `Constraints.min_effective_dpi` (Task 1); panel asset state via `MainWindow._refresh_sidebar`.
- Produces: Sidebar signal `asset_remove_requested = Signal(str)`; `Sidebar.show_panel(..., asset_name: str | None = None, asset_px: tuple[int, int] | None = None, eff_dpi: float | None = None, dpi_level: str = "ok", asset_missing: bool = False)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sidebar_asset_block_and_dpi_light(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path, 400, 300)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win.do_action("select", pid)
    sb = win.sidebar
    assert sb.asset_box.isVisibleTo(sb)  # offscreen-safe visibility check
    assert sb.lbl_asset_name.text() == "asset.png"
    assert sb.lbl_asset_px.text() == "400 × 300 px"
    # default panel 183x100mm: eff dpi = min(400/7.2in, 300/3.94in) ~ 55 -> red
    assert sb.lbl_asset_dpi.property("level") == "bad"
    assert "dpi" in sb.lbl_asset_dpi.text()


def test_sidebar_remove_asset(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(png))
    win.do_action("select", pid)
    win.sidebar.btn_remove_asset.click()
    assert next(iter_panels(win.doc.tree)).asset is None
    win.do_action("select", pid)
    assert not win.sidebar.asset_box.isVisibleTo(win.sidebar)


def test_dpi_levels(qtbot, tmp_path):
    # a big asset on the default 183x100 panel: 8000x5000 -> ~1270 dpi -> ok
    win = MainWindow()
    qtbot.addWidget(win)
    png = _make_png(tmp_path, 80, 50, "big.png")  # tiny file, fake px via ops
    pid = next(iter_panels(win.doc.tree)).id
    from figspec.layout import ops
    win._push_tree(ops.set_asset(win.doc.tree, pid, str(png), (8000, 5000)))
    win.do_action("select", pid)
    assert win.sidebar.lbl_asset_dpi.property("level") == "ok"
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_c_ui.py -q`
Expected: FAIL (no `asset_box`).

- [ ] **Step 3: Implement the sidebar block**

`sidebar.py` — after the aspect-lock/buttons section, before the stretch:

```python
        # ---- external asset block (hidden unless the panel has one) ----
        self.asset_box = QWidget()
        self.asset_box.setObjectName("assetBox")
        asset_layout = QVBoxLayout(self.asset_box)
        asset_layout.setContentsMargins(0, 8, 0, 0)
        asset_layout.setSpacing(6)
        asset_header = QLabel("Asset")
        asset_header.setObjectName("sectionHeader")
        asset_header.setFont(smallcaps_font())
        asset_layout.addWidget(asset_header)
        asset_grid = QGridLayout()
        asset_grid.setSpacing(8)
        self.lbl_asset_name = QLabel("—")
        self.lbl_asset_px = QLabel("—")
        self.lbl_asset_dpi = QLabel("—")
        self.lbl_asset_dpi.setObjectName("dpiValue")
        for row, (text, widget) in enumerate([("File", self.lbl_asset_name),
                                              ("Pixels", self.lbl_asset_px),
                                              ("Effective", self.lbl_asset_dpi)]):
            left = QLabel(text)
            left.setObjectName("fieldLabel")
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            asset_grid.addWidget(left, row, 0)
            asset_grid.addWidget(widget, row, 1)
        asset_layout.addLayout(asset_grid)
        self.btn_remove_asset = QPushButton("Remove Asset")
        self.btn_remove_asset.setObjectName("removeAssetButton")
        asset_layout.addWidget(self.btn_remove_asset)
        outer.addWidget(self.asset_box)
        self.asset_box.setVisible(False)
```

Signal + connection (`asset_remove_requested = Signal(str)`):

```python
        self.btn_remove_asset.clicked.connect(self._emit_asset_remove)
```

```python
    def _emit_asset_remove(self) -> None:
        if self._panel_id is not None:
            self.asset_remove_requested.emit(self._panel_id)
```

`show_panel` gains the new keyword args from the Interfaces block; at its end:

```python
        from figspec_designer.ui.theme import repolish
        if asset_name is None:
            self.asset_box.setVisible(False)
        else:
            self.asset_box.setVisible(True)
            self.lbl_asset_name.setText(
                asset_name + (" (missing)" if asset_missing else ""))
            self.lbl_asset_px.setText(
                f"{asset_px[0]} × {asset_px[1]} px" if asset_px else "—")
            self.lbl_asset_dpi.setText(
                f"{eff_dpi:.0f} dpi" if eff_dpi is not None else "—")
            self.lbl_asset_dpi.setProperty(
                "level", "bad" if asset_missing else dpi_level)
            repolish(self.lbl_asset_dpi)
```

`clear()` additionally hides the box: `self.asset_box.setVisible(False)`.

- [ ] **Step 4: MainWindow feeds the block**

`_refresh_sidebar` — before the `show_panel` call:

```python
        from pathlib import Path as _P
        from figspec_designer.model.flatten import effective_dpi
        from figspec.document import resolve_asset
        asset_name = asset_px = eff = None
        dpi_level, missing = "ok", False
        if panel.asset is not None:
            asset_name = _P(panel.asset).name
            asset_px = panel.asset_px
            eff = effective_dpi(panel.asset_px, rect.w_mm, rect.h_mm)
            floor = self.doc.constraints.min_effective_dpi
            dpi_level = ("ok" if eff >= floor
                         else "warn" if eff >= 0.67 * floor else "bad")
            missing = resolve_asset(panel.asset, self._asset_base_dir()) is None
```

…then extend the call: `..., asset_name=asset_name, asset_px=asset_px, eff_dpi=eff, dpi_level=dpi_level, asset_missing=missing)`. (Check that `figspec_designer.model.flatten` re-exports `effective_dpi` — the model shims are one-line re-exports; if the shim uses `from figspec.layout.flatten import *` it comes free, otherwise add it.) Wire removal in `__init__`:

```python
        self.sidebar.asset_remove_requested.connect(self._on_asset_removed)
```

```python
    def _on_asset_removed(self, panel_id: str) -> None:
        try:
            self._push_tree(ops.set_asset(self.doc.tree, panel_id, None, None))
        except KeyError:
            pass
```

- [ ] **Step 5: Theme — DPI light colors**

`theme.py`: add tokens `DPI_OK = "#3D7A44"`, `DPI_WARN = "#B07D2A"`, `DPI_BAD = "#B04A3A"` (follow the file's palette naming style) and QSS:

```css
QLabel#dpiValue[level="ok"] {{ color: {DPI_OK}; font-weight: 600; }}
QLabel#dpiValue[level="warn"] {{ color: {DPI_WARN}; font-weight: 600; }}
QLabel#dpiValue[level="bad"] {{ color: {DPI_BAD}; font-weight: 600; }}
```

- [ ] **Step 6: Run designer tests**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 7: Commit**

```bash
git add designer/figspec_designer/ui/sidebar.py designer/figspec_designer/ui/main_window.py designer/figspec_designer/ui/theme.py designer/tests/test_batch_c_ui.py
git commit -m "feat: sidebar asset block with effective-DPI traffic light"
```

---

### Task 6: Wireframe layout preview export (`ui/preview_export.py`)

**Files:**
- Create: `designer/figspec_designer/ui/preview_export.py`
- Modify: `designer/figspec_designer/ui/main_window.py` (File menu)
- Test: extend `designer/tests/test_batch_c_ui.py`

**Interfaces:**
- Consumes: `flatten`, `assign_labels`, `DesignerDocument`.
- Produces (Task 7 reuses the first):
  - `render_layout_image(tree, target, *, scale: int = 2) -> QImage`
  - `render_layout_png(doc, path, scale: int = 2) -> None`
  - `MainWindow.export_layout_preview()`

- [ ] **Step 1: Write the failing tests**

```python
def test_render_layout_png(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("split_right", pid)
    out = tmp_path / "layout.png"
    from figspec_designer.ui.preview_export import render_layout_png
    render_layout_png(win.doc, out)
    assert out.exists() and out.stat().st_size > 0
    from PySide6.QtGui import QImage
    img = QImage(str(out))
    # 183mm page at 4 px/mm * scale 2 = 1464 px wide, page + footer tall
    assert img.width() == round(183.0 * 8)
    assert img.height() > round(100.0 * 8)


def test_render_layout_image_standalone_tree(qtbot):
    from figspec.templates import TEMPLATES
    from figspec.spec import Target
    from figspec_designer.ui.preview_export import render_layout_image
    img = render_layout_image(TEMPLATES["hero_left"].build(),
                              Target("nature_double", 183.0, 100.0),
                              scale=1)
    assert not img.isNull()
    assert img.width() == round(183.0 * 4)
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_c_ui.py -q`
Expected: FAIL (ModuleNotFoundError: preview_export).

- [ ] **Step 3: Implement `preview_export.py`**

```python
"""Clean wireframe rendering of a layout — deliberately NOT canvas.grab():
no selection borders, hover buttons, or armed-state cues in the output."""
from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from figspec_designer.model.flatten import assign_labels, flatten

PX_PER_MM = 4.0
_PAGE = QColor("#FFFFFF")
_FRAME = QColor("#B9B6B0")
_TEXT = QColor("#6E6B66")
_LETTER = QColor("#3A3835")


def render_layout_image(tree, target, *, scale: int = 2) -> QImage:
    ppm = PX_PER_MM * scale
    w = round(target.figure_width_mm * ppm)
    h = round(target.figure_height_mm * ppm)
    footer = round(8 * ppm)
    img = QImage(w, h + footer, QImage.Format_RGB32)
    img.fill(_PAGE)
    rects = flatten(tree, target.figure_width_mm, target.figure_height_mm,
                    target.gutter_mm)
    labels = assign_labels(rects)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    letter_font = QFont()
    letter_font.setBold(True)
    letter_font.setPixelSize(max(10, round(3.2 * ppm)))
    small_font = QFont()
    small_font.setPixelSize(max(8, round(2.2 * ppm)))

    for r in rects:
        rect = QRectF(r.x_mm * ppm, r.y_mm * ppm, r.w_mm * ppm, r.h_mm * ppm)
        painter.setPen(QPen(_FRAME, max(1.0, 0.35 * scale)))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)
        painter.setPen(_LETTER)
        painter.setFont(letter_font)
        painter.drawText(rect.adjusted(1.2 * ppm, 0.6 * ppm, 0, 0),
                         Qt.AlignLeft | Qt.AlignTop, labels[r.panel_id])
        painter.setPen(_TEXT)
        painter.setFont(small_font)
        painter.drawText(rect, Qt.AlignCenter,
                         f"{r.w_mm:.1f} × {r.h_mm:.1f} mm")

    painter.setPen(_TEXT)
    painter.setFont(small_font)
    painter.drawText(QRectF(0, h, w, footer), Qt.AlignCenter,
                     f"{target.journal_preset} · "
                     f"{target.figure_width_mm:g} × {target.figure_height_mm:g} mm"
                     f" · {target.dpi} dpi · gutter {target.gutter_mm:g} mm")
    painter.end()
    return img


def render_layout_png(doc, path, scale: int = 2) -> None:
    render_layout_image(doc.tree, doc.target, scale=scale).save(str(path))
```

(Check the `figspec_designer.model.flatten` shim exports `assign_labels`/`flatten`; import from `figspec.layout.flatten` directly if not.)

- [ ] **Step 4: MainWindow menu wiring**

`_make_menus`, after "Copy matplotlib Snippet":

```python
        act(file_menu, "Export Layout Preview…", None, self.export_layout_preview)
```

```python
    def export_layout_preview(self) -> None:
        from figspec_designer.ui.preview_export import render_layout_png
        path, _ = QFileDialog.getSaveFileName(self, "Export layout preview",
                                              "layout.png", "PNG image (*.png)")
        if not path:
            return
        render_layout_png(self.doc, path)
        self.statusBar().showMessage(f"Layout preview exported to {path}", 3000)
```

- [ ] **Step 5: Run designer tests**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add designer/figspec_designer/ui/preview_export.py designer/figspec_designer/ui/main_window.py designer/tests/test_batch_c_ui.py
git commit -m "feat: wireframe layout preview export (PNG)"
```

---

### Task 7: New from Template dialog

**Files:**
- Create: `designer/figspec_designer/ui/template_dialog.py`
- Modify: `designer/figspec_designer/ui/main_window.py`
- Test: extend `designer/tests/test_batch_c_ui.py`

**Interfaces:**
- Consumes: `figspec.templates.TEMPLATES` (Task 2), `render_layout_image` (Task 6), `MainWindow.confirm_discard` (batch A).
- Produces: `TemplateDialog(target, parent=None)` with `.selected_key() -> str | None`; `MainWindow.new_from_template()`.

- [ ] **Step 1: Write the failing tests**

```python
def test_template_dialog_lists_all(qtbot):
    from figspec_designer.ui.template_dialog import TemplateDialog
    win = MainWindow()
    qtbot.addWidget(win)
    dlg = TemplateDialog(win.doc.target)
    qtbot.addWidget(dlg)
    assert dlg.list_widget.count() == 4
    dlg.list_widget.setCurrentRow(0)
    assert dlg.selected_key() in {"quantitative_grid", "hero_left",
                                  "image_plate", "asymmetric"}
    assert dlg.preview_label.pixmap() is not None


def test_new_from_template_builds_doc(qtbot, monkeypatch):
    # conftest's autouse fixture already patches confirm_discard -> True
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_pick_template", lambda: "quantitative_grid")
    win.new_from_template()
    assert len(list(iter_panels(win.doc.tree))) == 6
    assert win.current_path is None
    assert win.dirty is False
    assert win.windowTitle().startswith("Untitled")


def test_new_from_template_respects_cancel(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    before = win.doc.tree
    monkeypatch.setattr(win, "_pick_template", lambda: None)
    win.new_from_template()
    assert win.doc.tree is before
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_c_ui.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `template_dialog.py`**

```python
"""File > New from Template… — list left, wireframe preview right."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QVBoxLayout)

from figspec.templates import TEMPLATES
from figspec_designer.ui.preview_export import render_layout_image


class TemplateDialog(QDialog):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New from Template")
        self._target = target

        self.list_widget = QListWidget()
        for key, t in TEMPLATES.items():
            item = QListWidgetItem(t.title)
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(260, 200)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.preview_label)
        right.addWidget(self.desc_label)
        right.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        top = QHBoxLayout()
        top.addWidget(self.list_widget, stretch=1)
        top.addLayout(right)
        outer = QVBoxLayout(self)
        outer.addLayout(top)
        outer.addWidget(buttons)

        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())

    def selected_key(self) -> str | None:
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _update_preview(self, *_args) -> None:
        key = self.selected_key()
        if key is None:
            return
        t = TEMPLATES[key]
        img = render_layout_image(t.build(), self._target, scale=1)
        pix = QPixmap.fromImage(img).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio,
            Qt.SmoothTransformation)
        self.preview_label.setPixmap(pix)
        self.desc_label.setText(t.description)
```

- [ ] **Step 4: MainWindow wiring**

Imports: `from figspec.templates import TEMPLATES`, `from figspec_designer.model.history import History` (already there). `_make_menus` — FIRST entry of the File menu, above "Open…":

```python
        act(file_menu, "New from Template…", "Ctrl+N", self.new_from_template)
```

```python
    def _pick_template(self) -> str | None:
        """Factored out so tests can monkeypatch past the modal dialog."""
        from figspec_designer.ui.template_dialog import TemplateDialog
        dlg = TemplateDialog(self.doc.target, self)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.selected_key()

    def new_from_template(self) -> None:
        if not self.confirm_discard():
            return
        key = self._pick_template()
        if key is None:
            return
        self.doc = DesignerDocument(tree=TEMPLATES[key].build(),
                                    target=self.doc.target,
                                    constraints=self.doc.constraints)
        self.history = History(self.doc.tree)
        self.selected_panel_id = None
        self._cancel_swap_pending(notify=False)
        self.current_path = None
        self.refresh()
        # A template you just picked is 2 clicks to recreate — treat like a
        # fresh window, not unsaved user work (no close-nag until edited).
        self.dirty = False
        self._refresh_title()
```

(`QDialog` needs importing in main_window.py.)

- [ ] **Step 5: Run all designer tests + smoke**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → all pass.
Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` → clean.

- [ ] **Step 6: Commit**

```bash
git add designer/figspec_designer/ui/template_dialog.py designer/figspec_designer/ui/main_window.py designer/tests/test_batch_c_ui.py
git commit -m "feat: New from Template dialog with wireframe previews"
```

---

## Verification (whole batch)

1. `.venv/bin/pytest tests/ -q` — figspec suite green (118 + new).
2. `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` — designer suite green (108 + new).
3. `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` — clean.
4. Controller visual check (offscreen screenshot): open a template, drop a PNG onto a panel, confirm thumbnail + sidebar DPI light; export a layout preview PNG and view it.
