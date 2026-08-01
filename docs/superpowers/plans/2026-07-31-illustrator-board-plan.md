# Illustrator Board (批次 H) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exact-physical-size, layered, Illustrator-openable PDFs per the approved spec `docs/superpowers/specs/2026-07-31-illustrator-board-design.md`: a whole-figure assembly board (frames on a hideable OCG layer, assets pre-placed 1:1) and a per-panel artboard (the authoring card's golden path as a file).

**Architecture:** All PDF authoring in `figspec/board.py` (pure pikepdf, Qt-free, hand-written content streams per the `selftest/samples.py` precedent). One core `build_board()`; `panel_artboard()` is a one-panel board with shifted origin and a constraint note. Placement math reuses `figspec.scaling` (same k the sidebar shows). Designer adds two thin entry points. Verification is dogfooding: `figspec.pdf.interpreter.extract` reads every claim back out of the output.

**Tech Stack:** pikepdf (as_form_xobject/copy_foreign, OCG dictionaries), Pillow (raster bytes), existing figspec test fixtures (`selftest.samples.write_samples`), pytest / pytest-qt offscreen.

## Global Constraints

- `figspec/` stays Qt-free. No new dependencies.
- Coordinate flip is the classic bug farm: spec top-left y-down → PDF `lly = mm_to_pt(H_mm − y_mm − h_mm)`. Every placement test must pin a NON-symmetric rect (h ≠ w, y ≠ 0) so a missed flip cannot pass.
- Letterbox k and centering must equal the sidebar's (`scaling.placement_scale`, KeepAspectRatio center) — assert numerically in tests, don't re-derive by hand.
- Content-stream text: escape `( ) \` in strings; labels/notes are ASCII by construction.
- Missing/unreadable assets: skip the embed, keep the frame, never raise out of `build_board`.
- Baselines before H: `tests/` 167 pass + 1 skip (+1 known root-env false failure), `designer/tests` 206 pass, smoke exit 0. All stay green; suites run from repo root and `designer/` respectively (`QT_QPA_PLATFORM=offscreen`).

## File Structure

- `figspec/board.py` — `BoardPanel`, `build_board`, `panel_artboard` (create)
- `tests/test_board.py` (create)
- `designer/figspec_designer/ui/main_window.py` — File > Export Illustrator Board…, `export_panel_artboard`, do_action branch (modify)
- `designer/figspec_designer/ui/panel_widget.py` — context-menu item (modify)
- `designer/tests/test_board_ui.py` (create)

---

### Task H1: `figspec/board.py` — frames, letters, notes, OCG layers

**Interfaces (later tasks rely on these EXACT names):**
```python
@dataclass
class BoardPanel:
    label: str
    x_mm: float; y_mm: float; w_mm: float; h_mm: float
    asset_path: str | None = None
    asset_px: tuple[int, int] | None = None
    asset_dpi: float | None = None

def build_board(width_mm, height_mm, panels: list[BoardPanel], path, *,
                constraints=None, label_style="lowercase",
                annotate_mm=True, note_text: str | None = None) -> None
def panel_artboard(panel: BoardPanel, path, *, constraints=None,
                   label_style="lowercase") -> None
```

- [ ] **Step 1: failing tests** (`tests/test_board.py`): build 183×100 with two panels (a: 0,0,91.5,50; b: 95.5,54,87.5,46) →
  - `extract(path)`: `pages[0].width_pt == mm_to_pt(183)` ± 0.1, height likewise; TrimBox set (pikepdf read).
  - letters: TextRun 'a' with `nominal_pt == constraints.max_font_pt` (pass Nature 5/7/0.25), font_name contains "Bold"; bbox lands inside panel a's pt rect **upper-left region** (y-flip pin).
  - `label_style="uppercase"` → TextRun 'A'.
  - raw pikepdf: `Root.OCProperties.OCGs` has 2 entries named "figspec layout"/"figspec content"; content stream bytes contain `/OC` + `BDC`; page Resources.Properties maps both.
  - mm annotation "91.5 × 50.0 mm" present as TextRun at 5 pt; `annotate_mm=False` → absent.
  - `panel_artboard(BoardPanel('c',10,20,60,36), path, constraints=NATURE)`: page == 60×36 mm in pt; letter at origin-shifted position; note TextRun contains "60.0 × 36.0 mm" and "fonts 5.0–7.0 pt".
- [ ] **Step 2: implement.** Hand-written ops joined into one content stream: `/OC /L2 BDC …assets(H2 placeholder empty)… EMC` then `/OC /L1 BDC …frames/letters/notes… EMC`. Frames `q 0.29 0.56 0.85 RG 0.5 w x y w h re S Q`. Letter baseline at `y_top + 1.2mm + 0.72×em` (converted+flipped). Note/annotation gray `0.45 g` Helvetica 5 pt. OCGs via `pdf.make_indirect`; `Root.OCProperties = {OCGs, D:{Order, ON}}`. Fonts F1 Helvetica / F2 Helvetica-Bold base-14. `panel_artboard` shifts the panel to origin, composes the default note from constraints, delegates.
- [ ] **Step 3: suites green.** Commit: `feat: figspec.board — layered Illustrator-ready assembly board + panel artboard`

### Task H2: 1:1 asset placement

- [ ] **Step 1: failing tests**:
  - **vector golden**: `write_samples` bad.pdf (183 mm × 200 pt page, in-asset effective text 3.2 pt) into panel (0,0,91.5,50) on a 183×100 board → k = min(91.5/183, 50/70.556) = 0.5 exactly; `extract(board)`: TextRun "Scaled tiny text" with `effective_pt == 3.2 × 0.5 = 1.6` ± 0.02 (form-XObject recursion is the shipped interpreter's own feature — dogfooding). Placed bbox centered in the panel's pt rect ± 1 pt.
  - **raster golden**: Pillow 400×300 RGB PNG, `asset_dpi=None` (assume 96) into panel (95.5,54,60,36) → src 105.83×79.375 mm, k = min(60/105.83, 36/79.375) = 0.45354; `extract`: PlacedImage px 400×300, `effective_dpi == 400 / (105.83×k/25.4)` ± 2; bbox inside panel rect (non-symmetric y pins the flip).
  - missing asset path → board still written, frame present, no raise.
- [ ] **Step 2: implement.** PDF: `xobj = pdf.copy_foreign(pikepdf.open(asset).pages[0].as_form_xobject())`; BBox-aware transform `q k 0 0 k (llx+cx−k·bbox.llx) (lly+cy−k·bbox.lly) cm /Pn Do Q` with letterbox-center offsets. Raster: Pillow → RGB raw bytes → `pikepdf.Stream` dict {XObject/Image/Width/Height/DeviceRGB/8bpc}, no manual Filter (qpdf compresses on save); `q (src_w_pt·k) 0 0 (src_h_pt·k) tx ty cm /Pn Do Q`. k via `scaling.asset_size_mm`/`placement_scale`. Per-asset try/except.
- [ ] **Step 3: suites green.** Commit: `feat: board pre-places assets 1:1 — vector via form XObject, raster via image XObject`

### Task H3: Designer entry points

- [ ] **Step 1: failing tests** (`designer/tests/test_board_ui.py`, monkeypatch the save dialogs):
  - `win.export_ai_board()` → file exists; `extract` page == doc target mm; with a dropped bad.pdf asset the board contains its text (placement wired through resolve_asset).
  - `win.do_action("export_artboard", pid)` → file exists; page == that panel's mm; statusbar mentions Illustrator.
  - context menu wiring: PanelWidget menu contains an "Export Panel Artboard…" action (inspect `QMenu` actions via monkeypatched exec, same pattern as existing context-menu tests if any; otherwise assert `do_action` route directly).
- [ ] **Step 2: implement.** `_board_panels()` builds BoardPanel list from `doc.panel_rects()` + labels + nodes (assets absolutized via `resolve_asset`). File > "Export Illustrator Board…" (default `figure-board.pdf`), panel context-menu "Export Panel Artboard…" → `do_action("export_artboard", pid)` → save dialog (default `panel-<label>-artboard.pdf`). Statusbar copy: "…opens in Illustrator at exact size". OSError → statusbar, no crash.
- [ ] **Step 3: both suites + smoke green.** Commit: `feat: Export Illustrator Board / panel artboard from the Designer`

---

## Verification (batch)

1. Both suites + smoke green (expect ≈ +10 core, +4 designer tests).
2. Dogfood chain: render the exported board with pypdfium2 → non-trivial pixels; `figspec lint` on a board with a placed bad.pdf reports the SAME effective sizes the sidebar predicted (1.6 pt for the 91.5 mm panel case).
3. Docs closeout: spec status → Shipped; `figspec-设计文档.md` §2.5 one-line addition.
4. Follow-ups (not this batch): MCP `export_board` tool; letters-on-content-layer option; bleed/crop marks.
