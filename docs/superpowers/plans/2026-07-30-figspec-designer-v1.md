# FigSpec Designer V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship FigSpec Designer — a PySide6 macOS app where the user splits a journal-width canvas into panels with live mm feedback and exports figspec.json.

**Architecture:** A pure-Python layout tree (`designer/figspec_designer/model/`, zero Qt imports) is the single source of truth; all tree operations are pure functions returning new trees, so undo is a snapshot stack. The Qt layer (`ui/`) renders the tree as nested QSplitters with custom gutter handles and forwards user actions back as model operations. Export flattens the tree to absolute top-left-origin mm rectangles via the shared `figspec/spec.py` schema helpers; a `designer.tree` sidecar in the JSON enables round-trip editing.

**Tech Stack:** Python ≥3.10 (build pipeline pins 3.11), PySide6 ≥6.7, pytest + pytest-qt (offscreen), PyInstaller + codesign/notarytool/create-dmg for packaging.

## Global Constraints

- Monorepo: designer code under `designer/`, shared schema helpers in `figspec/spec.py` (the existing `figspec` package). `model/` must not import Qt; `ui/` must not do geometry math (always call model/flatten).
- Coordinate convention (normative, documented in figspec/spec.py): panel x_mm/y_mm top-left origin, y down, millimetres.
- Split-tree semantics: `SplitNode.orientation` ∈ {"row" (children side by side), "column" (stacked)}; `ratios` normalized, same length as `children`. Gutters have physical width `gutter_mm`; flatten avail = size − (n−1)×gutter.
- Defaults: height 100 mm, dpi 600, gutter 4 mm, constraints min_font 5 / max_font 8 / min_linewidth 0.5. Presets: nature_single 89, nature_double 183, acs_single 82.5, acs_double 178, aps_single 86, aps_double 172.
- Labels: reading order sort key `(round(y_mm, 1), x_mm)`; a…z then aa, ab….
- Derived values: `w_px = round(w_mm/25.4*dpi)`; `figsize_in` rounded to 3 decimals; rect mm rounded to 3 decimals.
- Snap: divider release snaps sizes to 0.5 mm grid (⌥ held disables); snapping never produces a child below 0.5 mm.
- Shortcuts: Split Right ⌘D, Split Down ⇧⌘D, Delete Panel ⌘⌫, Undo ⌘Z, Redo ⇧⌘Z, Save ⌘S, Open ⌘O. English UI.
- App identity: name "FigSpec Designer", bundle id `com.github.sebdeng.figspec-designer`, version single-sourced from `designer/figspec_designer/__init__.py` (`0.1.0.dev0`), arm64 only.
- All test commands from repo root `/Users/dengyusong/Desktop/FigSpec`; UI tests set `QT_QPA_PLATFORM=offscreen` (designer/tests/conftest.py does this). figspec-package tests: `.venv/bin/pytest tests/ -q`; designer tests: `.venv/bin/pytest designer/tests -q`.
- The venv's `figspec` install is NON-editable — any task that edits `figspec/` must run `.venv/bin/pip install --no-deps --force-reinstall .` before testing.
- TDD everywhere: failing test first (RED), implement, GREEN, commit.

---

### Task 1: Designer scaffolding

**Files:**
- Create: `designer/pyproject.toml`, `designer/figspec_designer/__init__.py`, `designer/figspec_designer/__main__.py`, `designer/figspec_designer/model/__init__.py` (empty), `designer/figspec_designer/ui/__init__.py` (empty), `designer/conftest.py`, `designer/tests/conftest.py`, `designer/tests/test_scaffold.py`

**Interfaces:**
- Produces: importable `figspec_designer` package with `__version__ = "0.1.0.dev0"`; PySide6 + pytest-qt installed in `.venv`; `python -m figspec_designer` entry (calls `app.main`, which exists from Task 11 — until then `__main__.py` import fails at runtime only, not collection).

- [ ] **Step 1: Write files**

`designer/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "figspec-designer"
dynamic = ["version"]
description = "Visual multi-panel figure layout designer exporting figspec.json"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = ["PySide6>=6.7", "figspec"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt>=4.4"]

[project.gui-scripts]
figspec-designer = "figspec_designer.app:main"

[tool.hatch.version]
path = "figspec_designer/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["figspec_designer"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`designer/figspec_designer/__init__.py`:
```python
__version__ = "0.1.0.dev0"
```

`designer/figspec_designer/__main__.py`:
```python
from figspec_designer.app import main

raise SystemExit(main())
```

`designer/conftest.py` (import-path safety net; the known UF_HIDDEN .pth issue makes editable installs unreliable on this machine):
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

`designer/tests/conftest.py`:
```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

`designer/tests/test_scaffold.py`:
```python
import figspec_designer


def test_version():
    assert figspec_designer.__version__ == "0.1.0.dev0"


def test_qt_importable():
    from PySide6.QtWidgets import QApplication  # noqa: F401
```

- [ ] **Step 2: Install deps and run**

Run: `.venv/bin/pip install -q "PySide6>=6.7" "pytest-qt>=4.4" && .venv/bin/pytest designer/tests -q`
Expected: 2 passed. (No editable install of figspec-designer needed — `designer/conftest.py` puts the package on sys.path for tests.)

- [ ] **Step 3: Verify figspec suite untouched**

Run: `.venv/bin/pytest tests/ -q` — Expected: 74 passed.

- [ ] **Step 4: Commit** — `git add designer/ && git commit -m "chore: scaffold figspec-designer package"`

---

### Task 2: Shared schema helpers (`figspec/spec.py`)

**Files:**
- Create: `figspec/spec.py`
- Test: `tests/test_spec.py` (figspec package suite)

**Interfaces:**
- Produces (consumed by Task 7's document layer and future CLI --spec mode):
  - `FIGSPEC_VERSION = "0.1"`; `class SpecError(ValueError)`
  - `@dataclass Target(journal_preset: str, figure_width_mm: float, figure_height_mm: float, dpi: int = 600, gutter_mm: float = 4.0)`
  - `@dataclass Constraints(min_font_pt: float = 5.0, max_font_pt: float = 8.0, min_linewidth_pt: float = 0.5)`
  - `@dataclass PanelSpec(label: str, x_mm: float, y_mm: float, w_mm: float, h_mm: float, w_px: int, h_px: int, figsize_in: tuple[float, float], content_hint: str = "")`
  - `build_spec(target, constraints, panels, designer: dict | None = None) -> dict`
  - `parse_spec(data: dict) -> tuple[Target, Constraints, list[PanelSpec], dict | None]` — raises SpecError on missing keys/bad types.

- [ ] **Step 1: Write the failing test** (`tests/test_spec.py`)

```python
import pytest
from figspec.spec import (FIGSPEC_VERSION, Constraints, PanelSpec, SpecError,
                          Target, build_spec, parse_spec)

T = Target("nature_double", 183.0, 100.0)
C = Constraints()
P = PanelSpec("a", 0.0, 0.0, 89.5, 50.0, 2114, 1181, (3.524, 1.969), "STEM image")


def test_build_shape():
    d = build_spec(T, C, [P], designer={"tree": {"type": "panel", "id": "x"}})
    assert d["figspec_version"] == FIGSPEC_VERSION
    assert d["target"]["figure_width_mm"] == 183.0
    assert d["constraints"]["min_font_pt"] == 5.0
    assert d["panels"][0] == {
        "label": "a", "x_mm": 0.0, "y_mm": 0.0, "w_mm": 89.5, "h_mm": 50.0,
        "w_px": 2114, "h_px": 1181, "figsize_in": [3.524, 1.969],
        "content_hint": "STEM image",
    }
    assert d["designer"]["tree"]["id"] == "x"


def test_build_omits_designer_when_none():
    assert "designer" not in build_spec(T, C, [P])


def test_roundtrip():
    d = build_spec(T, C, [P], designer={"tree": {"k": 1}})
    t2, c2, panels2, designer2 = parse_spec(d)
    assert t2 == T and c2 == C and panels2 == [P]
    assert designer2 == {"tree": {"k": 1}}


def test_parse_errors():
    with pytest.raises(SpecError):
        parse_spec({})
    with pytest.raises(SpecError):
        parse_spec({"figspec_version": "0.1", "target": {}, "constraints": {},
                    "panels": "not-a-list"})
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_spec.py -q` → ModuleNotFoundError (figspec.spec — note: runs against the INSTALLED figspec, so failure is expected even after creating the file until reinstall).

- [ ] **Step 3: Implement** (`figspec/spec.py`)

```python
"""figspec.json schema helpers shared by the Designer and the CLI.

Coordinate convention (normative): panel ``x_mm``/``y_mm`` use a TOP-LEFT
origin with y increasing DOWNWARD, in millimetres. Consumers working in PDF
coordinates (bottom-left origin, y up) must convert internally.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

FIGSPEC_VERSION = "0.1"


class SpecError(ValueError):
    """Raised when a figspec.json document is malformed."""


@dataclass
class Target:
    journal_preset: str
    figure_width_mm: float
    figure_height_mm: float
    dpi: int = 600
    gutter_mm: float = 4.0


@dataclass
class Constraints:
    min_font_pt: float = 5.0
    max_font_pt: float = 8.0
    min_linewidth_pt: float = 0.5


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


def build_spec(target: Target, constraints: Constraints,
               panels: list[PanelSpec], designer: dict | None = None) -> dict:
    doc = {
        "figspec_version": FIGSPEC_VERSION,
        "target": asdict(target),
        "constraints": asdict(constraints),
        "panels": [
            {**asdict(p), "figsize_in": [p.figsize_in[0], p.figsize_in[1]]}
            for p in panels
        ],
    }
    if designer is not None:
        doc["designer"] = designer
    return doc


def _require(data: dict, key: str):
    if key not in data:
        raise SpecError(f"missing key: {key}")
    return data[key]


def parse_spec(data: dict):
    _require(data, "figspec_version")
    try:
        target = Target(**_require(data, "target"))
        constraints = Constraints(**_require(data, "constraints"))
        raw_panels = _require(data, "panels")
        if not isinstance(raw_panels, list):
            raise SpecError("panels must be a list")
        panels = [
            PanelSpec(**{**p, "figsize_in": tuple(p["figsize_in"])})
            for p in raw_panels
        ]
    except SpecError:
        raise
    except (TypeError, KeyError, ValueError) as e:
        raise SpecError(f"malformed spec: {e}") from e
    return target, constraints, panels, data.get("designer")
```

- [ ] **Step 4: Reinstall and verify pass**

Run: `.venv/bin/pip install -q --no-deps --force-reinstall . && .venv/bin/pytest tests/ -q`
Expected: 78 passed (74 + 4).

- [ ] **Step 5: Commit** — `git add figspec/spec.py tests/test_spec.py && git commit -m "feat: shared figspec.json schema helpers"`

---

### Task 3: Layout tree nodes (`model/tree.py`)

**Files:**
- Create: `designer/figspec_designer/model/tree.py`
- Test: `designer/tests/test_tree.py`

**Interfaces:**
- Produces: frozen dataclasses `PanelNode(id: str, content_hint: str = "")`, `SplitNode(orientation: str, ratios: tuple[float, ...], children: tuple[Node, ...])` (validates orientation ∈ row/column and len match); type alias `Node`; `new_panel() -> PanelNode` (uuid4 hex[:8]); `iter_panels(node) -> Iterator[PanelNode]`; `to_dict(node) -> dict`; `from_dict(d) -> Node` (ValueError on unknown type).

- [ ] **Step 1: Write the failing test** (`designer/tests/test_tree.py`)

```python
import pytest
from figspec_designer.model.tree import (PanelNode, SplitNode, from_dict,
                                         iter_panels, new_panel, to_dict)


def test_new_panel_ids_unique():
    a, b = new_panel(), new_panel()
    assert a.id != b.id and len(a.id) == 8


def test_split_validation():
    p = PanelNode("p1")
    with pytest.raises(ValueError):
        SplitNode("diagonal", (1.0,), (p,))
    with pytest.raises(ValueError):
        SplitNode("row", (0.5,), (p, PanelNode("p2")))


def test_iter_panels_order():
    tree = SplitNode("row", (0.5, 0.5),
                     (PanelNode("a"),
                      SplitNode("column", (0.5, 0.5),
                                (PanelNode("b"), PanelNode("c")))))
    assert [p.id for p in iter_panels(tree)] == ["a", "b", "c"]


def test_dict_roundtrip():
    tree = SplitNode("row", (0.6, 0.4),
                     (PanelNode("a", content_hint="hero"), PanelNode("b")))
    d = to_dict(tree)
    assert d["type"] == "split" and d["children"][0]["content_hint"] == "hero"
    assert from_dict(d) == tree
    with pytest.raises(ValueError):
        from_dict({"type": "mystery"})
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_tree.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/model/tree.py`)

```python
"""Pure layout tree. No Qt imports allowed in this package."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Iterator, Union


@dataclass(frozen=True)
class PanelNode:
    id: str
    content_hint: str = ""


@dataclass(frozen=True)
class SplitNode:
    orientation: str  # "row" = children side by side; "column" = stacked
    ratios: tuple[float, ...]
    children: tuple["Node", ...]

    def __post_init__(self):
        if self.orientation not in ("row", "column"):
            raise ValueError(f"orientation must be row|column, got {self.orientation!r}")
        if len(self.ratios) != len(self.children):
            raise ValueError("ratios and children must have equal length")


Node = Union[PanelNode, SplitNode]


def new_panel() -> PanelNode:
    return PanelNode(id=uuid.uuid4().hex[:8])


def iter_panels(node: Node) -> Iterator[PanelNode]:
    if isinstance(node, PanelNode):
        yield node
    else:
        for child in node.children:
            yield from iter_panels(child)


def to_dict(node: Node) -> dict:
    if isinstance(node, PanelNode):
        return {"type": "panel", "id": node.id, "content_hint": node.content_hint}
    return {
        "type": "split",
        "orientation": node.orientation,
        "ratios": list(node.ratios),
        "children": [to_dict(c) for c in node.children],
    }


def from_dict(d: dict) -> Node:
    kind = d.get("type")
    if kind == "panel":
        return PanelNode(id=d["id"], content_hint=d.get("content_hint", ""))
    if kind == "split":
        return SplitNode(
            d["orientation"],
            tuple(float(r) for r in d["ratios"]),
            tuple(from_dict(c) for c in d["children"]),
        )
    raise ValueError(f"unknown node type: {kind!r}")
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → 6 passed.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: layout tree nodes"`

---

### Task 4: Tree operations (`model/ops.py`)

**Files:**
- Create: `designer/figspec_designer/model/ops.py`
- Test: `designer/tests/test_ops.py`

**Interfaces:**
- Produces (pure functions, all return NEW trees; raise KeyError if panel_id absent):
  - `split_panel(root, panel_id: str, direction: str) -> Node` — direction "right"|"down" (ValueError otherwise). If the target's parent SplitNode has matching orientation, insert new panel after target splitting target's ratio in half; else wrap target in `SplitNode(orient, (0.5, 0.5), (target, new))`.
  - `close_panel(root, panel_id) -> Node` — remove, renormalize sibling ratios, collapse single-child splits; ValueError when closing the last panel.
  - `node_at(root, path: tuple[int, ...]) -> Node`; `set_ratios(root, path, ratios) -> Node` (normalizes ratios; ValueError if path is not a matching-arity SplitNode).
  - `set_content_hint(root, panel_id, text) -> Node`.
  - `snap_ratios(ratios, avail_mm: float, step: float = 0.5) -> tuple[float, ...]` — snap child sizes to step grid, last child absorbs remainder; returns input unchanged if any snapped size would fall below step.

- [ ] **Step 1: Write the failing test** (`designer/tests/test_ops.py`)

```python
import pytest
from figspec_designer.model.tree import PanelNode, SplitNode
from figspec_designer.model.ops import (close_panel, node_at, set_content_hint,
                                        set_ratios, snap_ratios, split_panel)

A, B, C = PanelNode("A"), PanelNode("B"), PanelNode("C")


def test_split_wraps_when_orientation_differs():
    out = split_panel(A, "A", "right")
    assert isinstance(out, SplitNode) and out.orientation == "row"
    assert out.ratios == (0.5, 0.5) and out.children[0] == A


def test_split_inlines_when_orientation_matches():
    root = SplitNode("row", (0.5, 0.3, 0.2), (A, B, C))
    out = split_panel(root, "B", "right")
    assert len(out.children) == 4
    assert out.children[1] == B
    assert out.ratios == pytest.approx((0.5, 0.15, 0.15, 0.2))


def test_split_down_wraps_inside_row():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = split_panel(root, "B", "down")
    inner = out.children[1]
    assert isinstance(inner, SplitNode) and inner.orientation == "column"
    assert inner.children[0] == B


def test_split_errors():
    with pytest.raises(KeyError):
        split_panel(A, "nope", "right")
    with pytest.raises(ValueError):
        split_panel(A, "A", "sideways")


def test_close_renormalizes_and_collapses():
    root = SplitNode("row", (0.5, 0.3, 0.2), (A, B, C))
    out = close_panel(root, "B")
    assert [c.id for c in out.children] == ["A", "C"]
    assert out.ratios == pytest.approx((0.5 / 0.7, 0.2 / 0.7))
    # closing down to one child collapses the split entirely
    assert close_panel(out, "C") == A


def test_close_collapses_nested_single_child():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    out = close_panel(root, "C")
    assert out.children[1] == B  # inner split collapsed away


def test_close_last_panel_forbidden():
    with pytest.raises(ValueError):
        close_panel(A, "A")


def test_set_ratios_by_path():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    assert node_at(root, (1,)).orientation == "column"
    out = set_ratios(root, (1,), (0.6, 0.4))
    assert out.children[1].ratios == pytest.approx((0.6, 0.4))
    out2 = set_ratios(root, (), (2.0, 2.0))  # normalizes
    assert out2.ratios == pytest.approx((0.5, 0.5))
    with pytest.raises(ValueError):
        set_ratios(root, (0,), (1.0,))  # path points at a panel


def test_set_content_hint():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = set_content_hint(root, "B", "inset")
    assert out.children[1].content_hint == "inset"
    with pytest.raises(KeyError):
        set_content_hint(root, "zz", "x")


def test_snap_ratios():
    # 100 mm avail, ratios .333/.667 -> sizes 33.3/66.7 -> snap to 33.5/66.5
    out = snap_ratios((0.333, 0.667), 100.0)
    assert out == pytest.approx((0.335, 0.665))
    # snapping that would starve a child returns input unchanged
    tiny = snap_ratios((0.001, 0.999), 100.0)
    assert tiny == pytest.approx((0.001, 0.999))
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_ops.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/model/ops.py`)

```python
"""Pure tree operations. Every function returns a new tree."""
from __future__ import annotations
from dataclasses import replace
from figspec_designer.model.tree import Node, PanelNode, SplitNode, new_panel

_ORIENT = {"right": "row", "down": "column"}


def split_panel(root: Node, panel_id: str, direction: str) -> Node:
    if direction not in _ORIENT:
        raise ValueError(f"direction must be right|down, got {direction!r}")
    orient = _ORIENT[direction]

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id != panel_id:
                return node
            return SplitNode(orient, (0.5, 0.5), (node, new_panel()))
        children: list[Node] = []
        ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            if (isinstance(child, PanelNode) and child.id == panel_id
                    and node.orientation == orient):
                children.extend([child, new_panel()])
                ratios.extend([ratio / 2, ratio / 2])
            else:
                children.append(rec(child))
                ratios.append(ratio)
        if all(a is b for a, b in zip(children, node.children)) \
                and len(children) == len(node.children):
            return node
        return SplitNode(node.orientation, tuple(ratios), tuple(children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def close_panel(root: Node, panel_id: str) -> Node:
    if isinstance(root, PanelNode):
        if root.id == panel_id:
            raise ValueError("cannot close the last remaining panel")
        raise KeyError(panel_id)

    def rec(node: Node):
        if isinstance(node, PanelNode):
            return None if node.id == panel_id else node
        kept_children: list[Node] = []
        kept_ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            rc = rec(child)
            if rc is not None:
                kept_children.append(rc)
                kept_ratios.append(ratio)
        unchanged = (len(kept_children) == len(node.children)
                     and all(a is b for a, b in zip(kept_children, node.children)))
        if unchanged:
            return node
        if not kept_children:
            return None
        if len(kept_children) == 1:
            return kept_children[0]
        total = sum(kept_ratios)
        return SplitNode(node.orientation,
                         tuple(r / total for r in kept_ratios),
                         tuple(kept_children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    if out is None:
        raise ValueError("cannot close the last remaining panel")
    return out


def node_at(root: Node, path: tuple[int, ...]) -> Node:
    node = root
    for i in path:
        node = node.children[i]
    return node


def set_ratios(root: Node, path: tuple[int, ...], ratios) -> Node:
    ratios = tuple(float(r) for r in ratios)
    total = sum(ratios)
    if total <= 0:
        raise ValueError("ratios must sum to a positive value")
    ratios = tuple(r / total for r in ratios)

    def rec(node: Node, path: tuple[int, ...]) -> Node:
        if not path:
            if not isinstance(node, SplitNode) or len(ratios) != len(node.children):
                raise ValueError("path does not address a matching SplitNode")
            return SplitNode(node.orientation, ratios, node.children)
        if not isinstance(node, SplitNode):
            raise ValueError("path descends through a panel")
        i = path[0]
        children = list(node.children)
        children[i] = rec(children[i], path[1:])
        return SplitNode(node.orientation, node.ratios, tuple(children))

    return rec(root, tuple(path))


def set_content_hint(root: Node, panel_id: str, text: str) -> Node:
    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                return replace(node, content_hint=text)
            return node
        children = tuple(rec(c) for c in node.children)
        if all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, node.ratios, children)

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def snap_ratios(ratios, avail_mm: float, step: float = 0.5) -> tuple[float, ...]:
    ratios = tuple(float(r) for r in ratios)
    sizes = [r * avail_mm for r in ratios]
    snapped = [round(s / step) * step for s in sizes[:-1]]
    if any(s < step for s in snapped):
        return ratios
    last = avail_mm - sum(snapped)
    if last < step:
        return ratios
    snapped.append(last)
    return tuple(s / avail_mm for s in snapped)
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: pure tree operations with snap"`

---

### Task 5: Flatten and labels (`model/flatten.py`)

**Files:**
- Create: `designer/figspec_designer/model/flatten.py`
- Test: `designer/tests/test_flatten.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) PanelRect(panel_id: str, x_mm: float, y_mm: float, w_mm: float, h_mm: float)`; `flatten(root, width_mm, height_mm, gutter_mm) -> list[PanelRect]` (tree order, mm rounded 3dp); `assign_labels(rects) -> dict[str, str]` (reading order); `derive(rect, dpi) -> tuple[int, int, tuple[float, float]]` (w_px, h_px, figsize_in).

- [ ] **Step 1: Write the failing test** (`designer/tests/test_flatten.py`) — ground truth: 183×100 page, gutter 4, L-shaped tree row(0.5,0.5)[A, column(0.6,0.4)[B, C]]:

```python
import pytest
from figspec_designer.model.tree import PanelNode, SplitNode
from figspec_designer.model.flatten import assign_labels, derive, flatten

TREE = SplitNode("row", (0.5, 0.5),
                 (PanelNode("A"),
                  SplitNode("column", (0.6, 0.4),
                            (PanelNode("B"), PanelNode("C")))))


def test_flatten_l_shape_exact():
    rects = {r.panel_id: r for r in flatten(TREE, 183.0, 100.0, 4.0)}
    a, b, c = rects["A"], rects["B"], rects["C"]
    assert (a.x_mm, a.y_mm, a.w_mm, a.h_mm) == (0.0, 0.0, 89.5, 100.0)
    assert (b.x_mm, b.y_mm, b.w_mm, b.h_mm) == (93.5, 0.0, 89.5, 57.6)
    assert (c.x_mm, c.y_mm, c.w_mm, c.h_mm) == (93.5, 61.6, 89.5, 38.4)


def test_labels_reading_order():
    labels = assign_labels(flatten(TREE, 183.0, 100.0, 4.0))
    assert labels == {"A": "a", "B": "b", "C": "c"}


def test_labels_beyond_z():
    from figspec_designer.model.flatten import PanelRect
    rects = [PanelRect(f"p{i}", float(i), 0.0, 1.0, 1.0) for i in range(28)]
    labels = assign_labels(rects)
    assert labels["p25"] == "z" and labels["p26"] == "aa" and labels["p27"] == "ab"


def test_derive():
    from figspec_designer.model.flatten import PanelRect
    w_px, h_px, figsize = derive(PanelRect("x", 0, 0, 89.5, 50.0), 600)
    assert (w_px, h_px) == (2114, 1181)
    assert figsize == (pytest.approx(3.524, abs=0.001), pytest.approx(1.969, abs=0.001))
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_flatten.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/model/flatten.py`)

```python
"""Tree -> absolute mm rectangles (top-left origin, y down) + labels."""
from __future__ import annotations
from dataclasses import dataclass
from figspec_designer.model.tree import Node, PanelNode


@dataclass(frozen=True)
class PanelRect:
    panel_id: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


def flatten(root: Node, width_mm: float, height_mm: float,
            gutter_mm: float) -> list[PanelRect]:
    out: list[PanelRect] = []

    def rec(node: Node, x: float, y: float, w: float, h: float) -> None:
        if isinstance(node, PanelNode):
            out.append(PanelRect(node.id, round(x, 3), round(y, 3),
                                 round(w, 3), round(h, 3)))
            return
        n = len(node.children)
        if node.orientation == "row":
            avail = w - (n - 1) * gutter_mm
            cx = x
            for child, ratio in zip(node.children, node.ratios):
                cw = avail * ratio
                rec(child, cx, y, cw, h)
                cx += cw + gutter_mm
        else:
            avail = h - (n - 1) * gutter_mm
            cy = y
            for child, ratio in zip(node.children, node.ratios):
                ch = avail * ratio
                rec(child, x, cy, w, ch)
                cy += ch + gutter_mm

    rec(root, 0.0, 0.0, width_mm, height_mm)
    return out


def _label(i: int) -> str:
    s = ""
    while True:
        s = chr(ord("a") + i % 26) + s
        i = i // 26 - 1
        if i < 0:
            return s


def assign_labels(rects: list[PanelRect]) -> dict[str, str]:
    ordered = sorted(rects, key=lambda r: (round(r.y_mm, 1), r.x_mm))
    return {r.panel_id: _label(i) for i, r in enumerate(ordered)}


def derive(rect: PanelRect, dpi: int) -> tuple[int, int, tuple[float, float]]:
    w_px = round(rect.w_mm / 25.4 * dpi)
    h_px = round(rect.h_mm / 25.4 * dpi)
    return w_px, h_px, (round(rect.w_mm / 25.4, 3), round(rect.h_mm / 25.4, 3))
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: flatten tree to mm rects with labels"`

---

### Task 6: Undo history (`model/history.py`)

**Files:**
- Create: `designer/figspec_designer/model/history.py`
- Test: `designer/tests/test_history.py`

**Interfaces:**
- Produces: `class History: __init__(initial)`, `.current` property, `.push(state)` (clears redo), `.undo() -> state`, `.redo() -> state`, `.can_undo() -> bool`, `.can_redo() -> bool`.

- [ ] **Step 1: Write the failing test** (`designer/tests/test_history.py`)

```python
from figspec_designer.model.history import History


def test_undo_redo_cycle():
    h = History("s0")
    assert h.current == "s0" and not h.can_undo() and not h.can_redo()
    h.push("s1")
    h.push("s2")
    assert h.current == "s2" and h.can_undo()
    assert h.undo() == "s1"
    assert h.undo() == "s0"
    assert h.undo() == "s0"  # bottoms out
    assert h.redo() == "s1"
    h.push("s1b")  # push clears redo
    assert not h.can_redo()
    assert h.current == "s1b"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_history.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/model/history.py`)

```python
"""Snapshot undo stack. States are immutable trees, so storing them is free."""
from __future__ import annotations


class History:
    def __init__(self, initial):
        self._undo = [initial]
        self._redo: list = []

    @property
    def current(self):
        return self._undo[-1]

    def push(self, state) -> None:
        self._undo.append(state)
        self._redo.clear()

    def undo(self):
        if len(self._undo) > 1:
            self._redo.append(self._undo.pop())
        return self.current

    def redo(self):
        if self._redo:
            self._undo.append(self._redo.pop())
        return self.current

    def can_undo(self) -> bool:
        return len(self._undo) > 1

    def can_redo(self) -> bool:
        return bool(self._redo)
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: undo history"`

---

### Task 7: Presets and document layer (`presets.py`, `document.py`)

**Files:**
- Create: `designer/figspec_designer/presets.py`, `designer/figspec_designer/document.py`
- Test: `designer/tests/test_document.py`

**Interfaces:**
- Consumes: `figspec.spec` (Task 2), model modules (Tasks 3–5).
- Produces:
  - `presets.PRESETS: dict[str, float]` = {"nature_single": 89.0, "nature_double": 183.0, "acs_single": 82.5, "acs_double": 178.0, "aps_single": 86.0, "aps_double": 172.0}; `DEFAULT_HEIGHT_MM = 100.0`, `DEFAULT_DPI = 600`, `DEFAULT_GUTTER_MM = 4.0`.
  - `class MissingDesignerData(Exception)`.
  - `@dataclass DesignerDocument(tree: Node, target: Target, constraints: Constraints)` with: `default() classmethod` (nature_double, one panel); `panel_rects() -> list[PanelRect]`; `labels() -> dict[str, str]`; `to_spec_dict() -> dict` (panels sorted by label, content_hints from tree, designer sidecar {"tree": to_dict(tree)}); `to_json() -> str` (indent=2 + trailing newline); `from_spec_dict(data) classmethod` (raises MissingDesignerData when `designer.tree` absent, SpecError bubbles up).

- [ ] **Step 1: Write the failing test** (`designer/tests/test_document.py`)

```python
import json
import pytest
from figspec.spec import SpecError
from figspec_designer.document import DesignerDocument, MissingDesignerData
from figspec_designer.model.ops import split_panel
from figspec_designer.model.tree import iter_panels


def _two_panel_doc():
    doc = DesignerDocument.default()
    first = next(iter_panels(doc.tree)).id
    doc.tree = split_panel(doc.tree, first, "right")
    return doc


def test_default_document():
    doc = DesignerDocument.default()
    assert doc.target.journal_preset == "nature_double"
    assert doc.target.figure_width_mm == 183.0
    assert len(list(iter_panels(doc.tree))) == 1


def test_to_spec_dict_shape():
    doc = _two_panel_doc()
    d = doc.to_spec_dict()
    assert [p["label"] for p in d["panels"]] == ["a", "b"]
    a = d["panels"][0]
    assert a["x_mm"] == 0.0 and a["w_mm"] == 89.5  # (183-4)/2
    assert a["w_px"] == 2114
    assert d["designer"]["tree"]["type"] == "split"


def test_json_roundtrip():
    doc = _two_panel_doc()
    data = json.loads(doc.to_json())
    doc2 = DesignerDocument.from_spec_dict(data)
    assert doc2.to_spec_dict() == doc.to_spec_dict()


def test_open_without_designer_sidecar():
    data = _two_panel_doc().to_spec_dict()
    del data["designer"]
    with pytest.raises(MissingDesignerData):
        DesignerDocument.from_spec_dict(data)


def test_open_malformed_spec():
    with pytest.raises(SpecError):
        DesignerDocument.from_spec_dict({"nope": 1})
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_document.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

`designer/figspec_designer/presets.py`:
```python
"""Journal width presets (mm) and canvas defaults."""
PRESETS: dict[str, float] = {
    "nature_single": 89.0,
    "nature_double": 183.0,
    "acs_single": 82.5,
    "acs_double": 178.0,
    "aps_single": 86.0,
    "aps_double": 172.0,
}
DEFAULT_HEIGHT_MM = 100.0
DEFAULT_DPI = 600
DEFAULT_GUTTER_MM = 4.0
```

`designer/figspec_designer/document.py`:
```python
"""Document = layout tree + target + constraints; bridges model and figspec.spec."""
from __future__ import annotations
import json
from dataclasses import dataclass
from figspec.spec import Constraints, PanelSpec, Target, build_spec, parse_spec
from figspec_designer import presets
from figspec_designer.model.flatten import PanelRect, assign_labels, derive, flatten
from figspec_designer.model.tree import Node, from_dict, iter_panels, new_panel, to_dict


class MissingDesignerData(Exception):
    """figspec.json lacks the designer.tree sidecar needed for editing."""


@dataclass
class DesignerDocument:
    tree: Node
    target: Target
    constraints: Constraints

    @classmethod
    def default(cls) -> "DesignerDocument":
        return cls(
            tree=new_panel(),
            target=Target("nature_double", presets.PRESETS["nature_double"],
                          presets.DEFAULT_HEIGHT_MM, presets.DEFAULT_DPI,
                          presets.DEFAULT_GUTTER_MM),
            constraints=Constraints(),
        )

    def panel_rects(self) -> list[PanelRect]:
        return flatten(self.tree, self.target.figure_width_mm,
                       self.target.figure_height_mm, self.target.gutter_mm)

    def labels(self) -> dict[str, str]:
        return assign_labels(self.panel_rects())

    def to_spec_dict(self) -> dict:
        rects = self.panel_rects()
        labels = self.labels()
        hints = {p.id: p.content_hint for p in iter_panels(self.tree)}
        panels = []
        for rect in sorted(rects, key=lambda r: (round(r.y_mm, 1), r.x_mm)):
            w_px, h_px, figsize = derive(rect, self.target.dpi)
            panels.append(PanelSpec(
                label=labels[rect.panel_id],
                x_mm=rect.x_mm, y_mm=rect.y_mm, w_mm=rect.w_mm, h_mm=rect.h_mm,
                w_px=w_px, h_px=h_px, figsize_in=figsize,
                content_hint=hints[rect.panel_id],
            ))
        return build_spec(self.target, self.constraints, panels,
                          designer={"tree": to_dict(self.tree)})

    def to_json(self) -> str:
        return json.dumps(self.to_spec_dict(), indent=2) + "\n"

    @classmethod
    def from_spec_dict(cls, data: dict) -> "DesignerDocument":
        target, constraints, _panels, designer = parse_spec(data)
        if not designer or "tree" not in designer:
            raise MissingDesignerData(
                "this figspec.json has no designer layout data; "
                "V1 cannot reconstruct a tree from panel rectangles")
        return cls(tree=from_dict(designer["tree"]), target=target,
                   constraints=constraints)
```

Note: `to_spec_dict` sorts panels by the same reading-order key `(round(y_mm, 1), x_mm)` that `assign_labels` uses — never by label string ("aa" < "b" lexicographically would break >26 panels).

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: presets and document export/open layer"`

---

### Task 8: Panel widget (`ui/panel_widget.py`)

**Files:**
- Create: `designer/figspec_designer/ui/panel_widget.py`
- Test: `designer/tests/test_panel_widget.py`

**Interfaces:**
- Produces: `class PanelWidget(QFrame)` — ctor `(panel_id: str, label_text: str)`; Signal `action = Signal(str, str)` emitting `(action, panel_id)` with action ∈ "split_right"|"split_down"|"close"|"select"; methods `set_label(text)`, `set_selected(on: bool)`; hover shows the three buttons (objectNames `btn_split_right`, `btn_split_down`, `btn_close`), click anywhere emits select.

- [ ] **Step 1: Write the failing test** (`designer/tests/test_panel_widget.py`)

```python
from PySide6.QtCore import Qt
from figspec_designer.ui.panel_widget import PanelWidget


def test_buttons_emit_actions(qtbot):
    w = PanelWidget("p1", "a")
    qtbot.addWidget(w)
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    for name, expected in [("btn_split_right", "split_right"),
                           ("btn_split_down", "split_down"),
                           ("btn_close", "close")]:
        btn = w.findChild(object, name)
        qtbot.mouseClick(btn, Qt.LeftButton)
        assert got[-1] == (expected, "p1")


def test_click_selects_and_label_updates(qtbot):
    w = PanelWidget("p2", "a")
    qtbot.addWidget(w)
    got = []
    w.action.connect(lambda act, pid: got.append((act, pid)))
    qtbot.mouseClick(w, Qt.LeftButton)
    assert ("select", "p2") in got
    w.set_label("c")
    assert w.label_widget.text() == "c"
    w.set_selected(True)
    assert w.property("selected") is True
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_panel_widget.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/ui/panel_widget.py`)

```python
"""A single panel on the canvas: big label, hover action buttons."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QToolButton,
                               QVBoxLayout, QWidget)

_BTN_SPECS = [("btn_split_right", "▸", "split_right", "Split right (Cmd+D)"),
              ("btn_split_down", "▾", "split_down", "Split down (Shift+Cmd+D)"),
              ("btn_close", "✕", "close", "Delete panel (Cmd+Backspace)")]


class PanelWidget(QFrame):
    action = Signal(str, str)  # (action, panel_id)

    def __init__(self, panel_id: str, label_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.panel_id = panel_id
        self.setObjectName("panel")
        self.setProperty("selected", False)
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()
        bar.addStretch(1)
        self._buttons = []
        for name, glyph, act, tip in _BTN_SPECS:
            btn = QToolButton(self)
            btn.setObjectName(name)
            btn.setText(glyph)
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _=False, a=act: self.action.emit(a, self.panel_id))
            btn.setVisible(False)
            bar.addWidget(btn)
            self._buttons.append(btn)
        root.addLayout(bar)

        self.label_widget = QLabel(label_text, self)
        self.label_widget.setAlignment(Qt.AlignCenter)
        self.label_widget.setStyleSheet("font-size: 24px; font-weight: bold; color: #555;")
        root.addWidget(self.label_widget, stretch=1)

    def _apply_style(self) -> None:
        selected = self.property("selected")
        border = "2px solid #0F62FE" if selected else "1px solid #b0b0b0"
        self.setStyleSheet(f"QFrame#panel {{ background: #fafafa; border: {border}; }}")

    def set_label(self, text: str) -> None:
        self.label_widget.setText(text)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", bool(on))
        self._apply_style()

    def enterEvent(self, event) -> None:
        for b in self._buttons:
            b.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        for b in self._buttons:
            b.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.action.emit("select", self.panel_id)
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: panel widget with hover actions"`

---

### Task 9: Canvas with gutter splitters (`ui/handle.py`, `ui/canvas.py`)

**Files:**
- Create: `designer/figspec_designer/ui/handle.py`, `designer/figspec_designer/ui/canvas.py`
- Test: `designer/tests/test_canvas.py`

**Interfaces:**
- Consumes: model (tree/ops/flatten), `PanelWidget` (Task 8), `DesignerDocument` (Task 7).
- Produces:
  - `handle.GutterSplitter(QSplitter)` — ctor `(orientation_qt, path: tuple[int, ...], canvas)`; `createHandle()` returns `GutterHandle`; `setChildrenCollapsible(False)` applied.
  - `handle.GutterHandle(QSplitterHandle)` — during drag shows canvas feedback label with adjacent child sizes in mm; on mouse release calls `canvas.commit_splitter(splitter, alt_held)`.
  - `canvas.Canvas(QWidget)` — Signals: `panel_action = Signal(str, str)` (re-emitted from PanelWidgets), `ratios_committed = Signal(tuple, tuple)` (path, new_ratios — already snapped unless ⌥). Methods: `set_document(doc)` (full rebuild), `panel_widgets() -> dict[str, PanelWidget]`, `px_per_mm: float` attribute, `commit_splitter(splitter, alt_held)` (reads sizes → mm → ratios → snap via `ops.snap_ratios` unless alt → emit `ratios_committed`), `apply_selection(panel_id | None)`, `mm_sizes(splitter) -> list[float]`.

- [ ] **Step 1: Write the failing test** (`designer/tests/test_canvas.py`)

```python
import pytest
from figspec_designer.document import DesignerDocument
from figspec_designer.model.ops import split_panel
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.canvas import Canvas


def _doc_two_panels():
    doc = DesignerDocument.default()
    first = next(iter_panels(doc.tree)).id
    doc.tree = split_panel(doc.tree, first, "right")
    return doc


def test_canvas_builds_widgets(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    assert set(canvas.panel_widgets()) == {p.id for p in iter_panels(doc.tree)}
    labels = doc.labels()
    for pid, w in canvas.panel_widgets().items():
        assert w.label_widget.text() == labels[pid]


def test_panel_action_forwarded(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    got = []
    canvas.panel_action.connect(lambda a, pid: got.append((a, pid)))
    pid = next(iter(canvas.panel_widgets()))
    canvas.panel_widgets()[pid].action.emit("split_down", pid)
    assert got == [("split_down", pid)]


def test_commit_splitter_emits_snapped_ratios(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    (path, splitter), = canvas.splitters().items()
    assert path == ()
    got = []
    canvas.ratios_committed.connect(lambda p, r: got.append((p, r)))
    # force uneven pixel sizes then commit
    total = sum(splitter.sizes())
    splitter.setSizes([int(total * 0.333), total - int(total * 0.333)])
    canvas.commit_splitter(splitter, alt_held=False)
    (p, ratios), = got
    assert p == ()
    # snapped ratios correspond to whole 0.5mm sizes over avail = 183-4 = 179mm
    sizes_mm = [r * 179.0 for r in ratios]
    for s in sizes_mm:
        assert s == pytest.approx(round(s * 2) / 2, abs=1e-6)


def test_selection_highlight(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    pid = next(iter(canvas.panel_widgets()))
    canvas.apply_selection(pid)
    assert canvas.panel_widgets()[pid].property("selected") is True
    canvas.apply_selection(None)
    assert canvas.panel_widgets()[pid].property("selected") is False
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_canvas.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

`designer/figspec_designer/ui/handle.py`:
```python
"""Custom splitter whose handles ARE the gutters, with live mm feedback."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QSplitterHandle


class GutterHandle(QSplitterHandle):
    def __init__(self, orientation, splitter: "GutterSplitter"):
        super().__init__(orientation, splitter)
        self.setStyleSheet("background: #e8e8e8;")

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        splitter = self.splitter()
        splitter.canvas.show_drag_feedback(splitter, self)

    def mouseReleaseEvent(self, event) -> None:
        alt = bool(event.modifiers() & Qt.AltModifier)
        super().mouseReleaseEvent(event)
        splitter = self.splitter()
        splitter.canvas.hide_drag_feedback()
        splitter.canvas.commit_splitter(splitter, alt_held=alt)


class GutterSplitter(QSplitter):
    def __init__(self, orientation_qt, path: tuple[int, ...], canvas):
        super().__init__(orientation_qt)
        self.path = path
        self.canvas = canvas
        self.setChildrenCollapsible(False)

    def createHandle(self) -> QSplitterHandle:
        return GutterHandle(self.orientation(), self)
```

`designer/figspec_designer/ui/canvas.py`:
```python
"""Renders the layout tree as nested GutterSplitters inside a page frame."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget
from figspec_designer.document import DesignerDocument
from figspec_designer.model import ops
from figspec_designer.model.tree import Node, PanelNode
from figspec_designer.ui.handle import GutterSplitter
from figspec_designer.ui.panel_widget import PanelWidget

_MARGIN_PX = 24


class Canvas(QWidget):
    panel_action = Signal(str, str)      # (action, panel_id)
    ratios_committed = Signal(tuple, tuple)  # (path, ratios)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc: DesignerDocument | None = None
        self._page: QWidget | None = None
        self._panels: dict[str, PanelWidget] = {}
        self._splitters: dict[tuple[int, ...], GutterSplitter] = {}
        self.px_per_mm = 1.0
        self._feedback = QLabel(self)
        self._feedback.setStyleSheet(
            "background: #333; color: white; padding: 2px 6px; border-radius: 3px;")
        self._feedback.hide()

    # ---- public API -------------------------------------------------
    def panel_widgets(self) -> dict[str, PanelWidget]:
        return dict(self._panels)

    def splitters(self) -> dict[tuple[int, ...], GutterSplitter]:
        return dict(self._splitters)

    def set_document(self, doc: DesignerDocument) -> None:
        self._doc = doc
        self._rebuild()

    def apply_selection(self, panel_id: str | None) -> None:
        for pid, w in self._panels.items():
            w.set_selected(pid == panel_id)

    # ---- geometry ---------------------------------------------------
    def _fit_scale(self) -> float:
        t = self._doc.target
        avail_w = max(self.width() - 2 * _MARGIN_PX, 50)
        avail_h = max(self.height() - 2 * _MARGIN_PX, 50)
        return max(min(avail_w / t.figure_width_mm, avail_h / t.figure_height_mm), 0.1)

    def mm_sizes(self, splitter: GutterSplitter) -> list[float]:
        return [s / self.px_per_mm for s in splitter.sizes()]

    # ---- build ------------------------------------------------------
    def _rebuild(self) -> None:
        if self._page is not None:
            self._page.deleteLater()
        self._panels.clear()
        self._splitters.clear()
        if self._doc is None:
            return
        t = self._doc.target
        self.px_per_mm = self._fit_scale()
        labels = self._doc.labels()
        self._page = QWidget(self)
        self._page.setStyleSheet("background: white; border: 1px solid #888;")
        page_w = round(t.figure_width_mm * self.px_per_mm)
        page_h = round(t.figure_height_mm * self.px_per_mm)
        self._page.setGeometry((self.width() - page_w) // 2,
                               (self.height() - page_h) // 2, page_w, page_h)
        content = self._build_node(self._doc.tree, (), labels)
        content.setParent(self._page)
        content.setGeometry(0, 0, page_w, page_h)
        self._page.show()
        content.show()
        self._feedback.raise_()

    def _build_node(self, node: Node, path: tuple[int, ...],
                    labels: dict[str, str]) -> QWidget:
        if isinstance(node, PanelNode):
            w = PanelWidget(node.id, labels.get(node.id, "?"))
            w.action.connect(self.panel_action.emit)
            self._panels[node.id] = w
            return w
        qt_orient = Qt.Horizontal if node.orientation == "row" else Qt.Vertical
        splitter = GutterSplitter(qt_orient, path, self)
        gutter_px = max(round(self._doc.target.gutter_mm * self.px_per_mm), 1)
        splitter.setHandleWidth(gutter_px)
        for i, child in enumerate(node.children):
            splitter.addWidget(self._build_node(child, path + (i,), labels))
        total_px = round((self._axis_mm(node, path) -
                          (len(node.children) - 1) * self._doc.target.gutter_mm)
                         * self.px_per_mm)
        splitter.setSizes([max(round(r * total_px), 1) for r in node.ratios])
        self._splitters[path] = splitter
        return splitter

    def _axis_mm(self, node: Node, path: tuple[int, ...]) -> float:
        """Length in mm of this splitter's axis, derived from the flattened rects."""
        rects = {r.panel_id: r for r in self._doc.panel_rects()}
        first = next(iter(self._iter_node_panels(node)))
        last_rects = [rects[p.id] for p in self._iter_node_panels(node)]
        if node.orientation == "row":
            x0 = min(r.x_mm for r in last_rects)
            x1 = max(r.x_mm + r.w_mm for r in last_rects)
            return x1 - x0
        y0 = min(r.y_mm for r in last_rects)
        y1 = max(r.y_mm + r.h_mm for r in last_rects)
        return y1 - y0

    @staticmethod
    def _iter_node_panels(node: Node):
        from figspec_designer.model.tree import iter_panels
        return iter_panels(node)

    # ---- drag feedback + commit ------------------------------------
    def show_drag_feedback(self, splitter: GutterSplitter, handle) -> None:
        sizes = self.mm_sizes(splitter)
        idx = max(splitter.indexOf(handle) - 1, 0)
        left = sizes[idx]
        right = sizes[idx + 1] if idx + 1 < len(sizes) else 0.0
        self._feedback.setText(f"{left:.1f} mm | {right:.1f} mm")
        self._feedback.adjustSize()
        pos = handle.mapTo(self, handle.rect().center())
        self._feedback.move(pos.x() + 8, pos.y() - 24)
        self._feedback.show()
        self._feedback.raise_()

    def hide_drag_feedback(self) -> None:
        self._feedback.hide()

    def commit_splitter(self, splitter: GutterSplitter, alt_held: bool) -> None:
        sizes_px = splitter.sizes()
        total = sum(sizes_px)
        if total <= 0:
            return
        ratios = tuple(s / total for s in sizes_px)
        if not alt_held:
            node = ops.node_at(self._doc.tree, splitter.path)
            avail_mm = (self._axis_mm(node, splitter.path)
                        - (len(sizes_px) - 1) * self._doc.target.gutter_mm)
            ratios = ops.snap_ratios(ratios, avail_mm)
        self.ratios_committed.emit(splitter.path, ratios)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._doc is not None:
            self._rebuild()
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass. Debug notes: offscreen platform still lays out widgets; if `splitter.sizes()` come back all zeros in the commit test, call `canvas.show()` + `qtbot.waitExposed(canvas)` — do not weaken the snap assertion.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: canvas with gutter splitters and snap commit"`

---

### Task 10: Sidebar and top bar (`ui/sidebar.py`, `ui/toolbar.py`)

**Files:**
- Create: `designer/figspec_designer/ui/sidebar.py`, `designer/figspec_designer/ui/toolbar.py`
- Test: `designer/tests/test_sidebar_toolbar.py`

**Interfaces:**
- Produces:
  - `Sidebar(QWidget)` — Signal `content_hint_edited = Signal(str, str)` (panel_id, text); `show_panel(panel_id, label, rect: PanelRect, dpi: int, content_hint: str)` (fills labels: size mm one decimal, px, figsize 3dp); `clear()`. Attributes for tests: `.lbl_label`, `.lbl_mm`, `.lbl_px`, `.lbl_figsize`, `.hint_edit`.
  - `TopBar(QWidget)` — Signals: `settings_changed = Signal()`, `save_requested = Signal()`, `copy_requested = Signal()`, `open_requested = Signal()`; `values() -> tuple[str, float, float, int, float]` (preset_key, width_mm, height_mm, dpi, gutter_mm); `set_values(preset_key, width, height, dpi, gutter)`. Preset combo has entries from `presets.PRESETS` plus "custom"; width spin enabled only for custom; selecting a preset writes its width into the spin. Attributes: `.preset_combo`, `.width_spin`, `.height_spin`, `.dpi_spin`, `.gutter_spin`, `.btn_save`, `.btn_copy`, `.btn_open`.

- [ ] **Step 1: Write the failing test** (`designer/tests/test_sidebar_toolbar.py`)

```python
from figspec_designer.model.flatten import PanelRect
from figspec_designer.ui.sidebar import Sidebar
from figspec_designer.ui.toolbar import TopBar


def test_sidebar_shows_values(qtbot):
    sb = Sidebar()
    qtbot.addWidget(sb)
    sb.show_panel("p1", "b", PanelRect("p1", 93.5, 0.0, 89.5, 57.6), 600, "hero")
    assert sb.lbl_label.text() == "b"
    assert "89.5" in sb.lbl_mm.text() and "57.6" in sb.lbl_mm.text()
    assert "2114" in sb.lbl_px.text()
    assert "3.524" in sb.lbl_figsize.text()
    assert sb.hint_edit.text() == "hero"
    got = []
    sb.content_hint_edited.connect(lambda pid, t: got.append((pid, t)))
    sb.hint_edit.setText("new hint")
    sb.hint_edit.editingFinished.emit()
    assert got[-1] == ("p1", "new hint")
    sb.clear()
    assert sb.lbl_label.text() == "—"


def test_topbar_preset_drives_width(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    tb.preset_combo.setCurrentText("nature_single")
    assert tb.values()[0] == "nature_single"
    assert tb.values()[1] == 89.0
    assert not tb.width_spin.isEnabled()
    tb.preset_combo.setCurrentText("custom")
    assert tb.width_spin.isEnabled()
    tb.width_spin.setValue(120.0)
    assert tb.values()[1] == 120.0


def test_topbar_signals(qtbot):
    tb = TopBar()
    qtbot.addWidget(tb)
    got = []
    tb.settings_changed.connect(lambda: got.append("settings"))
    tb.save_requested.connect(lambda: got.append("save"))
    tb.height_spin.setValue(120.0)
    tb.btn_save.click()
    assert "settings" in got and "save" in got
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_sidebar_toolbar.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

`designer/figspec_designer/ui/sidebar.py`:
```python
"""Selected-panel inspector: label, mm / px / figsize, content hint."""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QWidget
from figspec_designer.model.flatten import PanelRect, derive


class Sidebar(QWidget):
    content_hint_edited = Signal(str, str)  # (panel_id, text)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._panel_id: str | None = None
        form = QFormLayout(self)
        self.lbl_label = QLabel("—")
        self.lbl_mm = QLabel("—")
        self.lbl_px = QLabel("—")
        self.lbl_figsize = QLabel("—")
        self.hint_edit = QLineEdit()
        self.hint_edit.setPlaceholderText("content hint (e.g. STEM image + FFT inset)")
        form.addRow("Panel", self.lbl_label)
        form.addRow("Size (mm)", self.lbl_mm)
        form.addRow("Pixels", self.lbl_px)
        form.addRow("figsize (in)", self.lbl_figsize)
        form.addRow("Hint", self.hint_edit)
        self.hint_edit.editingFinished.connect(self._emit_hint)
        self.hint_edit.setEnabled(False)

    def _emit_hint(self) -> None:
        if self._panel_id is not None:
            self.content_hint_edited.emit(self._panel_id, self.hint_edit.text())

    def show_panel(self, panel_id: str, label: str, rect: PanelRect,
                   dpi: int, content_hint: str) -> None:
        self._panel_id = panel_id
        w_px, h_px, figsize = derive(rect, dpi)
        self.lbl_label.setText(label)
        self.lbl_mm.setText(f"{rect.w_mm:.1f} × {rect.h_mm:.1f}")
        self.lbl_px.setText(f"{w_px} × {h_px} @ {dpi} dpi")
        self.lbl_figsize.setText(f"({figsize[0]:.3f}, {figsize[1]:.3f})")
        self.hint_edit.setEnabled(True)
        self.hint_edit.setText(content_hint)

    def clear(self) -> None:
        self._panel_id = None
        for lbl in (self.lbl_label, self.lbl_mm, self.lbl_px, self.lbl_figsize):
            lbl.setText("—")
        self.hint_edit.clear()
        self.hint_edit.setEnabled(False)
```

`designer/figspec_designer/ui/toolbar.py`:
```python
"""Page settings + export actions."""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QWidget)
from figspec_designer import presets


class TopBar(QWidget):
    settings_changed = Signal()
    save_requested = Signal()
    copy_requested = Signal()
    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(presets.PRESETS) + ["custom"])
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10.0, 1000.0)
        self.width_spin.setSuffix(" mm")
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 1000.0)
        self.height_spin.setSuffix(" mm")
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 2400)
        self.gutter_spin = QDoubleSpinBox()
        self.gutter_spin.setRange(0.0, 50.0)
        self.gutter_spin.setSingleStep(0.5)
        self.gutter_spin.setSuffix(" mm")
        self.btn_open = QPushButton("Open…")
        self.btn_save = QPushButton("Save JSON…")
        self.btn_copy = QPushButton("Copy JSON")

        for label, w in [("Preset", self.preset_combo), ("Width", self.width_spin),
                         ("Height", self.height_spin), ("DPI", self.dpi_spin),
                         ("Gutter", self.gutter_spin)]:
            lay.addWidget(QLabel(label))
            lay.addWidget(w)
        lay.addStretch(1)
        for b in (self.btn_open, self.btn_save, self.btn_copy):
            lay.addWidget(b)

        self.set_values("nature_double", presets.PRESETS["nature_double"],
                        presets.DEFAULT_HEIGHT_MM, presets.DEFAULT_DPI,
                        presets.DEFAULT_GUTTER_MM)

        self.preset_combo.currentTextChanged.connect(self._on_preset)
        for spin in (self.width_spin, self.height_spin, self.gutter_spin):
            spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.dpi_spin.valueChanged.connect(lambda _=None: self.settings_changed.emit())
        self.btn_save.clicked.connect(self.save_requested.emit)
        self.btn_copy.clicked.connect(self.copy_requested.emit)
        self.btn_open.clicked.connect(self.open_requested.emit)

    def _on_preset(self, key: str) -> None:
        if key in presets.PRESETS:
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(presets.PRESETS[key])
            self.width_spin.blockSignals(False)
            self.width_spin.setEnabled(False)
        else:
            self.width_spin.setEnabled(True)
        self.settings_changed.emit()

    def values(self) -> tuple[str, float, float, int, float]:
        return (self.preset_combo.currentText(), self.width_spin.value(),
                self.height_spin.value(), self.dpi_spin.value(),
                self.gutter_spin.value())

    def set_values(self, preset_key: str, width: float, height: float,
                   dpi: int, gutter: float) -> None:
        for w in (self.preset_combo, self.width_spin, self.height_spin,
                  self.dpi_spin, self.gutter_spin):
            w.blockSignals(True)
        self.preset_combo.setCurrentText(preset_key)
        self.width_spin.setValue(width)
        self.width_spin.setEnabled(preset_key not in presets.PRESETS)
        self.height_spin.setValue(height)
        self.dpi_spin.setValue(dpi)
        self.gutter_spin.setValue(gutter)
        for w in (self.preset_combo, self.width_spin, self.height_spin,
                  self.dpi_spin, self.gutter_spin):
            w.blockSignals(False)
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: sidebar inspector and settings top bar"`

---

### Task 11: Main window and app entry (`ui/main_window.py`, `app.py`)

**Files:**
- Create: `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/app.py`
- Test: `designer/tests/test_main_window.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `MainWindow(QMainWindow)` — owns `doc: DesignerDocument`, `history: History` (stores trees), `selected_panel_id: str | None`. Public-for-test methods: `do_action(action: str, panel_id: str | None = None)` handling "split_right"/"split_down"/"close"/"select"; `apply_ratios(path, ratios)`; `undo()`, `redo()`; `export_json_text() -> str`; `copy_json()` (clipboard); `save_json(path)`; `open_json(path)` (MissingDesignerData/SpecError → returns error string instead of raising, shows QMessageBox only when window visible). Menu actions with shortcuts per Global Constraints. Closing the last panel is a no-op with a status-bar message.
  - `app.main(argv: list[str] | None = None) -> int` — `--smoke` flag: forces offscreen, opens MainWindow, quits after event-loop start (used by packaging verification).

- [ ] **Step 1: Write the failing test** (`designer/tests/test_main_window.py`)

```python
import json
from figspec.spec import parse_spec
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def _first_panel(win):
    return next(iter_panels(win.doc.tree)).id


def test_split_and_labels(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    assert sorted(win.doc.labels().values()) == ["a", "b"]


def test_close_last_panel_is_noop(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("close", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 1


def test_undo_redo(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    win.undo()
    assert len(list(iter_panels(win.doc.tree))) == 1
    win.redo()
    assert len(list(iter_panels(win.doc.tree))) == 2


def test_apply_ratios_updates_model(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    win.apply_ratios((), (0.6, 0.4))
    rects = sorted(win.doc.panel_rects(), key=lambda r: r.x_mm)
    assert abs(rects[0].w_mm - (183 - 4) * 0.6) < 1e-6


def test_export_valid_and_copy(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    data = json.loads(win.export_json_text())
    target, constraints, panels, designer = parse_spec(data)
    assert len(panels) == 2 and designer is not None
    win.copy_json()
    from PySide6.QtWidgets import QApplication
    assert json.loads(QApplication.clipboard().text()) == data


def test_save_and_open_roundtrip(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_down", _first_panel(win))
    p = tmp_path / "layout.figspec.json"
    win.save_json(p)
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None  # no error
    assert win2.doc.to_spec_dict() == win.doc.to_spec_dict()


def test_open_without_sidecar_reports_error(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    data = win.doc.to_spec_dict()
    del data["designer"]
    p = tmp_path / "plain.json"
    p.write_text(json.dumps(data))
    err = win.open_json(p)
    assert err is not None and "designer" in err


def test_smoke_flag():
    from figspec_designer.app import main
    assert main(["--smoke"]) == 0
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_main_window.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

`designer/figspec_designer/ui/main_window.py`:
```python
"""Assembles canvas + sidebar + top bar and owns the document/undo state."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QMainWindow,
                               QMessageBox, QApplication, QVBoxLayout, QWidget)
from figspec.spec import Constraints, SpecError, Target
from figspec_designer.document import DesignerDocument, MissingDesignerData
from figspec_designer.model import ops
from figspec_designer.model.history import History
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.canvas import Canvas
from figspec_designer.ui.sidebar import Sidebar
from figspec_designer.ui.toolbar import TopBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FigSpec Designer")
        self.resize(1100, 700)
        self.doc = DesignerDocument.default()
        self.history = History(self.doc.tree)
        self.selected_panel_id: str | None = None

        self.topbar = TopBar()
        self.canvas = Canvas()
        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(260)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.topbar)
        row = QHBoxLayout()
        row.addWidget(self.canvas, stretch=1)
        row.addWidget(self.sidebar)
        outer.addLayout(row, stretch=1)
        self.setCentralWidget(central)

        self.canvas.panel_action.connect(lambda a, pid: self.do_action(a, pid))
        self.canvas.ratios_committed.connect(self.apply_ratios)
        self.topbar.settings_changed.connect(self._on_settings_changed)
        self.topbar.save_requested.connect(self._save_dialog)
        self.topbar.copy_requested.connect(self.copy_json)
        self.topbar.open_requested.connect(self._open_dialog)
        self.sidebar.content_hint_edited.connect(self._on_hint_edited)

        self._make_menus()
        self.refresh()

    # ---- menus ------------------------------------------------------
    def _make_menus(self) -> None:
        def act(menu, text, shortcut, slot):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        file_menu = self.menuBar().addMenu("File")
        act(file_menu, "Open…", "Ctrl+O", self._open_dialog)
        act(file_menu, "Save JSON…", "Ctrl+S", self._save_dialog)
        act(file_menu, "Copy JSON", "Ctrl+Shift+C", self.copy_json)
        edit_menu = self.menuBar().addMenu("Edit")
        act(edit_menu, "Undo", "Ctrl+Z", self.undo)
        act(edit_menu, "Redo", "Ctrl+Shift+Z", self.redo)
        panel_menu = self.menuBar().addMenu("Panel")
        act(panel_menu, "Split Right", "Ctrl+D",
            lambda: self.do_action("split_right", self.selected_panel_id))
        act(panel_menu, "Split Down", "Ctrl+Shift+D",
            lambda: self.do_action("split_down", self.selected_panel_id))
        act(panel_menu, "Delete Panel", "Ctrl+Backspace",
            lambda: self.do_action("close", self.selected_panel_id))

    # ---- state ------------------------------------------------------
    def _push_tree(self, new_tree) -> None:
        self.doc.tree = new_tree
        self.history.push(new_tree)
        self.refresh()

    def refresh(self) -> None:
        self.canvas.set_document(self.doc)
        self.canvas.apply_selection(self.selected_panel_id)
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        pid = self.selected_panel_id
        panels = {p.id: p for p in iter_panels(self.doc.tree)}
        if pid is None or pid not in panels:
            self.selected_panel_id = None
            self.sidebar.clear()
            return
        rect = next(r for r in self.doc.panel_rects() if r.panel_id == pid)
        self.sidebar.show_panel(pid, self.doc.labels()[pid], rect,
                                self.doc.target.dpi, panels[pid].content_hint)

    # ---- actions ----------------------------------------------------
    def do_action(self, action: str, panel_id: str | None = None) -> None:
        if action == "select":
            self.selected_panel_id = panel_id
            self.canvas.apply_selection(panel_id)
            self._refresh_sidebar()
            return
        if panel_id is None:
            self.statusBar().showMessage("Select a panel first", 3000)
            return
        try:
            if action == "split_right":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "right"))
            elif action == "split_down":
                self._push_tree(ops.split_panel(self.doc.tree, panel_id, "down"))
            elif action == "close":
                self._push_tree(ops.close_panel(self.doc.tree, panel_id))
        except ValueError:
            self.statusBar().showMessage("Cannot delete the last panel", 3000)
        except KeyError:
            self.statusBar().showMessage("Panel no longer exists", 3000)

    def apply_ratios(self, path, ratios) -> None:
        self._push_tree(ops.set_ratios(self.doc.tree, tuple(path), tuple(ratios)))

    def undo(self) -> None:
        self.doc.tree = self.history.undo()
        self.refresh()

    def redo(self) -> None:
        self.doc.tree = self.history.redo()
        self.refresh()

    def _on_hint_edited(self, panel_id: str, text: str) -> None:
        try:
            self._push_tree(ops.set_content_hint(self.doc.tree, panel_id, text))
        except KeyError:
            pass

    def _on_settings_changed(self) -> None:
        preset, width, height, dpi, gutter = self.topbar.values()
        self.doc.target = Target(preset, width, height, dpi, gutter)
        self.refresh()

    # ---- export / open ----------------------------------------------
    def export_json_text(self) -> str:
        return self.doc.to_json()

    def copy_json(self) -> None:
        QApplication.clipboard().setText(self.export_json_text())
        self.statusBar().showMessage("figspec.json copied to clipboard", 3000)

    def save_json(self, path) -> None:
        Path(path).write_text(self.export_json_text())

    def open_json(self, path) -> str | None:
        """Returns an error message, or None on success."""
        try:
            data = json.loads(Path(path).read_text())
            self.doc = DesignerDocument.from_spec_dict(data)
        except MissingDesignerData as e:
            return str(e)
        except (SpecError, json.JSONDecodeError, OSError) as e:
            return f"cannot open: {e}"
        self.history = History(self.doc.tree)
        self.selected_panel_id = None
        self.topbar.set_values(self.doc.target.journal_preset,
                               self.doc.target.figure_width_mm,
                               self.doc.target.figure_height_mm,
                               self.doc.target.dpi, self.doc.target.gutter_mm)
        self.refresh()
        return None

    def _save_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save figspec.json", "figspec.json",
                                              "figspec JSON (*.json)")
        if path:
            self.save_json(path)

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open figspec.json", "",
                                              "figspec JSON (*.json)")
        if not path:
            return
        err = self.open_json(path)
        if err and self.isVisible():
            QMessageBox.warning(self, "Cannot open", err)
```

`designer/figspec_designer/app.py`:
```python
"""Application entry point."""
from __future__ import annotations
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    smoke = "--smoke" in argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from figspec_designer.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(argv)
    win = MainWindow()
    win.show()
    if smoke:
        QTimer.singleShot(0, app.quit)
        app.exec()
        return 0
    return app.exec()
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass. Note: `test_smoke_flag` reuses the QApplication pytest-qt created; `app.main` handles that via `QApplication.instance()`.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: main window wiring and app entry"`

---

### Task 12: macOS packaging (icon, PyInstaller spec, build script)

**Files:**
- Create: `designer/packaging/make_icon.py`, `designer/packaging/figspec-designer.spec`, `designer/packaging/build_macos.sh` (chmod +x)

**Interfaces:**
- Consumes: `figspec_designer.__version__`, `app.main --smoke`.
- Produces: `dist/FigSpec Designer.app` + `FigSpec-Designer-<ver>-arm64.dmg`; script flags `--skip-sign` (unsigned local build), `--release` (gh release draft upload). Env contract: `FIGSPEC_SIGN_IDENTITY` (Developer ID Application cert name), `FIGSPEC_NOTARY_PROFILE` (notarytool keychain profile); both required unless `--skip-sign`.

- [ ] **Step 1: Write the icon generator** (`designer/packaging/make_icon.py`)

```python
"""Generate a placeholder app icon (grid glyph) -> AppIcon.icns via iconutil."""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "assets"


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size // 8
    d.rounded_rectangle([m, m, size - m, size - m], radius=size // 6,
                        fill=(15, 77, 146, 255))
    # panel grid glyph: one tall left panel, two stacked right panels
    g = size // 24
    x0, y0, x1, y1 = 2 * m, 2 * m, size - 2 * m, size - 2 * m
    mid_x = (x0 + x1) // 2
    mid_y = (y0 + y1) // 2
    white = (250, 250, 250, 255)
    d.rounded_rectangle([x0, y0, mid_x - g, y1], radius=g, fill=white)
    d.rounded_rectangle([mid_x + g, y0, x1, mid_y - g], radius=g, fill=white)
    d.rounded_rectangle([mid_x + g, mid_y + g, x1, y1], radius=g, fill=white)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        iconset = Path(td) / "AppIcon.iconset"
        iconset.mkdir()
        for pts in (16, 32, 64, 128, 256, 512):
            draw(pts).save(iconset / f"icon_{pts}x{pts}.png")
            draw(pts * 2).save(iconset / f"icon_{pts}x{pts}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset),
                        "-o", str(OUT / "AppIcon.icns")], check=True)
    print(f"wrote {OUT / 'AppIcon.icns'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the PyInstaller spec** (`designer/packaging/figspec-designer.spec`)

```python
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

HERE = Path(SPECPATH)
sys.path.insert(0, str(HERE.parent))
from figspec_designer import __version__

a = Analysis(
    [str(HERE.parent / "figspec_designer" / "app.py")],
    pathex=[str(HERE.parent), str(HERE.parent.parent)],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="FigSpec Designer",
          console=False, target_arch="arm64")
coll = COLLECT(exe, a.binaries, a.datas, name="FigSpec Designer")
app = BUNDLE(
    coll,
    name="FigSpec Designer.app",
    icon=str(HERE / "assets" / "AppIcon.icns"),
    bundle_identifier="com.github.sebdeng.figspec-designer",
    version=__version__,
    info_plist={"NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "12.0"},
)
```

- [ ] **Step 3: Write the build script** (`designer/packaging/build_macos.sh`)

```bash
#!/usr/bin/env bash
# Build, sign, notarize and package FigSpec Designer (arm64).
# Usage: ./build_macos.sh [--skip-sign] [--release]
# Env (required unless --skip-sign):
#   FIGSPEC_SIGN_IDENTITY   e.g. "Developer ID Application: NAME (TEAMID)"
#   FIGSPEC_NOTARY_PROFILE  notarytool keychain profile name
set -euo pipefail
cd "$(dirname "$0")"

SKIP_SIGN=0; RELEASE=0
for arg in "$@"; do
  case "$arg" in
    --skip-sign) SKIP_SIGN=1 ;;
    --release) RELEASE=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' ../figspec_designer/__init__.py)
APP="dist/FigSpec Designer.app"
DMG="FigSpec-Designer-${VERSION}-arm64.dmg"

if [ "$SKIP_SIGN" -eq 0 ]; then
  : "${FIGSPEC_SIGN_IDENTITY:?set FIGSPEC_SIGN_IDENTITY or use --skip-sign}"
  : "${FIGSPEC_NOTARY_PROFILE:?set FIGSPEC_NOTARY_PROFILE or use --skip-sign}"
fi

echo "==> build venv (uv, python 3.11)"
uv venv --python 3.11 build-env --clear
source build-env/bin/activate
uv pip install --quiet ../../ ../ pyinstaller

echo "==> icon"
python make_icon.py

echo "==> pyinstaller"
rm -rf build dist
pyinstaller --noconfirm figspec-designer.spec

echo "==> smoke test"
"./dist/FigSpec Designer/FigSpec Designer" --smoke

if [ "$SKIP_SIGN" -eq 0 ]; then
  echo "==> codesign"
  codesign --deep --force --options runtime --timestamp \
    --sign "$FIGSPEC_SIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict "$APP"

  echo "==> notarize"
  ditto -c -k --keepParent "$APP" "dist/notarize.zip"
  xcrun notarytool submit "dist/notarize.zip" \
    --keychain-profile "$FIGSPEC_NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP"
fi

echo "==> dmg"
rm -f "$DMG"
create-dmg --volname "FigSpec Designer" --window-size 500 320 \
  --icon-size 100 --app-drop-link 350 130 "$DMG" "$APP" \
  || { echo "create-dmg failed (brew install create-dmg)"; exit 1; }

if [ "$RELEASE" -eq 1 ]; then
  gh release create "designer-v${VERSION}" --draft \
    --title "FigSpec Designer ${VERSION}" "$DMG"
fi
echo "done: $DMG"
```

- [ ] **Step 4: Verify unsigned build end-to-end**

Run: `chmod +x designer/packaging/build_macos.sh && cd designer/packaging && ./build_macos.sh --skip-sign; cd ../..`
Expected: script completes; smoke test prints nothing and exits 0; DMG file exists. (Requires `uv` and `create-dmg`; if create-dmg is missing, `brew install create-dmg` first — the .app + smoke test must still pass before that.) If the onefile/onedir smoke binary path differs, check `dist/` layout and fix the script path — do not skip the smoke step.

- [ ] **Step 5: Commit** — `git add designer/packaging && git commit -m "feat: macOS packaging with sign/notarize pipeline"` (assets/AppIcon.icns is generated; add `designer/packaging/assets/` and `designer/packaging/build-env/`, `designer/packaging/build/`, `designer/packaging/dist/`, `*.dmg` to `.gitignore` in the same commit).

---

### Task 13: README updates and final verification

**Files:**
- Modify: `README.md`, `README.zh-CN.md` (add a "FigSpec Designer" section)

- [ ] **Step 1: Add Designer section to both READMEs**

English (`README.md`, after the Checks section; translate faithfully into `README.zh-CN.md` keeping code blocks identical):

````markdown
## FigSpec Designer (macOS app)

A visual layout editor for the other half of the workflow: split a
journal-width canvas into panels, drag gutters with live mm feedback, and
export `figspec.json` (Save or Copy) for your plotting agent. Panels carry
auto reading-order labels (a, b, c…) and per-panel mm / px / figsize values.

Run from source:

```bash
pip install -e designer
python -m figspec_designer
```

Build a signed DMG (needs Apple Developer ID; see
`designer/packaging/build_macos.sh` for the env contract):

```bash
cd designer/packaging && ./build_macos.sh
```
````

- [ ] **Step 2: Full verification**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/pytest designer/tests -q && .venv/bin/python -m pytest --collect-only -q designer/tests | tail -1`
Expected: figspec suite 78 passed; designer suite all passed; collection count matches.

- [ ] **Step 3: Commit** — `git add README.md README.zh-CN.md && git commit -m "docs: designer section in READMEs"`

---

## Self-Review Notes (completed during planning)

- **Spec coverage:** §1 scope → Tasks 7–11 (presets/settings/split/close/drag/undo/labels/hints/export/open) + Task 12 (app identity); §2 architecture → file layout matches exactly, model has zero Qt imports (Tasks 3–6); §3 model semantics → Tasks 3–5 with the spec's exact L-shape ground truth (89.5/57.6/38.4); §4 interaction → Tasks 8, 9, 11 (buttons/shortcuts/snap/⌥/status-bar messaging); §5 export/format → Tasks 2, 7 (sidecar, coordinate note in figspec/spec.py docstring, missing-sidecar error); §6 packaging → Task 12 (codesign/notarytool/staple/create-dmg/env contract/--skip-sign); §7 testing → per-task TDD + offscreen conftest + Task 12 smoke + Task 13 full run; §8 YAGNI → nothing beyond scope planned.
- **Known deviations, intentional:** Copy JSON shortcut ⌘⇧C added (spec lists it as a button; shortcut is free). `LSMinimumSystemVersion 12.0` chosen for arm64-only Qt 6. Drag feedback shows sizes of the two panels adjacent to the dragged handle only (matches spec's "两侧 panel 实时 mm").
- **Type consistency check:** `do_action` signature (Task 11) matches canvas `panel_action` payloads (Task 9) and PanelWidget actions (Task 8); `ratios_committed(tuple, tuple)` matches `apply_ratios(path, ratios)`; `DesignerDocument` API used identically in Tasks 9–11; `snap_ratios` consumed in Task 9 exactly as defined in Task 4.
- **Risk notes for implementers:** offscreen splitter geometry (Task 9 debug note); PyInstaller PySide6 hooks are bundled with PyInstaller ≥6 so no hiddenimports expected — if the smoke test fails on missing Qt plugins, add `--collect-all PySide6` equivalent via spec `hookspath` before weakening anything; Task 7 contains an explicit correction note about panel ordering (use the reading-order sort expression, not label-string sort) — implement the corrected version.
