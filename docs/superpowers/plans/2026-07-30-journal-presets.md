# Journal Presets Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct/extend journal width presets with verified primary-source values, add per-preset constraint defaults wired into the TopBar, and land the fully-sourced reference doc.

**Architecture:** Data lives in `presets.py` (PRESETS + new PRESET_CONSTRAINTS); TopBar's preset handler applies both width and constraints in one signal batch; the evidence lives in `docs/journal-figure-specs.md` generated from the research workflow's structured output.

**Tech Stack:** Existing PySide6 app; no new dependencies.

## Global Constraints

- New PRESETS values exactly: nature_single 89.0, nature_double 183.0, nature_research_single 88.0, nature_research_double 180.0, science_single 90.0, science_double 183.0, acs_single 84.7, acs_double 177.8, aps_single 85.0, aps_double 178.0.
- PRESET_CONSTRAINTS exactly: nature_*/nature_research_* → 5.0/7.0/0.25; science_* → 5.0/10.0/0.5; acs_* → 4.5/8.0/0.5; aps_* → 8.0/10.0/0.5 (keys min_font_pt/max_font_pt/min_linewidth_pt).
- Preset selection writes width + three constraint spins in ONE blocked batch then a single settings_changed; "custom" unlocks width only, constraints untouched.
- MainWindow init syncs doc from topbar once (initial doc.constraints must match the initial preset's constraints).
- Existing tests: only numeric assertions tied to OLD preset/constraint values may be updated (semantics frozen); everything else untouched.
- Research data source (75 KB JSON): `/private/tmp/claude-501/-Users-dengyusong-Desktop-FigSpec/7a600979-8175-48cb-8367-190e54e506f3/tasks/w2uwic4lq.output` — structure `{"result": {"results": [4 publisher objects], "verification": {...}}}`.
- Tests: `.venv/bin/pytest designer/tests -q` from repo root.

---

### Task 1: Preset data + sourced reference doc

**Files:**
- Modify: `designer/figspec_designer/presets.py`
- Create: `docs/journal-figure-specs.md`
- Test: append to `designer/tests/test_sidebar_toolbar.py`

**Interfaces:**
- Produces: `PRESETS` (10 keys, values above), `PRESET_CONSTRAINTS: dict[str, dict[str, float]]` (same 10 keys).

- [ ] **Step 1: Write the failing test** (append to `designer/tests/test_sidebar_toolbar.py`)

```python
def test_preset_values_corrected():
    from figspec_designer import presets
    assert presets.PRESETS["acs_single"] == 84.7
    assert presets.PRESETS["acs_double"] == 177.8
    assert presets.PRESETS["aps_single"] == 85.0
    assert presets.PRESETS["aps_double"] == 178.0
    assert presets.PRESETS["nature_research_single"] == 88.0
    assert presets.PRESETS["science_double"] == 183.0


def test_all_presets_have_constraints():
    from figspec_designer import presets
    assert set(presets.PRESET_CONSTRAINTS) == set(presets.PRESETS)
    assert presets.PRESET_CONSTRAINTS["nature_single"] == {
        "min_font_pt": 5.0, "max_font_pt": 7.0, "min_linewidth_pt": 0.25}
    assert presets.PRESET_CONSTRAINTS["acs_double"]["min_font_pt"] == 4.5
    assert presets.PRESET_CONSTRAINTS["aps_single"]["min_font_pt"] == 8.0
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_sidebar_toolbar.py -q` → 2 new tests fail (KeyError/AssertionError).

- [ ] **Step 3: Implement** — replace `designer/figspec_designer/presets.py` with:

```python
"""Journal width presets (mm), per-preset constraint defaults, canvas defaults.

Values verified against publisher primary sources on 2026-07-30; per-value
citations, unit conversions and known publisher-side inconsistencies are in
docs/journal-figure-specs.md. aps min_font_pt is DERIVED from APS's 2 mm
cap-height rule (~7.9 pt nominal for Helvetica), not stated in pt by APS.
"""
PRESETS: dict[str, float] = {
    "nature_single": 89.0,
    "nature_double": 183.0,
    "nature_research_single": 88.0,
    "nature_research_double": 180.0,
    "science_single": 90.0,
    "science_double": 183.0,
    "acs_single": 84.7,
    "acs_double": 177.8,
    "aps_single": 85.0,
    "aps_double": 178.0,
}

_NATURE = {"min_font_pt": 5.0, "max_font_pt": 7.0, "min_linewidth_pt": 0.25}
_SCIENCE = {"min_font_pt": 5.0, "max_font_pt": 10.0, "min_linewidth_pt": 0.5}
_ACS = {"min_font_pt": 4.5, "max_font_pt": 8.0, "min_linewidth_pt": 0.5}
_APS = {"min_font_pt": 8.0, "max_font_pt": 10.0, "min_linewidth_pt": 0.5}

PRESET_CONSTRAINTS: dict[str, dict[str, float]] = {
    "nature_single": dict(_NATURE),
    "nature_double": dict(_NATURE),
    "nature_research_single": dict(_NATURE),
    "nature_research_double": dict(_NATURE),
    "science_single": dict(_SCIENCE),
    "science_double": dict(_SCIENCE),
    "acs_single": dict(_ACS),
    "acs_double": dict(_ACS),
    "aps_single": dict(_APS),
    "aps_double": dict(_APS),
}

DEFAULT_HEIGHT_MM = 100.0
DEFAULT_DPI = 600
DEFAULT_GUTTER_MM = 4.0
```

- [ ] **Step 4: Write `docs/journal-figure-specs.md`** — extract from the research JSON (path in Global Constraints; load with `json.load(...)["result"]`, publishers under `results`, verifier verdicts under `verification`). Structure (Chinese prose, URLs verbatim):

```markdown
# 期刊 Figure 规范速查（Nature / Science / APS / ACS）

**数据日期**：2026-07-30（各来源访问日期同）。**核验**：约 30 条关键数字经独立复核，零错配。
**用途**：FigSpec 预设与约束的依据。投稿前请以期刊现行指南为准。

## 对比总表
[per-publisher rows: 单栏/1.5栏/双栏/最大高/字号/panel标号/字体/最细线/DPI/色彩 —
 each cell the verified value; conversions marked "(换算)"]

## 各社详情与来源
[one section per publisher: every number with its source URL from the JSON
 `sources` arrays and what it supports; quote confidence_notes essentials]

## 出版社自相矛盾处（均为对方文档间冲突，非我方查错）
[Nature 89/183/247 vs 90/180/170；Science HTML 三栏 57/121/184 vs PDF 双栏 90/183–184；
 Science 线宽 0.5 vs 0.28 pt；APS 双栏 178 仅存 legacy 2011；NComms 2080px=176mm≠180mm]

## FigSpec 取值决策
[which side of each conflict our presets take and why; aps min_font 派生逻辑；
 acs max_font 8.0 为工具默认（无官方上限）；NComms ≥1pt 线宽特例未进预设]

## 未独立核验残留
[from verification: byte-identical sibling-page claims, contrast rows, fees]
```
Every number in the doc must come from the JSON — no invention. Keep it complete but readable (aim 150-250 lines).

- [ ] **Step 5: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass (some pre-existing tests may assert old ACS/APS values — update ONLY such numeric assertions if hit; report which).

- [ ] **Step 6: Commit** — `git add designer/ docs/journal-figure-specs.md && git commit -m "feat: verified journal presets with sourced reference doc"`

---

### Task 2: TopBar preset→constraints wiring

**Files:**
- Modify: `designer/figspec_designer/ui/toolbar.py`, `designer/figspec_designer/ui/main_window.py`
- Test: append to `designer/tests/test_sidebar_toolbar.py`, possibly update numeric assertions in existing constraint-default tests

**Interfaces:**
- Consumes: `PRESET_CONSTRAINTS` (Task 1).
- Produces: preset selection applies width + constraints in one batch; MainWindow init state consistent (doc.constraints == topbar values).

- [ ] **Step 1: Write the failing tests** (append to `designer/tests/test_sidebar_toolbar.py`)

```python
def test_preset_applies_constraints(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    got = []
    tb.settings_changed.connect(lambda: got.append(1))
    tb.preset_combo.setCurrentText("acs_single")
    assert tb.values()[1] == 84.7
    assert tb.min_font_spin.value() == 4.5
    assert tb.max_font_spin.value() == 8.0
    assert tb.min_lw_spin.value() == 0.5
    assert len(got) == 1  # ONE settings_changed for the whole batch


def test_custom_preserves_constraints(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    tb.preset_combo.setCurrentText("acs_single")
    tb.preset_combo.setCurrentText("custom")
    assert tb.min_font_spin.value() == 4.5  # untouched
    assert tb.width_spin.isEnabled()


def test_mainwindow_initial_constraints_match_preset(qtbot):
    from figspec_designer.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.doc.constraints.min_font_pt == 5.0
    assert win.doc.constraints.max_font_pt == 7.0   # nature_double preset
    assert win.doc.constraints.min_linewidth_pt == 0.25
```

- [ ] **Step 2: Run to verify failure** — new tests fail (constraints spins unchanged by preset; initial doc has 5/8/0.5).

- [ ] **Step 3: Implement**

`toolbar.py` — replace `_on_preset` with:
```python
    def _on_preset(self, key: str) -> None:
        if key in presets.PRESETS:
            spins = (self.width_spin, self.min_font_spin,
                     self.max_font_spin, self.min_lw_spin)
            for s in spins:
                s.blockSignals(True)
            self.width_spin.setValue(presets.PRESETS[key])
            c = presets.PRESET_CONSTRAINTS[key]
            self.min_font_spin.setValue(c["min_font_pt"])
            self.max_font_spin.setValue(c["max_font_pt"])
            self.min_lw_spin.setValue(c["min_linewidth_pt"])
            for s in spins:
                s.blockSignals(False)
            self.width_spin.setEnabled(False)
        else:
            self.width_spin.setEnabled(True)
        self.settings_changed.emit()
```
Also update the ctor's initial `set_values(...)` call to pass the nature_double constraint values (5.0, 7.0, 0.25) instead of generic defaults, keeping the 8-arg signature.

`main_window.py` — at the END of `__init__` (after all signal wiring, before/instead of the bare `self.refresh()` if present — check current code), call `self._on_settings_changed()` once so `doc.target`/`doc.constraints` reflect the topbar's initial state. Verify `refresh()` still runs exactly once at init (avoid double rebuild: `_on_settings_changed` already calls refresh — remove the redundant standalone `refresh()` call if the current ctor has one).

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → all pass. Pre-existing numeric assertions that may need updating (ONLY these kinds): `test_topbar_constraint_spin_defaults` (5.0/8.0/0.5 → 5.0/7.0/0.25) and any default-export constraint assertions. Report every touched assertion.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: presets drive per-journal constraint defaults"`

---

## Self-Review Notes

- Spec §1 → Task 1 PRESETS; §2 → Task 1 PRESET_CONSTRAINTS + Task 2 wiring/semantics (one-batch signal, custom untouched, init sync); §3 → Task 1 Step 4 doc; §4 验收 → both tasks' test steps + the explicit "only numeric assertions" rule.
- Type consistency: PRESET_CONSTRAINTS key names match Constraints dataclass field names (min_font_pt/max_font_pt/min_linewidth_pt) consumed via dict lookup in toolbar; MainWindow sync reuses existing `_on_settings_changed`.
- Risk: double-refresh at init (guarded in Task 2 Step 3); existing tests asserting init export defaults.
