# Designer UI Restyle (Direction C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle FigSpec Designer to the approved "minimal studio" direction (warm off-white chrome, white panel cards with soft shadows on a warm canvas, near-black ink, hairline dividers) with ZERO behavior change.

**Architecture:** One new module `designer/figspec_designer/ui/theme.py` owns every color/spacing/style decision as tokens + a single global QSS applied idempotently from MainWindow. Components lose their scattered `setStyleSheet` calls and instead expose objectNames/dynamic properties the global QSS targets.

**Tech Stack:** PySide6 QSS, QGraphicsDropShadowEffect, dynamic-property repolish pattern.

## Global Constraints

- ZERO behavior change: the existing 59 designer tests must pass UNMODIFIED. Public interfaces (signals, method names, attribute names `lbl_label/lbl_mm/lbl_px/lbl_figsize/hint_edit`, button objectNames `btn_split_right/btn_split_down/btn_close`, `values()`/`set_values()` arity) are frozen.
- Tokens exactly per spec: CHROME #FAF9F7, CANVAS #F1EFEB, HAIRLINE #EAE7E1, DIVIDER #D8D5CF, INK #1A1A18, INK_SECONDARY #6B6862, INK_MUTED #A09D96, PANEL_BG #FFFFFF; shadow blur 12 offset (0,1) color rgba(26,26,24,26/255).
- Plain-QWidget subclasses that get QSS backgrounds MUST set `Qt.WA_StyledBackground`.
- Selection styling via dynamic property + repolish (`PanelWidget[selected="true"]`), not inline stylesheets.
- Tests: `.venv/bin/pytest designer/tests -q` from repo root. After any pip install: `chflags -R nohidden .venv.nosync/`.
- TDD for new theme tests; restyle steps are refactors verified by the frozen suite.

---

### Task 1: Theme module (`ui/theme.py`) + application

**Files:**
- Create: `designer/figspec_designer/ui/theme.py`
- Modify: `designer/figspec_designer/ui/main_window.py` (apply_theme in ctor)
- Test: `designer/tests/test_theme.py`

**Interfaces:**
- Produces: `CHROME/CANVAS/HAIRLINE/DIVIDER/INK/INK_SECONDARY/INK_MUTED/PANEL_BG` str constants; `QSS: str`; `apply_theme(app) -> None` (idempotent); `repolish(widget) -> None`; `smallcaps_font() -> QFont` (AllUppercase, PercentageSpacing 112, pointSizeF 10); `panel_shadow(widget) -> QGraphicsDropShadowEffect` (blur 12, offset (0,1), QColor(26,26,24,26), sets effect on widget).

- [ ] **Step 1: Write the failing test** (`designer/tests/test_theme.py`)

```python
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget
from figspec_designer.ui import theme
from figspec_designer.ui.main_window import MainWindow


def test_tokens_present_in_qss():
    for token in (theme.CHROME, theme.CANVAS, theme.INK, theme.DIVIDER):
        assert token in theme.QSS


def test_mainwindow_applies_theme(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert theme.CHROME in QApplication.instance().styleSheet()


def test_smallcaps_font():
    f = theme.smallcaps_font()
    assert f.capitalization() == QFont.AllUppercase
    assert f.letterSpacing() == 112.0


def test_panel_shadow_and_repolish(qtbot):
    w = QWidget()
    qtbot.addWidget(w)
    eff = theme.panel_shadow(w)
    assert w.graphicsEffect() is eff
    assert eff.blurRadius() == 12
    theme.repolish(w)  # must not raise
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_theme.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`designer/figspec_designer/ui/theme.py`)

```python
"""Direction C ("minimal studio") theme: every color and style decision lives here."""
from __future__ import annotations
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

CHROME = "#FAF9F7"
CANVAS = "#F1EFEB"
HAIRLINE = "#EAE7E1"
DIVIDER = "#D8D5CF"
INK = "#1A1A18"
INK_SECONDARY = "#6B6862"
INK_MUTED = "#A09D96"
PANEL_BG = "#FFFFFF"
LETTER = "#C6C3BC"

QSS = f"""
QMainWindow, QWidget#chrome {{ background: {CHROME}; }}
QMenuBar {{ background: {CHROME}; color: {INK}; }}
QStatusBar {{ background: {CHROME}; color: {INK_SECONDARY}; border-top: 1px solid {HAIRLINE}; }}

Canvas {{ background: {CANVAS}; }}
QWidget#page {{ background: transparent; border: none; }}

PanelWidget {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 4px; }}
PanelWidget[selected="true"] {{ border: 2px solid {INK}; }}
QLabel#panelLetter {{ color: {LETTER}; font-size: 20px; font-weight: 600; background: transparent; border: none; }}

QWidget#panelActions {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE}; border-radius: 6px; }}
QWidget#panelActions QToolButton {{ border: none; border-radius: 4px; padding: 2px 6px;
    color: {INK_SECONDARY}; background: transparent; font-size: 12px; }}
QWidget#panelActions QToolButton:hover {{ background: {CANVAS}; color: {INK}; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover, QSplitter::handle:pressed {{ background: {DIVIDER}; }}

QLabel#dragFeedback {{ background: {INK}; color: {CHROME}; padding: 3px 8px;
    border-radius: 6px; font-size: 11px; }}

QWidget#topbar {{ background: {CHROME}; border-bottom: 1px solid {HAIRLINE}; }}
QWidget#topbar QLabel {{ color: {INK_SECONDARY}; font-size: 12px; }}
QComboBox, QDoubleSpinBox, QSpinBox {{ background: {PANEL_BG}; border: 1px solid {HAIRLINE};
    border-radius: 6px; padding: 3px 8px; color: {INK}; }}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {DIVIDER}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QPushButton {{ background: {CHROME}; border: 1px solid {DIVIDER}; border-radius: 12px;
    padding: 4px 14px; color: {INK}; }}
QPushButton:hover {{ background: {CANVAS}; }}
QPushButton#primary {{ background: {INK}; color: {CHROME}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #33332F; }}

QWidget#sidebar {{ background: {CHROME}; border-left: 1px solid {HAIRLINE}; }}
QLabel#sectionHeader {{ color: {INK_MUTED}; font-size: 10px; font-weight: 600; }}
QLabel#fieldLabel {{ color: {INK_MUTED}; font-size: 12px; }}
QLabel#fieldValue {{ color: {INK}; font-size: 12px; font-weight: 600; }}
QLineEdit {{ background: transparent; border: none; border-bottom: 1px solid {DIVIDER};
    border-radius: 0; padding: 3px 0; color: {INK}; }}
QLineEdit:focus {{ border-bottom: 2px solid {INK}; }}
QLineEdit:disabled {{ border-bottom-color: {HAIRLINE}; color: {INK_MUTED}; }}
"""


def apply_theme(app) -> None:
    app.setStyleSheet(QSS)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def smallcaps_font() -> QFont:
    f = QFont()
    f.setPointSizeF(10)
    f.setLetterSpacing(QFont.PercentageSpacing, 112)
    f.setCapitalization(QFont.AllUppercase)
    return f


def panel_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(12)
    eff.setOffset(0, 1)
    eff.setColor(QColor(26, 26, 24, 26))
    widget.setGraphicsEffect(eff)
    return eff
```

In `main_window.py` `__init__`, immediately after `super().__init__()`:
```python
        from PySide6.QtWidgets import QApplication
        from figspec_designer.ui.theme import apply_theme
        apply_theme(QApplication.instance())
```
(module-level import preferred: add `from figspec_designer.ui.theme import apply_theme` to the imports and call it; QApplication is already imported there.) Also set `central.setObjectName("chrome")` on the central widget.

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → 63 passed (59 + 4).

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "feat: minimal-studio theme module"`

---

### Task 2: Restyle panel widget, canvas, handle

**Files:**
- Modify: `designer/figspec_designer/ui/panel_widget.py`, `designer/figspec_designer/ui/canvas.py`, `designer/figspec_designer/ui/handle.py`
- Test: append to `designer/tests/test_theme.py`

**Interfaces:**
- Frozen: PanelWidget signal/action strings, button objectNames, `label_widget`, `set_label`, `set_selected` (property semantics), Canvas public API.
- Produces: PanelWidget with `panelActions` container + `panelLetter` label + WA_StyledBackground where needed; canvas page objectName `page`; feedback label objectName `dragFeedback`; panels get `panel_shadow`; handle.py loses inline stylesheet.

- [ ] **Step 1: Write the failing tests** (append to `designer/tests/test_theme.py`)

```python
def test_panel_widget_theme_hooks(qtbot):
    from figspec_designer.ui.panel_widget import PanelWidget
    w = PanelWidget("p1", "a")
    qtbot.addWidget(w)
    assert w.findChild(QWidget, "panelActions") is not None
    assert w.label_widget.objectName() == "panelLetter"
    w.set_selected(True)
    assert w.property("selected") is True  # property survives repolish path


def test_canvas_theme_hooks(qtbot):
    from figspec_designer.document import DesignerDocument
    from figspec_designer.ui.canvas import Canvas
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(600, 400)
    canvas.set_document(DesignerDocument.default())
    page = canvas.findChild(QWidget, "page")
    assert page is not None
    for w in canvas.panel_widgets().values():
        assert w.graphicsEffect() is not None  # shadow attached
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest designer/tests/test_theme.py -q` → the two new tests FAIL.

- [ ] **Step 3: Implement**

`panel_widget.py` — replace the styling parts, keep all behavior:
- Delete `_apply_style` and every `setStyleSheet` call.
- Ctor: `self.setProperty("selected", False)`; buttons go into `actions = QWidget(self); actions.setObjectName("panelActions"); actions.setAttribute(Qt.WA_StyledBackground, True)` with an HBox (margins 2, spacing 0); the bar layout `bar.addStretch(1); bar.addWidget(actions)`; `actions.setVisible(False)`; `self._actions = actions`.
- `enterEvent/leaveEvent` toggle `self._actions.setVisible(...)` instead of per-button loops.
- `self.label_widget.setObjectName("panelLetter")`; remove its inline stylesheet.
- `set_selected`: `self.setProperty("selected", bool(on)); repolish(self)` (import `repolish` from theme).

`canvas.py`:
- `self._page.setObjectName("page")` and REMOVE its `setStyleSheet` line (keep `setAttribute(Qt.WA_StyledBackground, True)` on the page for the transparent background to apply cleanly).
- Canvas ctor: `self.setAttribute(Qt.WA_StyledBackground, True)`.
- `self._feedback.setObjectName("dragFeedback")`; remove its inline stylesheet.
- In `_build_node`, after creating a PanelWidget: `from figspec_designer.ui.theme import panel_shadow` (module-level import) and `panel_shadow(w)`.

`handle.py`: delete the `self.setStyleSheet(...)` line in `GutterHandle.__init__` (global QSS covers handles).

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → 65 passed, none of the original 59 modified.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "refactor: panel/canvas/handle restyle via theme hooks"`

---

### Task 3: Restyle sidebar, toolbar, main window chrome

**Files:**
- Modify: `designer/figspec_designer/ui/sidebar.py`, `designer/figspec_designer/ui/toolbar.py`, `designer/figspec_designer/ui/main_window.py`
- Test: append to `designer/tests/test_theme.py`

**Interfaces:**
- Frozen: all public attribute names, signals, `values()/set_values()` behavior, text formats asserted by existing tests (`lbl_mm` "89.5 × 57.6" etc.).
- Produces: sidebar objectName `sidebar` with `sectionHeader` label; field labels/values with objectNames; toolbar objectName `topbar`, `btn_copy` objectName `primary`.

- [ ] **Step 1: Write the failing tests** (append to `designer/tests/test_theme.py`)

```python
def test_sidebar_theme_hooks(qtbot):
    from figspec_designer.ui.sidebar import Sidebar
    sb = Sidebar()
    qtbot.addWidget(sb)
    assert sb.objectName() == "sidebar"
    header = sb.findChild(QWidget, "sectionHeader")
    assert header is not None
    assert sb.lbl_mm.objectName() == "fieldValue"


def test_topbar_theme_hooks(qtbot):
    from figspec_designer.ui.toolbar import TopBar
    tb = TopBar()
    qtbot.addWidget(tb)
    assert tb.objectName() == "topbar"
    assert tb.btn_copy.objectName() == "primary"
```

- [ ] **Step 2: Run to verify failure** — the two new tests FAIL.

- [ ] **Step 3: Implement**

`sidebar.py`:
- Ctor: `self.setObjectName("sidebar"); self.setAttribute(Qt.WA_StyledBackground, True)`.
- Replace QFormLayout with a QVBoxLayout (margins 16, spacing 8): first a `sectionHeader` QLabel ("Panel", objectName `sectionHeader`, font `smallcaps_font()`); then a QGridLayout of rows — for each of (Label, Size (mm), Pixels, figsize (in)): left QLabel objectName `fieldLabel` (color via QSS), right the existing value label (`lbl_label/lbl_mm/lbl_px/lbl_figsize`) with objectName `fieldValue`, right-aligned (`setAlignment(Qt.AlignRight | Qt.AlignVCenter)`); then the existing `hint_edit`; then `addStretch(1)`.
- Keep every method body (`show_panel/clear/_emit_hint/flush_pending`) unchanged.

`toolbar.py`:
- Ctor: `self.setObjectName("topbar"); self.setAttribute(Qt.WA_StyledBackground, True)`; layout margins (16, 8, 16, 8), spacing 8; insert `lay.addSpacing(8)` between logical groups (preset/geometry vs dpi/gutter vs constraints vs buttons).
- `self.btn_copy.setObjectName("primary")`.

`main_window.py`: `central.setObjectName("chrome")` if not already from Task 1; nothing else.

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest designer/tests -q` → 67 passed.

- [ ] **Step 5: Commit** — `git add designer/ && git commit -m "refactor: sidebar/topbar/chrome restyle via theme hooks"`

---

### Task 4: Verification + visual capture

**Files:**
- None new (verification only; screenshot to scratchpad)

- [ ] **Step 1: Full suites** — `.venv/bin/pytest designer/tests -q && .venv/bin/pytest tests/ -q` → 67 + 78 passed.

- [ ] **Step 2: Smoke** — `PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` → exit 0.

- [ ] **Step 3: Capture themed screenshot** (offscreen render for the record):

```bash
PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python - <<'EOF'
from PySide6.QtWidgets import QApplication
from figspec_designer.ui.main_window import MainWindow
from figspec_designer.model.tree import iter_panels
app = QApplication([])
win = MainWindow()
win.resize(1100, 700)
first = next(iter_panels(win.doc.tree)).id
win.do_action("split_right", first)
right = [p.id for p in iter_panels(win.doc.tree) if p.id != first][0]
win.do_action("split_down", right)
win.do_action("select", right)
win.show()
app.processEvents()
win.grab().save("designer-restyle-screenshot.png")
print("saved")
EOF
```
Expected: `designer-restyle-screenshot.png` written at repo root (git-ignored? it is NOT — do not commit it; delete after review or leave for the controller).

- [ ] **Step 4: Report** — screenshot path + suite counts in the task report; the controller shows the screenshot to the user for visual acceptance.

---

## Self-Review Notes

- Spec coverage: tokens table → Task 1 QSS; every component bullet → Tasks 2-3; acceptance → Task 4. WA_StyledBackground called out per widget. Zero-behavior constraint enforced by frozen-suite verification in every task.
- Type consistency: theme function names used in Tasks 2-3 match Task 1 definitions; objectNames consistent between QSS (Task 1) and setters (Tasks 2-3) and tests.
- Known risk: QSS class-name selectors (`Canvas`, `PanelWidget`) rely on Qt metaobject class names of Python subclasses — standard PySide6 behavior; if a selector fails, fall back to objectName selectors (add setObjectName + adjust QSS) rather than inline styles.
