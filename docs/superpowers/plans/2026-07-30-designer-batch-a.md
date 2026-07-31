# Designer Batch A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the six baseline-operation feature groups from the batch A spec: N-way splits/equalize, editable sidebar geometry + placement table, aspect display/square/soft-lock, dirty-state file lifecycle, panel swap, min-size guard + keyboard nudge.

**Architecture:** All geometry logic lands as pure functions in `figspec/layout/ops.py` (tested without Qt); the UI layers call them. PanelNode gains an optional `aspect_lock` field (sidecar-serialized). File-lifecycle state (dirty/current path/recents) lives in MainWindow with QSettings persistence.

**Tech Stack:** existing figspec/PySide6 codebase; no new dependencies.

## Global Constraints

- Spec: docs/superpowers/specs/2026-07-30-designer-batch-a-design.md — its semantics govern (split_panel_n distribution, set_panel_size nearest-adjustable-ancestor, 5mm guard = MIN_PANEL_MM constant, soft aspect lock is indicator-only, ⌘S silent-save semantics, 5-entry recents).
- MIN_PANEL_MM = 5.0 defined once in `figspec/layout/ops.py`; every command-style op raises ValueError when violated; drag-commit clamps instead (canvas snap already bounds — extend commit clamp).
- PanelNode gains `aspect_lock: float | None = None`; tree to_dict/from_dict serialize it when not None; all existing dict fixtures stay valid (missing key → None).
- Frozen surfaces: existing signals/attribute names; existing 104 figspec + 74 designer tests pass unmodified EXCEPT tests that construct PanelNode positionally with content_hint (verify none break — aspect_lock is keyword-with-default after content_hint).
- Tests from repo root: `.venv/bin/pytest tests/ -q` and `.venv/bin/pytest designer/tests -q` (run separately).
- TDD RED-first for every new behavior.

---

### Task 1: Model layer — split_n, equalize, swap, set_panel_size, guard, aspect_lock

**Files:**
- Modify: `figspec/layout/tree.py` (PanelNode field), `figspec/layout/ops.py`
- Test: `tests/test_layout_batch_a.py`

**Interfaces (produced, consumed by Tasks 2-4):**
- `tree.PanelNode(id, content_hint="", aspect_lock=None)`; to_dict emits `"aspect_lock"` only when not None; from_dict reads `d.get("aspect_lock")`.
- `ops.MIN_PANEL_MM = 5.0`
- `ops.split_panel_n(root, panel_id, direction, n) -> Node` — ValueError unless 2 ≤ n ≤ 8; matching-orientation parent → replace target with n panels sharing its ratio equally; else wrap into SplitNode(orient, n equal ratios, (target, new×(n−1))).
- `ops.equalize_siblings(root, panel_id) -> Node` — parent SplitNode ratios → uniform; panel at root (no parent) → ValueError("panel has no siblings").
- `ops.swap_panels(root, id_a, id_b) -> Node` — swap the two PanelNode objects' positions; KeyError if either missing, ValueError if identical.
- `ops.set_panel_size(root, panel_id, axis, size_mm, page_w_mm, page_h_mm, gutter_mm) -> Node` — axis ∈ "w"|"h"; walks from root tracking each node's rect (same math as flatten); finds the DEEPEST ancestor SplitNode whose orientation controls that axis for the target ("row" controls w, "column" controls h) and which has ≥2 children; recomputes that split's ratios so target's subtree gets `size_mm` along the axis, scaling sibling ratios proportionally to fill the remainder; ValueError("axis not adjustable") when no such ancestor; ValueError when target or any sibling would fall below MIN_PANEL_MM.
- `ops.snap_ratios` unchanged.

- [ ] **Step 1: Write the failing tests** (`tests/test_layout_batch_a.py`)

```python
import pytest
from figspec.layout.tree import PanelNode, SplitNode, from_dict, to_dict
from figspec.layout.flatten import flatten
from figspec.layout.ops import (MIN_PANEL_MM, equalize_siblings, set_panel_size,
                                split_panel_n, swap_panels)

A, B, C = PanelNode("A"), PanelNode("B"), PanelNode("C")


def _rects(tree, w=183.0, h=100.0, g=4.0):
    return {r.panel_id: r for r in flatten(tree, w, h, g)}


def test_split_n_wraps_into_equal_children():
    out = split_panel_n(A, "A", "right", 3)
    assert isinstance(out, SplitNode) and out.orientation == "row"
    assert len(out.children) == 3
    assert out.ratios == pytest.approx((1 / 3, 1 / 3, 1 / 3))
    assert out.children[0] == A


def test_split_n_inlines_on_matching_parent():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = split_panel_n(root, "B", "right", 3)
    assert len(out.children) == 4
    assert out.ratios == pytest.approx((0.5, 0.5 / 3, 0.5 / 3, 0.5 / 3))


def test_split_n_bounds():
    with pytest.raises(ValueError):
        split_panel_n(A, "A", "right", 1)
    with pytest.raises(ValueError):
        split_panel_n(A, "A", "right", 9)


def test_split_n_min_size_guard():
    # 183mm page: 12-way... n max is 8; craft narrow: wrap A(10mm wide) — parent
    root = SplitNode("row", (10 / 179, 169 / 179), (A, B))  # A ~10mm on 183/4 page
    with pytest.raises(ValueError):
        # A is ~10mm; splitting into 8 → ~0.7mm children
        split_panel_n(root, "A", "right", 8)


def test_equalize_siblings():
    root = SplitNode("row", (0.7, 0.2, 0.1), (A, B, C))
    out = equalize_siblings(root, "B")
    assert out.ratios == pytest.approx((1 / 3, 1 / 3, 1 / 3))
    with pytest.raises(ValueError):
        equalize_siblings(A, "A")


def test_swap_panels_preserves_fields():
    b2 = PanelNode("B", content_hint="hero", aspect_lock=1.0)
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (b2, C))))
    out = swap_panels(root, "A", "B")
    assert out.children[0].id == "B" and out.children[0].content_hint == "hero"
    assert out.children[0].aspect_lock == 1.0
    inner = out.children[1].children[0]
    assert inner.id == "A"
    with pytest.raises(KeyError):
        swap_panels(root, "A", "zz")
    with pytest.raises(ValueError):
        swap_panels(root, "A", "A")


def test_set_panel_size_width():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = set_panel_size(root, "A", "w", 100.0, 183.0, 100.0, 4.0)
    r = _rects(out)
    assert r["A"].w_mm == pytest.approx(100.0)
    assert r["B"].w_mm == pytest.approx(79.0)  # 179 - 100


def test_set_panel_size_nested_height():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    out = set_panel_size(root, "B", "h", 60.0, 183.0, 100.0, 4.0)
    r = _rects(out)
    assert r["B"].h_mm == pytest.approx(60.0)
    assert r["C"].h_mm == pytest.approx(36.0)  # 96 - 60


def test_set_panel_size_not_adjustable():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    with pytest.raises(ValueError, match="not adjustable"):
        set_panel_size(root, "A", "h", 50.0, 183.0, 100.0, 4.0)  # h fixed by page


def test_set_panel_size_guard():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    with pytest.raises(ValueError):
        set_panel_size(root, "A", "w", 176.0, 183.0, 100.0, 4.0)  # B -> 3mm


def test_aspect_lock_roundtrip():
    p = PanelNode("p", aspect_lock=1.5)
    d = to_dict(p)
    assert d["aspect_lock"] == 1.5
    assert from_dict(d).aspect_lock == 1.5
    d2 = to_dict(PanelNode("q"))
    assert "aspect_lock" not in d2
    assert from_dict(d2).aspect_lock is None
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_layout_batch_a.py -q` → ImportError.

- [ ] **Step 3: Implement**

`figspec/layout/tree.py` — PanelNode:
```python
@dataclass(frozen=True)
class PanelNode:
    id: str
    content_hint: str = ""
    aspect_lock: float | None = None
```
to_dict panel branch:
```python
    if isinstance(node, PanelNode):
        d = {"type": "panel", "id": node.id, "content_hint": node.content_hint}
        if node.aspect_lock is not None:
            d["aspect_lock"] = node.aspect_lock
        return d
```
from_dict panel branch adds `aspect_lock=d.get("aspect_lock")`.

`figspec/layout/ops.py` — add:
```python
MIN_PANEL_MM = 5.0


def split_panel_n(root: Node, panel_id: str, direction: str, n: int) -> Node:
    if not 2 <= n <= 8:
        raise ValueError(f"n must be between 2 and 8, got {n}")
    if direction not in _ORIENT:
        raise ValueError(f"direction must be right|down, got {direction!r}")
    orient = _ORIENT[direction]

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id != panel_id:
                return node
            children = (node,) + tuple(new_panel() for _ in range(n - 1))
            return SplitNode(orient, tuple(1.0 / n for _ in range(n)), children)
        children: list[Node] = []
        ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            if (isinstance(child, PanelNode) and child.id == panel_id
                    and node.orientation == orient):
                children.append(child)
                children.extend(new_panel() for _ in range(n - 1))
                ratios.extend([ratio / n] * n)
            else:
                children.append(rec(child))
                ratios.append(ratio)
        if len(children) == len(node.children) and \
                all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, tuple(ratios), tuple(children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def equalize_siblings(root: Node, panel_id: str) -> Node:
    if isinstance(root, PanelNode):
        if root.id == panel_id:
            raise ValueError("panel has no siblings")
        raise KeyError(panel_id)

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            return node
        if any(isinstance(c, PanelNode) and c.id == panel_id
               for c in node.children):
            n = len(node.children)
            return SplitNode(node.orientation, tuple(1.0 / n for _ in range(n)),
                             node.children)
        children = tuple(rec(c) for c in node.children)
        if all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, node.ratios, children)

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def swap_panels(root: Node, id_a: str, id_b: str) -> Node:
    if id_a == id_b:
        raise ValueError("cannot swap a panel with itself")
    found = {p.id for p in _iter_panels(root)}
    if id_a not in found or id_b not in found:
        missing = {id_a, id_b} - found
        raise KeyError(", ".join(sorted(missing)))
    lookup = {p.id: p for p in _iter_panels(root)}

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == id_a:
                return lookup[id_b]
            if node.id == id_b:
                return lookup[id_a]
            return node
        return SplitNode(node.orientation, node.ratios,
                         tuple(rec(c) for c in node.children))

    return rec(root)


def _iter_panels(node: Node):
    from figspec.layout.tree import iter_panels
    return iter_panels(node)


def set_panel_size(root: Node, panel_id: str, axis: str, size_mm: float,
                   page_w_mm: float, page_h_mm: float, gutter_mm: float) -> Node:
    if axis not in ("w", "h"):
        raise ValueError(f"axis must be 'w' or 'h', got {axis!r}")
    controlling = "row" if axis == "w" else "column"
    target_path: list[int] | None = None

    def find(node: Node, path: list[int]) -> None:
        nonlocal target_path
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                target_path = list(path)
            return
        for i, child in enumerate(node.children):
            find(child, path + [i])

    find(root, [])
    if target_path is None:
        raise KeyError(panel_id)

    # deepest ancestor split controlling this axis
    best: tuple[list[int], int] | None = None  # (split path, child index within it)
    node: Node = root
    for depth, idx in enumerate(target_path):
        assert isinstance(node, SplitNode)
        if node.orientation == controlling and len(node.children) >= 2:
            best = (target_path[:depth], idx)
        node = node.children[idx]
    if best is None:
        raise ValueError(f"axis {axis!r} not adjustable for this panel")
    split_path, child_idx = best

    # available mm along the axis at that split = its rect extent minus gutters
    rect_w, rect_h = page_w_mm, page_h_mm
    node = root
    for idx in split_path:
        assert isinstance(node, SplitNode)
        n = len(node.children)
        if node.orientation == "row":
            avail = rect_w - (n - 1) * gutter_mm
            rect_w = avail * node.ratios[idx]
        else:
            avail = rect_h - (n - 1) * gutter_mm
            rect_h = avail * node.ratios[idx]
        node = node.children[idx]
    assert isinstance(node, SplitNode)
    n = len(node.children)
    avail = (rect_w if controlling == "row" else rect_h) - (n - 1) * gutter_mm

    if not MIN_PANEL_MM <= size_mm <= avail - MIN_PANEL_MM * (n - 1):
        raise ValueError(
            f"size {size_mm:g} mm out of range ({MIN_PANEL_MM:g}–"
            f"{avail - MIN_PANEL_MM * (n - 1):g} mm here)")
    remainder = avail - size_mm
    old_others = sum(r for i, r in enumerate(node.ratios) if i != child_idx)
    new_ratios = []
    for i, r in enumerate(node.ratios):
        if i == child_idx:
            new_ratios.append(size_mm / avail)
        else:
            share = (r / old_others) if old_others > 0 else 1.0 / (n - 1)
            new_ratios.append(remainder * share / avail)
    if any(nr * avail < MIN_PANEL_MM - 1e-9 for nr in new_ratios):
        raise ValueError("adjustment would shrink a sibling below 5 mm")
    return set_ratios(root, tuple(split_path), tuple(new_ratios))
```

Note the sibling-share subtlety: `set_panel_size` adjusts the CONTROLLING split's direct children; the target's entry there may be a subtree containing the target — that is correct per spec ("target's subtree gets size_mm along the axis").

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/ -q` (all green incl. new) AND `.venv/bin/pytest designer/tests -q` (74 unmodified).

- [ ] **Step 5: Commit** — `git add figspec tests && git commit -m "feat: batch-a layout ops (split-n, equalize, swap, set-size, guard)"`

---

### Task 2: Sidebar geometry editing + placement table + aspect UI

**Files:**
- Modify: `designer/figspec_designer/ui/sidebar.py`, `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/panel_widget.py`, `designer/figspec_designer/ui/theme.py`
- Test: `designer/tests/test_batch_a_ui.py` (new)

**Interfaces:**
- Sidebar reworked rows: `x/y` read-only fieldValue labels (`lbl_xy`, text "x, y" 1dp), editable `spin_w`/`spin_h` (QDoubleSpinBox mm 1dp, range 5–600) replacing lbl_mm (keep `lbl_mm` REMOVED — update the two existing tests that reference lbl_mm: test_sidebar_shows_values and test_sidebar_theme_hooks — this is the ONE sanctioned existing-test change set, keep semantics: assert spin values instead), `lbl_aspect`, `btn_square` ("Make Square"), `chk_aspect_lock`; Signals: `size_edited = Signal(str, str, float)` (panel_id, axis, mm), `square_requested = Signal(str)`, `aspect_lock_toggled = Signal(str, object)` (panel_id, float|None), `placement_copy_requested = Signal()`.
- MainWindow handlers: `_on_size_edited` → ops.set_panel_size(with doc target dims) → push tree (ValueError → statusbar); `_on_square` → set_panel_size(axis "h", size=current w) fallback statusbar; `_on_aspect_lock` → ops.set_content... no: new tree via dataclasses.replace? aspect_lock lives on PanelNode → add tiny model helper INLINE via ops.set_content_hint pattern: implement `ops.set_aspect_lock(root, panel_id, value)` in Task 2 (same shape as set_content_hint; add pure test in designer suite file or figspec file — put in tests/test_layout_batch_a.py addition allowed here); `copy_placement_table()` builds TSV from doc.panel_rects()+labels → clipboard.
- PanelWidget: amber badge QLabel objectName `aspectBadge` top-left, visible only when `aspect_lock` set AND |current−lock|/lock > 0.02 (canvas passes state on build); theme QSS `#aspectBadge` amber chip.
- Canvas `_build_node` passes aspect violation flag: canvas computes rect aspect from doc.panel_rects().

- [ ] **Step 1: failing tests** (`designer/tests/test_batch_a_ui.py`)

```python
import pytest
from PySide6.QtWidgets import QApplication
from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def _win(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    first = next(iter_panels(win.doc.tree)).id
    win.do_action("split_right", first)
    return win, first


def test_sidebar_size_edit_resizes(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.spin_w.setValue(100.0)
    win.sidebar.spin_w.editingFinished.emit()
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].w_mm == pytest.approx(100.0)


def test_sidebar_shows_position_and_aspect(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    assert win.sidebar.lbl_xy.text().startswith("0.0, 0.0")
    assert ":" in win.sidebar.lbl_aspect.text() or "." in win.sidebar.lbl_aspect.text()


def test_make_square(qtbot):
    win, first = _win(qtbot)
    win.do_action("split_down", [p.id for p in iter_panels(win.doc.tree)
                                 if p.id != first][0])
    win.do_action("select", first)
    win.sidebar.btn_square.click()
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].h_mm == pytest.approx(rects[first].w_mm, abs=0.05)


def test_placement_table(qtbot):
    win, first = _win(qtbot)
    win.copy_placement_table()
    text = QApplication.clipboard().text()
    lines = text.strip().split("\n")
    assert lines[0] == "label\tx_mm\ty_mm\tw_mm\th_mm"
    assert len(lines) == 3  # header + 2 panels
    assert lines[1].startswith("a\t0.00\t0.00\t")


def test_aspect_lock_roundtrips_via_export(qtbot):
    win, first = _win(qtbot)
    win.do_action("select", first)
    win.sidebar.chk_aspect_lock.setChecked(True)
    tree_panel = next(p for p in iter_panels(win.doc.tree) if p.id == first)
    assert tree_panel.aspect_lock is not None
```

- [ ] **Step 2: RED** — new file fails on missing attributes.

- [ ] **Step 3: Implement** per Interfaces. Key code:

`ops.set_aspect_lock` (figspec/layout/ops.py, mirrors set_content_hint):
```python
def set_aspect_lock(root: Node, panel_id: str, value: float | None) -> Node:
    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                return replace(node, aspect_lock=value)
            return node
        children = tuple(rec(c) for c in node.children)
        if all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, node.ratios, children)
    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out
```
Sidebar: replace the Size row with two spinboxes (blockSignals during show_panel; emit size_edited on editingFinished only when value changed vs shown); disable each spinbox when MainWindow marks that axis non-adjustable (MainWindow probes by calling set_panel_size in a try/except on the CURRENT tree without pushing — helper `_axis_adjustable(pid, axis) -> bool`).
MainWindow `copy_placement_table`:
```python
    def copy_placement_table(self) -> None:
        labels = self.doc.labels()
        rows = ["label\tx_mm\ty_mm\tw_mm\th_mm"]
        for rect in sorted(self.doc.panel_rects(),
                           key=lambda r: (round(r.y_mm, 1), r.x_mm)):
            rows.append(f"{labels[rect.panel_id]}\t{rect.x_mm:.2f}\t"
                        f"{rect.y_mm:.2f}\t{rect.w_mm:.2f}\t{rect.h_mm:.2f}")
        QApplication.clipboard().setText("\n".join(rows) + "\n")
        self.statusBar().showMessage("Placement table copied", 3000)
```
File menu gains "Copy Placement Table". Update the two lbl_mm-referencing tests (values → spin_w/spin_h assertions, same semantics; report exact edits).

- [ ] **Step 4: GREEN** both suites (report updated assertions).
- [ ] **Step 5: Commit** — `git add figspec designer tests && git commit -m "feat: editable sidebar geometry, placement table, aspect tools"`

---

### Task 3: File lifecycle — dirty state, close guard, save semantics, recents, restore

**Files:**
- Modify: `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/app.py` (restore hook if needed)
- Test: append to `designer/tests/test_batch_a_ui.py`

**Interfaces:**
- MainWindow: `current_path: Path | None`, `dirty: bool`; `_mark_dirty()` called from _push_tree and _on_settings_changed; title updates `"{name}{' •' if dirty} — FigSpec Designer"`; `save()` (⌘S: current_path ? save_json+clear dirty : save_as dialog), `save_as()` (⇧⌘S); closeEvent → QMessageBox Save/Discard/Cancel when dirty (Save routes through save(); Cancel ignores event); `_add_recent(path)` (QSettings "recent_files", max 5, deduped, most-recent first) on open/save; File > Open Recent submenu rebuilt on menu aboutToShow + Clear Menu; startup: QSettings "last_file" → open_json if exists (in __init__, after wiring, guarded).
- Testability: dialogs must be bypassable — closeEvent logic factored as `confirm_discard() -> bool` (monkeypatchable); save() with no path and no dialog-available returns False in tests via injectable `_ask_save_path()`.

- [ ] **Step 1: failing tests** (append)

```python
def test_dirty_flag_and_title(qtbot, tmp_path):
    win, first = _win(qtbot)
    assert win.dirty is True  # split marked dirty
    p = tmp_path / "f.figspec.json"
    win.save_json(p)  # low-level write does NOT manage state
    win.current_path = p
    win.save()
    assert win.dirty is False
    assert "•" not in win.windowTitle()
    win.do_action("split_down", first)
    assert win.dirty is True and "•" in win.windowTitle()


def test_save_silent_with_path(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    assert win.save() is True
    assert p.exists()


def test_recent_files_tracked(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    win.save()
    assert str(p) in win.recent_files()


def test_open_marks_clean_and_recent(qtbot, tmp_path):
    win, _ = _win(qtbot)
    p = tmp_path / "f.figspec.json"
    win.current_path = p
    win.save()
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None
    assert win2.dirty is False and win2.current_path == p
```

- [ ] **Step 2: RED.** Note QSettings pollution: tests must isolate — set `QSettings.setDefaultFormat`/org per-test? Simplest: MainWindow reads settings via `self._settings()` helper returning QSettings("figspec", "designer"); tests monkeypatch it to a QSettings pointed at tmp file (`QSettings(str(tmp_path/'s.ini'), QSettings.IniFormat)`). Add fixture in the test file that patches `MainWindow._settings` BEFORE constructing windows (autouse within this module).

- [ ] **Step 3: Implement** per Interfaces (open_json sets current_path/clear dirty/_add_recent; save() writes via save_json then clears dirty + registers recent; title refresh in one `_refresh_title()`; startup-restore reads last_file inside __init__ guarded by `if restore` param default True — tests construct MainWindow(restore=False)? Simpler: startup restore ONLY in app.main (calls win.open_json(last) after construction) so tests are unaffected — choose this).

- [ ] **Step 4: GREEN** both suites.
- [ ] **Step 5: Commit** — `git add designer && git commit -m "feat: file lifecycle (dirty state, save semantics, recents, restore)"`

---

### Task 4: Split-N/equalize/swap/nudge wiring + drag clamp guard

**Files:**
- Modify: `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/panel_widget.py` (context menu), `designer/figspec_designer/ui/canvas.py` (commit clamp)
- Test: append to `designer/tests/test_batch_a_ui.py`

**Interfaces:**
- Panel context menu (PanelWidget contextMenuEvent → emits action strings through the existing `action` signal): "split_right_n"/"split_down_n" (MainWindow prompts N via QInputDialog.getInt bypassable helper `_ask_n() -> int|None`), "equalize", "swap". Menu items also in the Panel menubar menu.
- MainWindow.do_action gains cases: split_right_n/split_down_n (uses ops.split_panel_n), equalize (ops.equalize_siblings), swap (enters swap mode: `self._swap_pending = panel_id`, statusbar prompt; next "select" action with different id executes ops.swap_panels then clears; Esc via keyPressEvent clears).
- Keyboard nudge: MainWindow keyPressEvent — with selected panel, ⌘+arrows → set_panel_size(current±0.5mm) (⇧⌘ = 2mm); errors → statusbar, no crash.
- Canvas.commit_splitter clamp: after computing mm sizes, clamp each child to ≥ MIN_PANEL_MM before emitting (renormalize), guaranteeing drags cannot produce <5mm panels.

- [ ] **Step 1: failing tests** (append)

```python
def test_split_n_via_action(qtbot, monkeypatch):
    win, first = _win(qtbot)
    monkeypatch.setattr(win, "_ask_n", lambda: 3)
    win.do_action("split_right_n", first)
    assert len(list(iter_panels(win.doc.tree))) == 4  # 2 before + 2 added


def test_equalize_via_action(qtbot, monkeypatch):
    win, first = _win(qtbot)
    monkeypatch.setattr(win, "_ask_n", lambda: 3)
    win.do_action("split_right_n", first)
    win.do_action("equalize", first)
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    widths = sorted(round(r.w_mm, 1) for r in rects.values())
    assert len(set(widths[:3])) == 1  # the three split siblings equal


def test_swap_flow(qtbot):
    win, first = _win(qtbot)
    other = [p.id for p in iter_panels(win.doc.tree) if p.id != first][0]
    win.do_action("swap", first)
    win.do_action("select", other)
    labels = win.doc.labels()
    rects = {r.panel_id: r for r in win.doc.panel_rects()}
    assert rects[first].x_mm > rects[other].x_mm  # positions exchanged


def test_nudge_shortcut(qtbot):
    from PySide6.QtCore import Qt
    win, first = _win(qtbot)
    win.do_action("select", first)
    before = {r.panel_id: r for r in win.doc.panel_rects()}[first].w_mm
    qtbot.keyClick(win, Qt.Key_Right, Qt.ControlModifier)
    after = {r.panel_id: r for r in win.doc.panel_rects()}[first].w_mm
    assert after == pytest.approx(before + 0.5)
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** per Interfaces (context menu emits through existing signal; swap-mode state on MainWindow; commit clamp in canvas as pure adjustment before ops.snap_ratios).
- [ ] **Step 4: GREEN** both suites; run `--smoke`.
- [ ] **Step 5: Commit** — `git add designer figspec && git commit -m "feat: split-n, equalize, swap mode, nudge, drag min-size clamp"`

---

### Task 5: Verification + visual capture

- [ ] **Step 1:** `.venv/bin/pytest tests/ -q` + `.venv/bin/pytest designer/tests -q` + `--smoke` all green.
- [ ] **Step 2:** offscreen screenshot (same recipe as the restyle plan, with a 3-way split + selection showing the new sidebar) saved to the scratchpad; controller shows the user.
- [ ] **Step 3:** report counts + screenshot path (no commit).

---

## Self-Review Notes

- Spec A1→Task 1+4; A2→Tasks 1 (set_panel_size)+2; A3→Tasks 1 (field)+2 (UI); A4→Task 3; A5→Tasks 1+4; A6→Tasks 1 (guard)+4 (clamp+nudge).
- Sanctioned existing-test edits: only the two sidebar lbl_mm references (Task 2) — everything else frozen.
- Type consistency: ops signatures match call sites; set_panel_size(page dims from doc.target) wiring in Tasks 2/4; MIN_PANEL_MM single-sourced.
- Risks flagged: QSettings isolation fixture (Task 3), spinbox editingFinished emission discipline (Task 2), swap-mode statefulness (Task 4 keeps it one field + Esc).
