# UI Slim (批次 I) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans, task-by-task. Spec: `docs/superpowers/specs/2026-07-31-ui-slim-design.md`.

**Goal:** Consolidate the Designer's surfaces around the three verbs (carve / see truth / hand off) with zero feature loss: one Hand Off palette, a three-item top bar with a Document popover, a three-layer sidebar with a truth popover, a collapsed status strip with a unified zoom cluster, hover buttons removed, and the handoff actions extracted out of main_window.

**Widget-preservation strategy (the churn firewall):** every existing value widget and its attribute name stays alive — five top-bar spinners re-parent into the Document popover, the sidebar's `asset_box` becomes the truth popover's content container wholesale. Programmatic `setValue`/`click` works on hidden widgets, and `isVisibleTo(container)` ignores the container's own visibility, so the existing suites pass untouched except the enumerated sites below.

**Known test edits (complete list):**
- `test_panel_widget.py::test_buttons_emit_actions` → rewrite against `PanelWidget.context_actions()`.
- `test_batch_c_ui.py:13` (`sidebar.btn_copy_snippet.click()`) → `win.copy_snippet()`.
- `test_scale_truth.py` two `btn_copy_card.click()` sites → `win.copy_authoring_card()`.
- `test_sidebar_toolbar.py:46` (`tb.btn_save.click()`) → drop the button assertion, keep save-path coverage via `win.save()`.
- `test_theme.py:73` (`tb.btn_copy` objectName "primary") → retarget to `tb.btn_handoff`.
- `test_scale_truth.py::test_no_asset_hides_block` → assert truth-line disabled state instead of asset_box visibility.

## Tasks

### I1: Hand Off palette + menu/sidebar consolidation
- Create `designer/figspec_designer/ui/handoff.py`: the seven action bodies move here as functions taking the window (`export_board(win)`, `export_panel_artboard(win, pid)`, `copy_snippet(win)`, `copy_card(win)`, `copy_json(win)`, `copy_placement(win)`, `export_preview(win)`), plus `HandoffDialog` — vertical rows (title + one-line description), Enter/click runs and closes, per-row objectName `handoffRow`. Panel-scoped rows disabled when no selection.
- MainWindow: `hand_off()` (Cmd+E) opens it; existing public methods become thin delegates (API compat). File menu: New/Open/Recent/Save/Save As/──/Hand Off…/──/Lint PDF (12→8 items incl. separators-free count 7 actions). Sidebar: delete `btn_copy_placement/btn_copy_snippet/btn_copy_card` + their signals and window connections.
- Tests `designer/tests/test_ui_slim.py`: dialog lists 7 rows; snippet row copies to clipboard; artboard row disabled with no selection; File menu action count; sidebar has no copy buttons. Apply the enumerated edits for batch_c/scale_truth.
- Commit: `refactor: one Hand Off palette replaces seven scattered export paths`

### I2: TopBar slim + Document popover + restyle
- TopBar keeps all eight value widgets + contracts. Visible: Preset, W, H, settings chip (`btn_document`, text like `600 dpi · 4 mm · 5–7 pt · ≥0.25 pt`, refreshed in `set_values` and on `settings_changed`), stretch, `btn_handoff` ("Hand Off…", objectName "primary", signal `handoff_requested` → window). `btn_open/btn_save/btn_copy` and their signals removed (window connections too).
- Document popover: `QWidget(window flags Qt.Popup)` child `docPopover`, grid of DPI/Gutter/Min font/Max font/Min line re-parented; chip click shows it under the chip.
- theme.py: topbar 44px flat bar + 1px bottom hairline, uniform 26px control height, small-caps labels, chip pill (`#docChip`), popover card (`#docPopover`: white, 1px #D9D6D0, radius 8).
- Tests: chip text reflects values and updates after `min_font_spin.setValue`; popover contains the five widgets; `values()` contract unchanged; height warning still on visible `height_spin`. Apply sidebar_toolbar/theme edits.
- Commit: `refactor: three-item top bar — Document popover, settings chip, single primary action`

### I3: Sidebar three layers + truth popover
- Always-visible column: Label, Size, **truth line** (`btn_truth`, flat, objectName "truthLine"; text: raster `×{k:.3f} · {eff:.0f} dpi {✓/△/✗}`, vector `×{k:.3f} · 8→{8k:.2f} pt {worst-verdict glyph from prediction}`, no asset → `{min}–{max} pt · ≥{lw} pt`, disabled), hint, Stand-in, one compact row [Lock aspect ▢ · Square], Remove Asset (asset only). `Details ▸` QToolButton toggles the Position/Aspect/Pixels/figsize grid, default collapsed.
- Truth popover: `asset_box` re-parented into a Qt.Popup container shown from the truth line; contents unchanged (File/Pixels/Effective/Source DPI/Scale/Font calc/prediction) minus the Remove button (moves to main column). All attribute names preserved.
- `show_panel` signature unchanged; sets truth text + level property (`repolish`).
- Tests: truth text golden for the bad.pdf-in-91.5mm case (`×0.500` and `→4.00 pt`… compute from constraints) and for a raster (dpi + light); Details default collapsed and toggles; popover opens and contains `calc_nominal`; no-asset → truth shows constraints echo and popover disabled.
- Commit: `refactor: three-layer sidebar — truth line with on-demand analysis popover`

### I4: Status strip + zoom cluster + hover-button removal
- SpecimenStrip: `set_expanded(bool)` + chevron `btn_expand`; collapsed 24px (mini `Aa` at min-font true scale + badge text), expanded = current full strip; `rows()/badge_text()` unchanged. Right cluster: `btn_fit`, `btn_actual` (existing), `btn_zoom_out`, `btn_zoom_in`; window wires to zoom_fit/zoom_actual/zoom_step. Badge doubles as the % display.
- PanelWidget: delete `_BTN_SPECS`/hover buttons/enter-leave handlers; add `context_actions() -> list[tuple[str, str]]` = [("Split Right", "split_right"), ("Split Down", "split_down"), ("Split Right N…", …), ("Split Down N…", …), ("Equalize", …), ("Swap", …), ("Export Panel Artboard…", "export_artboard")]; contextMenuEvent builds the menu from it.
- Tests: strip default collapsed, expand toggles height; zoom buttons drive canvas modes; `context_actions` contains split_right; rewrite `test_buttons_emit_actions` accordingly.
- Commit: `refactor: collapsed status strip with unified zoom cluster; hover buttons retired`

## Verification
Both suites + smoke green; before/after screenshots (same scenario: grid + raster + bad.pdf selected) attached to the session; element counts hit the spec targets; `wc -l main_window.py` < 900.
