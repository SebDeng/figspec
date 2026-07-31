# Designer Batch B (期刊感知 + 工具链闭环) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Journal-aware Designer: GUI-integrated PDF lint (dock + background thread), per-journal max-height warnings, panel-label style that follows the journal, and preset provenance tooltips — per the approved spec `docs/superpowers/specs/2026-07-30-designer-batch-b-design.md`.

**Architecture:** All journal data lands in `figspec/presets.py` (three new dicts) with the pure `format_label` helper in `figspec/layout/flatten.py`; `Constraints` gains `panel_label_style`. The Designer consumes them: TopBar warns/tooltips, Canvas + wireframe export format letters, and a new `lint_runner.py` (QThread) + `lint_dock.py` (QDockWidget) pair reuses `figspec.lint`/`figspec.pdf` wholesale — zero new lint logic.

**Tech Stack:** Python 3.13, PySide6, pytest + pytest-qt (`PYTHONPATH=designer QT_QPA_PLATFORM=offscreen`), existing figspec lint stack (pikepdf/pypdfium2/PIL).

## Global Constraints

- `figspec/` stays Qt-free (presets/flatten/spec changes are pure data/functions).
- 兼容铁律: old figspec.json (constraints without `panel_label_style`) parses unchanged, defaulting to `"lowercase"`; internal tree labels and exported spec `panels[].label` stay LOWERCASE a/b/c always — only DISPLAY (canvas letters, sidebar Label row, wireframe export) is formatted.
- MAX_HEIGHT_MM values (spec-fixed, sources already in `docs/journal-figure-specs.md`): nature_single/nature_double 170.0; nature_research_single/nature_research_double 185.0; science_single/science_double 199.0; acs_single/acs_double 232.8; aps_single/aps_double None (no warning).
- PANEL_LABEL_STYLE (spec-fixed): nature_*/nature_research_*/acs_* → `"lowercase"`; science_* → `"uppercase"`; aps_* → `"paren_lower"`.
- Height warning is advisory only (amber styling + tooltip) — never blocks input. `custom` preset never warns.
- Lint dock reuses `figspec.pdf.interpreter.extract`, `figspec.lint.checks.run_checks`/`LintConfig`, `figspec.lint.report.summarize`/`render_json`, `figspec.lint.annotate.annotate` — NO reimplemented checks. Thresholds from the current document: `LintConfig(min_font_pt=constraints.min_font_pt, min_linewidth_pt=constraints.min_linewidth_pt, width_pt=mm_to_pt(target.figure_width_mm))`.
- Lint runs on a QThread; the UI thread never blocks; a running lint disables the menu action; `LintInputError` and unexpected exceptions surface as an in-dock error bar, never a crash.
- UI copy is English (the whole app is English; the spec's Chinese tooltip text is rendered in English — adjudicated deviation).
- Test commands: `.venv/bin/pytest tests/ -q` (138 at start) and `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` (142 at start), smoke `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` exit 0. All stay green.

## File Structure

- `figspec/presets.py` — MAX_HEIGHT_MM, PANEL_LABEL_STYLE, PRESET_SOURCES (modify)
- `figspec/layout/flatten.py` — `format_label` (modify); `designer/figspec_designer/model/flatten.py` shim re-export (modify)
- `figspec/spec.py` — `Constraints.panel_label_style: str = "lowercase"` (modify)
- `docs/journal-figure-specs.md` — append "FigSpec 取值决策" note for MAX_HEIGHT_MM (modify)
- `designer/figspec_designer/ui/toolbar.py` — preset tooltips + `set_height_over_limit` (modify)
- `designer/figspec_designer/ui/main_window.py` — height-warning driver, label-style sync, Lint PDF menu + worker wiring (modify)
- `designer/figspec_designer/ui/canvas.py` — formatted letters (modify)
- `designer/figspec_designer/ui/sidebar.py` — formatted Label row (modify)
- `designer/figspec_designer/ui/preview_export.py` — `label_style` kwarg (modify)
- `designer/figspec_designer/ui/theme.py` — overLimit QSS + lint level colors (modify)
- `designer/figspec_designer/ui/lint_runner.py` — `LintWorker(QThread)` (create)
- `designer/figspec_designer/ui/lint_dock.py` — `LintDock(QDockWidget)` (create)
- Tests: `tests/test_presets_journal.py` (create), `designer/tests/test_batch_b_ui.py` (create)

---

### Task 1: Journal data layer (presets dicts + format_label + Constraints field)

**Files:**
- Modify: `figspec/presets.py`, `figspec/layout/flatten.py`, `figspec/spec.py`, `designer/figspec_designer/model/flatten.py`, `docs/journal-figure-specs.md`
- Test: `tests/test_presets_journal.py`

**Interfaces:**
- Consumes: existing `PRESETS` keys.
- Produces (later tasks rely on these EXACT names):
  - `presets.MAX_HEIGHT_MM: dict[str, float | None]`
  - `presets.PANEL_LABEL_STYLE: dict[str, str]`
  - `presets.PRESET_SOURCES: dict[str, str]`
  - `flatten.format_label(label: str, style: str) -> str`
  - `Constraints.panel_label_style: str = "lowercase"`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_presets_journal.py`:

```python
import pytest

from figspec import presets
from figspec.layout.flatten import format_label
from figspec.spec import Constraints, parse_spec


def test_journal_dicts_cover_every_preset():
    for d in (presets.MAX_HEIGHT_MM, presets.PANEL_LABEL_STYLE,
              presets.PRESET_SOURCES):
        assert set(d) == set(presets.PRESETS)


def test_max_height_values():
    assert presets.MAX_HEIGHT_MM["nature_double"] == 170.0
    assert presets.MAX_HEIGHT_MM["nature_research_double"] == 185.0
    assert presets.MAX_HEIGHT_MM["science_single"] == 199.0
    assert presets.MAX_HEIGHT_MM["acs_double"] == 232.8
    assert presets.MAX_HEIGHT_MM["aps_single"] is None


def test_panel_label_styles():
    assert presets.PANEL_LABEL_STYLE["nature_double"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["nature_research_single"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["acs_single"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["science_double"] == "uppercase"
    assert presets.PANEL_LABEL_STYLE["aps_double"] == "paren_lower"


def test_preset_sources_mention_width():
    for key, text in presets.PRESET_SOURCES.items():
        assert f"{presets.PRESETS[key]:g}" in text, key


def test_format_label():
    assert format_label("a", "lowercase") == "a"
    assert format_label("b", "uppercase") == "B"
    assert format_label("c", "paren_lower") == "(c)"
    assert format_label("aa", "uppercase") == "AA"
    # unknown style falls back to identity, never raises
    assert format_label("a", "bogus") == "a"


def test_constraints_style_default_and_compat():
    assert Constraints().panel_label_style == "lowercase"
    old = {"figspec_version": "0.1",
           "target": {"journal_preset": "custom", "figure_width_mm": 100.0,
                      "figure_height_mm": 60.0},
           "constraints": {"min_font_pt": 5.0, "max_font_pt": 8.0,
                           "min_linewidth_pt": 0.5},
           "panels": []}
    _t, c, _p, _d = parse_spec(old)
    assert c.panel_label_style == "lowercase"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_presets_journal.py -q`
Expected: FAIL (AttributeError / ImportError).

- [ ] **Step 3: Implement**

`figspec/presets.py` — append after `PRESET_CONSTRAINTS`:

```python
# Height ceilings (mm, figure area incl. caption allowance) -- sources and
# the reasoning for each pick are in docs/journal-figure-specs.md
# ("FigSpec 取值决策"). None = publisher states no numeric limit -> no warning.
MAX_HEIGHT_MM: dict[str, float | None] = {
    "nature_single": 170.0,
    "nature_double": 170.0,
    "nature_research_single": 185.0,
    "nature_research_double": 185.0,
    "science_single": 199.0,
    "science_double": 199.0,
    "acs_single": 232.8,
    "acs_double": 232.8,
    "aps_single": None,
    "aps_double": None,
}

# Panel-letter display style per journal family. Internal/spec labels are
# ALWAYS lowercase a/b/c; only the display layer formats them.
PANEL_LABEL_STYLE: dict[str, str] = {
    "nature_single": "lowercase",
    "nature_double": "lowercase",
    "nature_research_single": "lowercase",
    "nature_research_double": "lowercase",
    "science_single": "uppercase",
    "science_double": "uppercase",
    "acs_single": "lowercase",
    "acs_double": "lowercase",
    "aps_single": "paren_lower",
    "aps_double": "paren_lower",
}

# One-line provenance shown as the preset dropdown's item tooltip.
PRESET_SOURCES: dict[str, str] = {
    "nature_single": "89 mm · Nature final-submission guide (nature.com/nature/for-authors)",
    "nature_double": "183 mm · Nature final-submission guide (nature.com/nature/for-authors)",
    "nature_research_single": "88 mm · NRJs guide to preparing final artwork (PDF)",
    "nature_research_double": "180 mm · NRJs guide to preparing final artwork (PDF)",
    "science_single": "90 mm · Science author prep guide 2025 (PDF)",
    "science_double": "183 mm · Science author prep guide 2025 (PDF)",
    "acs_single": "84.7 mm · ACS TOC/abstract graphics guidelines (pubsapp.acs.org)",
    "acs_double": "177.8 mm · ACS TOC/abstract graphics guidelines (pubsapp.acs.org)",
    "aps_single": "85 mm · APS Journals Style Guide Feb 2026 (PDF)",
    "aps_double": "178 mm · APS Journals Style Guide Feb 2026 (PDF)",
}
```

`figspec/layout/flatten.py` — append:

```python
def format_label(label: str, style: str) -> str:
    """Display-format an internal lowercase panel label. Identity for
    unknown styles -- display must never crash over a bad style string."""
    if style == "uppercase":
        return label.upper()
    if style == "paren_lower":
        return f"({label})"
    return label
```

`designer/figspec_designer/model/flatten.py` — add `format_label` to the explicit re-export list.

`figspec/spec.py` — `Constraints` gains (after `min_effective_dpi`):

```python
    panel_label_style: str = "lowercase"
```

`docs/journal-figure-specs.md` — append at the end:

```markdown
## FigSpec 取值决策（MAX_HEIGHT_MM / PANEL_LABEL_STYLE）

- nature_*: 170 mm — formatting-guide §5.9 页深上限（含图注位，247 mm 整页深不用于图）。
- nature_research_*: 185 mm — NRJs final-artwork PDF 中图注 <300 词档的双栏最大高度；取宽松档，tooltip 注明。
- science_*: 199 mm — SciAdv figure guide 推荐上限；Science 旗舰刊无数字，沿用并标注。
- acs_*: 232.8 mm — 660 pt（含图注）换算。
- aps_*: 无数字上限 → None，不警告。
- 标号风格：Nature/NRJ/ACS 小写 a；Science 大写 A；APS (a)（Memo H-18 惯例）。
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_presets_journal.py tests/ -q` → all pass.
Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → no regressions.

- [ ] **Step 5: Commit**

```bash
git add figspec/presets.py figspec/layout/flatten.py figspec/spec.py designer/figspec_designer/model/flatten.py docs/journal-figure-specs.md tests/test_presets_journal.py
git commit -m "feat: journal max-height/label-style/source data + format_label"
```

---

### Task 2: TopBar — height-limit warning + preset provenance tooltips

**Files:**
- Modify: `designer/figspec_designer/ui/toolbar.py`, `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/theme.py`
- Test: `designer/tests/test_batch_b_ui.py` (create)

**Interfaces:**
- Consumes: `presets.MAX_HEIGHT_MM`, `presets.PRESET_SOURCES` (Task 1).
- Produces: `TopBar.set_height_over_limit(over: bool, tooltip: str = "") -> None`; `MainWindow._update_height_warning()` called from `refresh()`.

- [ ] **Step 1: Write the failing tests**

Create `designer/tests/test_batch_b_ui.py`:

```python
"""Batch B UI tests: height warning, preset tooltips, label style, lint dock."""
from PySide6.QtCore import Qt

from figspec_designer.ui.main_window import MainWindow


def test_preset_tooltips(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    combo = win.topbar.preset_combo
    tip = combo.itemData(combo.findText("nature_double"), Qt.ToolTipRole)
    assert tip and "183" in tip
    assert combo.itemData(combo.findText("custom"), Qt.ToolTipRole) in (None, "")


def test_height_warning_flips_property(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    spin = win.topbar.height_spin
    assert spin.property("overLimit") is not True  # 100mm under 170 limit
    spin.setValue(180.0)  # nature_double limit 170
    assert spin.property("overLimit") is True
    assert "170" in spin.toolTip()
    spin.setValue(150.0)
    assert spin.property("overLimit") is not True
    assert spin.toolTip() == ""


def test_no_warning_for_custom_or_aps(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("aps_single")
    win.topbar.height_spin.setValue(500.0)
    assert win.topbar.height_spin.property("overLimit") is not True
    win.topbar.preset_combo.setCurrentText("custom")
    assert win.topbar.height_spin.property("overLimit") is not True
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_b_ui.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`toolbar.py` — in `__init__` right after `self.preset_combo.addItems(...)`:

```python
        for i in range(self.preset_combo.count()):
            key = self.preset_combo.itemText(i)
            if key in presets.PRESET_SOURCES:
                self.preset_combo.setItemData(
                    i, presets.PRESET_SOURCES[key], Qt.ToolTipRole)
```

…and a new method after `set_values`:

```python
    def set_height_over_limit(self, over: bool, tooltip: str = "") -> None:
        """Advisory amber styling on the height spinbox -- never blocks input."""
        from figspec_designer.ui.theme import repolish
        self.height_spin.setProperty("overLimit", bool(over))
        self.height_spin.setToolTip(tooltip if over else "")
        repolish(self.height_spin)
```

`main_window.py` — at the END of `refresh()` (single choke point: settings changes, open, template, undo all funnel through it):

```python
        self._update_height_warning()
```

```python
    def _update_height_warning(self) -> None:
        limit = presets.MAX_HEIGHT_MM.get(self.doc.target.journal_preset)
        height = self.doc.target.figure_height_mm
        over = limit is not None and height > limit
        tip = (f"Exceeds {self.doc.target.journal_preset} max height "
               f"{limit:g} mm (see docs/journal-figure-specs.md)") if over else ""
        self.topbar.set_height_over_limit(over, tip)
```

(`from figspec import presets` — main_window currently imports presets via the designer shim or not at all; check and use `from figspec_designer import presets` to match toolbar.py's idiom.)

`theme.py` — QSS (near the spinbox rules):

```css
QDoubleSpinBox[overLimit="true"] {{
    color: {AMBER_INK}; border: 1px solid {AMBER_BG};
    background: #FBF3E2;
}}
```

- [ ] **Step 4: Run designer tests**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add designer/figspec_designer/ui/toolbar.py designer/figspec_designer/ui/main_window.py designer/figspec_designer/ui/theme.py designer/tests/test_batch_b_ui.py
git commit -m "feat: journal height-limit warning + preset provenance tooltips"
```

---

### Task 3: Panel-label style through the display layer

**Files:**
- Modify: `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/canvas.py`, `designer/figspec_designer/ui/sidebar.py`, `designer/figspec_designer/ui/preview_export.py`
- Test: extend `designer/tests/test_batch_b_ui.py`, extend `tests/test_presets_journal.py`

**Interfaces:**
- Consumes: `format_label`, `PANEL_LABEL_STYLE`, `Constraints.panel_label_style` (Task 1).
- Produces: `render_layout_image(tree, target, *, scale=2, label_style="lowercase")` (additive kwarg; existing callers unchanged); canvas letters and sidebar Label row show formatted labels; `_sync_settings` preserves `min_effective_dpi` and syncs `panel_label_style` from the preset.

- [ ] **Step 1: Write the failing tests**

Append to `designer/tests/test_batch_b_ui.py`:

```python
def test_label_style_follows_preset(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    from figspec.layout.tree import iter_panels
    pid = next(iter_panels(win.doc.tree)).id
    win.topbar.preset_combo.setCurrentText("science_double")
    assert win.doc.constraints.panel_label_style == "uppercase"
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "A"
    win.do_action("select", pid)
    assert win.sidebar.lbl_label.text() == "A"
    win.topbar.preset_combo.setCurrentText("aps_double")
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "(a)"
    # spec export keeps internal lowercase labels regardless of display
    assert win.doc.to_spec_dict()["panels"][0]["label"] == "a"


def test_label_style_survives_spec_roundtrip(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    data = win.doc.to_spec_dict()
    assert data["constraints"]["panel_label_style"] == "uppercase"


def test_sync_settings_preserves_min_effective_dpi(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.doc.constraints.min_effective_dpi = 450
    win.topbar.gutter_spin.setValue(5.0)  # triggers _on_settings_changed
    assert win.doc.constraints.min_effective_dpi == 450
```

Also append to `designer/tests/test_batch_b_ui.py`:

```python
def test_wireframe_export_uses_label_style(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    from figspec_designer.ui.preview_export import render_layout_png
    out = tmp_path / "wf.png"
    assert render_layout_png(win.doc, out) is True
    # can't OCR the letter; assert the code path accepts the style without
    # error and the file is written (letter correctness is pinned by the
    # canvas/sidebar assertions above via the same format_label call)
    assert out.stat().st_size > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_b_ui.py -q`
Expected: FAIL (style not synced; canvas shows "a").

- [ ] **Step 3: Implement**

`main_window.py` `_sync_settings` — the constraints update was converted to a field-preserving `dataclasses.replace(...)` during batch C's final fix wave (it keeps `min_effective_dpi` intact). Extend THAT existing call — do not rebuild `Constraints(...)` positionally:

```python
        style = presets.PANEL_LABEL_STYLE.get(
            preset, self.doc.constraints.panel_label_style)
        self.doc.constraints = replace(
            self.doc.constraints, min_font_pt=min_font, max_font_pt=max_font,
            min_linewidth_pt=min_lw, panel_label_style=style)
```

(Read the current `_sync_settings` first and graft `panel_label_style=style` onto whatever replace/constructor shape is there — preserving `min_effective_dpi` is already handled; your addition must not regress it.)

`canvas.py` `_build_node` PanelNode branch — format the display letter:

```python
            from figspec_designer.model.flatten import format_label
            text = format_label(labels.get(node.id, "?"),
                                self._doc.constraints.panel_label_style)
            w = PanelWidget(node.id, text, ...)
```

(Move the import to the module top with the other model imports.)

`sidebar.py` — no change needed if MainWindow passes the formatted label; in `_refresh_sidebar` the `show_panel` call already passes `self.doc.labels()[pid]` — wrap it:

```python
        from figspec_designer.model.flatten import format_label
        label_text = format_label(self.doc.labels()[pid],
                                  self.doc.constraints.panel_label_style)
```

…and pass `label_text`. (Placement table and Copy JSON stay lowercase — data contexts, per the spec's 恒为小写 rule.)

`preview_export.py`:

```python
def render_layout_image(tree, target, *, scale: int = 2,
                        label_style: str = "lowercase") -> QImage:
```

…and where the letter is drawn: `format_label(labels[r.panel_id], label_style)` (import `format_label` alongside `assign_labels`/`flatten`). `render_layout_png`:

```python
def render_layout_png(doc, path, scale: int = 2) -> bool:
    img = render_layout_image(doc.tree, doc.target, scale=scale,
                              label_style=doc.constraints.panel_label_style)
    return img.save(str(path))
```

Template dialog keeps the default `"lowercase"` previews (targets are archetypes, not journal-bound).

- [ ] **Step 4: Run both suites + smoke**

Run: `.venv/bin/pytest tests/ -q` and `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` and the smoke check → all green.

- [ ] **Step 5: Commit**

```bash
git add designer/figspec_designer/ui/main_window.py designer/figspec_designer/ui/canvas.py designer/figspec_designer/ui/sidebar.py designer/figspec_designer/ui/preview_export.py designer/tests/test_batch_b_ui.py tests/test_presets_journal.py
git commit -m "feat: journal-aware panel-label display style"
```

---

### Task 4: Lint worker thread (`ui/lint_runner.py`)

**Files:**
- Create: `designer/figspec_designer/ui/lint_runner.py`
- Test: extend `designer/tests/test_batch_b_ui.py`

**Interfaces:**
- Consumes: `figspec.pdf.interpreter.extract`/`LintInputError`, `figspec.lint.checks.LintConfig`/`run_checks`, `figspec.lint.report.summarize`/`render_json`, `figspec.lint.annotate.annotate`, `figspec.units.mm_to_pt`.
- Produces (Task 5 relies on): `LintWorker(QThread)` with `__init__(self, pdf_path: str, cfg: LintConfig, out_dir, parent=None)`, signals `finished_ok = Signal(dict, list)` (report dict from `render_json`, list of annotated PNG path strings) and `failed = Signal(str)`.

- [ ] **Step 1: Write the failing tests**

Append to `designer/tests/test_batch_b_ui.py`:

```python
def test_lint_worker_success(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    from figspec.lint.checks import LintConfig
    from figspec.units import mm_to_pt
    from figspec_designer.ui.lint_runner import LintWorker
    paths = write_samples(tmp_path / "samples")
    cfg = LintConfig(min_font_pt=5.0, min_linewidth_pt=0.25,
                     width_pt=mm_to_pt(183.0))
    worker = LintWorker(str(paths["bad"]), cfg, tmp_path / "out")
    with qtbot.waitSignal(worker.finished_ok, timeout=15000) as blocker:
        worker.start()
    report, annotated = blocker.args
    # render_json shape: summary = {"ready": bool, "strict": bool,
    # "counts": {"PASS": n, "WARN": n, "FAIL": n}}; findings list of dicts
    assert set(report["summary"]["counts"]) == {"PASS", "WARN", "FAIL"}
    assert report["findings"] and "check_id" in report["findings"][0]
    assert isinstance(annotated, list)
    worker.wait()


def test_lint_worker_failure(qtbot, tmp_path):
    from figspec.lint.checks import LintConfig
    from figspec_designer.ui.lint_runner import LintWorker
    not_pdf = tmp_path / "x.pdf"
    not_pdf.write_bytes(b"not a pdf")
    worker = LintWorker(str(not_pdf), LintConfig(), tmp_path / "out")
    with qtbot.waitSignal(worker.failed, timeout=15000) as blocker:
        worker.start()
    assert blocker.args[0]  # non-empty error message
    worker.wait()
```

(BEFORE finalizing the first test, check the actual key shape of `render_json`/`summarize` in `figspec/lint/report.py` and adjust the `report["summary"]` assertion to the real structure — the worker must pass `render_json`'s dict through untouched.)

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_b_ui.py -k lint_worker -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `lint_runner.py`**

```python
"""Background PDF lint: QThread wrapper around figspec.lint -- no new logic."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from figspec.lint.annotate import annotate
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.report import render_json, summarize
from figspec.pdf.interpreter import LintInputError, extract


class LintWorker(QThread):
    finished_ok = Signal(dict, list)  # (render_json dict, [annotated PNG paths])
    failed = Signal(str)

    def __init__(self, pdf_path: str, cfg: LintConfig, out_dir, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._cfg = cfg
        self._out_dir = Path(out_dir)

    def run(self) -> None:
        try:
            doc = extract(self._pdf_path)
            findings = run_checks(doc, self._cfg)
            summary = summarize(findings, strict=False)
            report = render_json(self._pdf_path, findings, summary)
            self._out_dir.mkdir(parents=True, exist_ok=True)
            origins = {p.index: (p.origin_x_pt, p.origin_y_pt)
                       for p in doc.pages}
            written = annotate(self._pdf_path, findings,
                               self._out_dir / "lint.png", origins=origins)
        except LintInputError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:  # never crash the app over a bad PDF
            self.failed.emit(f"lint failed: {e}")
            return
        self.finished_ok.emit(report, [str(p) for p in written])
```

(Mirror `figspec/cli.py`'s exact flow — extract → run_checks → summarize → render_json → annotate with per-page origins. If `annotate` returns an empty list for finding-free PDFs, that is fine — the dock shows the "no annotatable violations" placeholder.)

- [ ] **Step 4: Run the new tests**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_b_ui.py -k lint_worker -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add designer/figspec_designer/ui/lint_runner.py designer/tests/test_batch_b_ui.py
git commit -m "feat: background lint worker (QThread over figspec.lint)"
```

---

### Task 5: Lint dock + File > Lint PDF… (⌘L)

**Files:**
- Create: `designer/figspec_designer/ui/lint_dock.py`
- Modify: `designer/figspec_designer/ui/main_window.py`, `designer/figspec_designer/ui/theme.py`
- Test: extend `designer/tests/test_batch_b_ui.py`

**Interfaces:**
- Consumes: `LintWorker` (Task 4), current doc constraints/target for thresholds.
- Produces: `LintDock(QDockWidget)` with `show_running(pdf_path: str)`, `show_report(report: dict, annotated: list[str])`, `show_error(message: str)`, signal `relint_requested = Signal()`; `MainWindow.lint_pdf()` + `_start_lint(path)`.

- [ ] **Step 1: Write the failing tests**

Append to `designer/tests/test_batch_b_ui.py`:

```python
def test_lint_dock_populates(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    paths = write_samples(tmp_path / "samples")
    win._start_lint(str(paths["bad"]))
    assert not win.lint_action.isEnabled()  # disabled while running
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=20000)
    dock = win.lint_dock
    assert dock.findings_tree.topLevelItemCount() > 0
    assert dock.summary_label.text()  # verdict + counts populated


def test_lint_dock_error_path(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    bad = tmp_path / "x.pdf"
    bad.write_bytes(b"nope")
    win._start_lint(str(bad))
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=20000)
    assert win.lint_dock.error_label.isVisibleTo(win.lint_dock)


def test_relint_button_reruns_lint(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    paths = write_samples(tmp_path / "samples")
    win._start_lint(str(paths["good"]))
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=20000)
    first = win.lint_dock.summary_label.text()
    win.lint_dock.btn_relint.click()
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=20000)
    assert win.lint_dock.summary_label.text() == first  # same file, same verdict
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests/test_batch_b_ui.py -k lint_dock -q`
Expected: FAIL.

- [ ] **Step 3: Implement `lint_dock.py`**

```python
"""Right-side dock showing figspec lint results: summary, findings, images."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDockWidget, QLabel, QPushButton, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

_LEVEL_GLYPH = {"FAIL": "●", "WARN": "●", "PASS": "○"}


class LintDock(QDockWidget):
    relint_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Lint", parent)
        self.setObjectName("lintDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("lintSummary")
        self.summary_label.setWordWrap(True)
        lay.addWidget(self.summary_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("lintError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        lay.addWidget(self.error_label)

        self.btn_relint = QPushButton("Re-lint Same File")
        self.btn_relint.clicked.connect(self.relint_requested.emit)
        self.btn_relint.setEnabled(False)
        lay.addWidget(self.btn_relint)

        self.findings_tree = QTreeWidget()
        self.findings_tree.setHeaderHidden(True)
        self.findings_tree.setRootIsDecorated(True)
        lay.addWidget(self.findings_tree, stretch=1)

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_label = QLabel("No annotated pages")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        lay.addWidget(self.image_scroll, stretch=1)

        self.setWidget(body)

    def show_running(self, pdf_path: str) -> None:
        self.error_label.setVisible(False)
        self.btn_relint.setEnabled(False)
        self.summary_label.setText(f"Linting {pdf_path}…")
        self.findings_tree.clear()
        self.image_label.setText("Running…")
        self.image_label.setPixmap(QPixmap())

    def show_report(self, report: dict, annotated: list[str]) -> None:
        self.error_label.setVisible(False)
        self.btn_relint.setEnabled(True)
        s = report["summary"]
        verdict = ("READY FOR SUBMISSION" if s["ready"]
                   else "FIX BEFORE SUBMISSION")  # mirrors report.render_text
        self.summary_label.setText(
            f"{verdict} — " + ", ".join(
                f"{k}: {v}" for k, v in s["counts"].items()))
        self.findings_tree.clear()
        for f in report["findings"]:
            head = QTreeWidgetItem(
                [f"{_LEVEL_GLYPH.get(f['level'], '·')} {f['level']} "
                 f"{f['check_id']}: {f['message']}"])
            head.setData(0, Qt.UserRole, f["level"])
            for ev in f.get("evidence", []):
                head.addChild(QTreeWidgetItem([ev]))
            self.findings_tree.addTopLevelItem(head)
        if annotated:
            self.image_label.setPixmap(QPixmap(annotated[0]))
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No annotatable violations")

    def show_error(self, message: str) -> None:
        self.btn_relint.setEnabled(True)
        self.summary_label.setText("Lint failed")
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.findings_tree.clear()
```

(Key shapes verified against `figspec/lint/report.py`: `report["summary"] = {"ready": bool, "strict": bool, "counts": {"PASS": n, "WARN": n, "FAIL": n}}`; `report["findings"]` items carry `check_id`/`level`/`message`/`evidence`/`page`/`bbox_mm`/`nominal_pt`/`scale`/`effective_pt` — no `verdict` key exists, compute it from `ready`. Colored levels: set a foreground brush per level using theme's DPI_OK/DPI_WARN/DPI_BAD tokens rather than QSS, simplest for tree items.)

`main_window.py`:

```python
        # in __init__, after sidebar setup:
        self.lint_dock = LintDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.lint_dock)
        self.lint_dock.hide()
        self.lint_dock.relint_requested.connect(self._relint)
        self._lint_worker = None
        self._last_lint_path: str | None = None
```

```python
        # in _make_menus, File menu after "Export Layout Preview…":
        self.lint_action = act(file_menu, "Lint PDF…", "Ctrl+L", self.lint_pdf)
```

```python
    def lint_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Lint a finished PDF", "",
                                              "PDF (*.pdf)")
        if path:
            self._start_lint(path)

    def _relint(self) -> None:
        if self._last_lint_path:
            self._start_lint(self._last_lint_path)

    def _start_lint(self, path: str) -> None:
        from figspec.lint.checks import LintConfig
        from figspec.units import mm_to_pt
        from figspec_designer.ui.lint_runner import LintWorker
        import tempfile
        self._last_lint_path = path
        cfg = LintConfig(
            min_font_pt=self.doc.constraints.min_font_pt,
            min_linewidth_pt=self.doc.constraints.min_linewidth_pt,
            width_pt=mm_to_pt(self.doc.target.figure_width_mm))
        out_dir = tempfile.mkdtemp(prefix="figspec-lint-")
        self.lint_action.setEnabled(False)
        self.statusBar().showMessage(f"Linting {path}…")
        self.lint_dock.show_running(path)
        self.lint_dock.show()
        self._lint_worker = LintWorker(path, cfg, out_dir, parent=self)
        self._lint_worker.finished_ok.connect(self._on_lint_done)
        self._lint_worker.failed.connect(self._on_lint_failed)
        self._lint_worker.start()

    def _on_lint_done(self, report: dict, annotated: list) -> None:
        self.lint_action.setEnabled(True)
        self.statusBar().showMessage("Lint finished", 3000)
        self.lint_dock.show_report(report, annotated)

    def _on_lint_failed(self, message: str) -> None:
        self.lint_action.setEnabled(True)
        self.statusBar().showMessage("Lint failed", 3000)
        self.lint_dock.show_error(message)
```

`theme.py` — QSS additions: `#lintError { color: <red token>; }`, `#lintSummary { font-weight: 600; }` following existing idiom.

- [ ] **Step 4: Run both suites + smoke**

All three commands green.

- [ ] **Step 5: Commit**

```bash
git add designer/figspec_designer/ui/lint_dock.py designer/figspec_designer/ui/main_window.py designer/figspec_designer/ui/theme.py designer/tests/test_batch_b_ui.py
git commit -m "feat: in-app PDF lint dock with background worker"
```

---

## Verification (whole batch)

1. `.venv/bin/pytest tests/ -q` green; `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/pytest designer/tests -q` green; smoke exit 0.
2. Controller visual check: screenshot with science preset (letters "A"), height 180 on nature_double (amber spin), lint dock populated from the synthetic bad.pdf.
