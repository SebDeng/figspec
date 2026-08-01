"""Illustrator-ready assembly boards.

"Export an .ai" translated honestly: modern .ai is a PDF shell around
private Adobe data nobody can (or should) forge — but Illustrator opens a
well-formed PDF natively, as editable artwork, at exact physical size. So
this module writes PDFs: the figure-sized assembly board with the layout
(frames, letters, notes) on a hideable OCG layer and assets pre-placed
1:1, and the per-panel artboard — the authoring card's golden path handed
over as a file instead of an instruction.

Pure pikepdf with hand-written content streams (the selftest/samples.py
precedent); Qt-free so MCP/CLI can reuse it. Coordinates: spec is
top-left y-down in mm, PDF is bottom-left y-up in pt — every y goes
through the flip exactly once, here.
"""
from __future__ import annotations

from dataclasses import dataclass

import pikepdf

from figspec.layout.flatten import format_label
from figspec.units import mm_to_pt, pt_to_mm

GUIDE_RGB = (0.29, 0.56, 0.85)  # guide blue: visibly not final ink
NOTE_GRAY = 0.45
ANNOTATION_PT = 5.0
FRAME_W_PT = 0.5
LAYOUT_LAYER = "figspec layout"
CONTENT_LAYER = "figspec content"


@dataclass
class BoardPanel:
    label: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    asset_path: str | None = None
    asset_px: tuple[int, int] | None = None
    asset_dpi: float | None = None


def _esc(text: str) -> str:
    return (text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))


def _text_op(font: str, size_pt: float, x_pt: float, y_pt: float, text: str,
             gray: float | None = None) -> str:
    color = f"{gray:.3f} g " if gray is not None else "0 g "
    return (f"BT {color}/{font} {size_pt:.3f} Tf "
            f"1 0 0 1 {x_pt:.3f} {y_pt:.3f} Tm ({_esc(text)}) Tj ET")


def _approx_width_mm(text: str, size_pt: float) -> float:
    """Helvetica averages ~0.5 em per character — good enough for
    fits-or-skip decisions, never for placement-critical math."""
    return len(text) * 0.5 * pt_to_mm(size_pt)


def build_board(width_mm: float, height_mm: float, panels: list[BoardPanel],
                path, *, constraints=None, label_style: str = "lowercase",
                annotate_mm: bool = True,
                note_text: str | None = None) -> None:
    letter_pt = constraints.max_font_pt if constraints is not None else 7.0
    W, H = mm_to_pt(width_mm), mm_to_pt(height_mm)

    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(W, H))
    page.TrimBox = pikepdf.Array([0, 0, W, H])

    oc_layout = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.OCG, Name=pikepdf.String(LAYOUT_LAYER)))
    oc_content = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.OCG, Name=pikepdf.String(CONTENT_LAYER)))
    pdf.Root.OCProperties = pikepdf.Dictionary(
        OCGs=pikepdf.Array([oc_layout, oc_content]),
        D=pikepdf.Dictionary(Order=pikepdf.Array([oc_content, oc_layout]),
                             ON=pikepdf.Array([oc_layout, oc_content])))

    xobjects = pikepdf.Dictionary()
    content_ops: list[str] = []
    for i, panel in enumerate(panels):
        if panel.asset_path is None:
            continue
        try:
            content_ops.append(
                _place_asset(pdf, xobjects, f"P{i}", panel, H))
        except Exception:
            continue  # unreadable asset: keep the frame, skip the embed

    layout_ops: list[str] = []
    for panel in panels:
        x = mm_to_pt(panel.x_mm)
        lly = H - mm_to_pt(panel.y_mm + panel.h_mm)
        w, h = mm_to_pt(panel.w_mm), mm_to_pt(panel.h_mm)
        r, g, b = GUIDE_RGB
        layout_ops.append(f"q {r:.3f} {g:.3f} {b:.3f} RG {FRAME_W_PT} w "
                          f"{x:.3f} {lly:.3f} {w:.3f} {h:.3f} re S Q")
        letter = format_label(panel.label, label_style)
        baseline_mm = panel.y_mm + 1.2 + 0.72 * pt_to_mm(letter_pt)
        layout_ops.append(_text_op(
            "F2", letter_pt, mm_to_pt(panel.x_mm + 1.2),
            H - mm_to_pt(baseline_mm), letter))
        if annotate_mm:
            # ASCII only: base-14 fonts without /Encoding read
            # StandardEncoding, where multiply-sign/middle-dot bytes drift
            note = f"{panel.w_mm:.1f} x {panel.h_mm:.1f} mm"
            if _approx_width_mm(note, ANNOTATION_PT) < 0.9 * panel.w_mm:
                cx_mm = (panel.x_mm + panel.w_mm / 2
                         - _approx_width_mm(note, ANNOTATION_PT) / 2)
                cy_mm = panel.y_mm + panel.h_mm / 2
                layout_ops.append(_text_op(
                    "F1", ANNOTATION_PT, mm_to_pt(cx_mm),
                    H - mm_to_pt(cy_mm), note, gray=NOTE_GRAY))
    if note_text:
        layout_ops.append(_text_op("F1", ANNOTATION_PT, mm_to_pt(1.5),
                                   mm_to_pt(1.5), note_text, gray=NOTE_GRAY))

    stream = "\n".join(
        ["/OC /L2 BDC"] + content_ops + ["EMC", "/OC /L1 BDC"]
        + layout_ops + ["EMC"])
    helv = pikepdf.Dictionary(Type=pikepdf.Name.Font,
                              Subtype=pikepdf.Name.Type1,
                              BaseFont=pikepdf.Name.Helvetica)
    helv_bold = pikepdf.Dictionary(Type=pikepdf.Name.Font,
                                   Subtype=pikepdf.Name.Type1,
                                   BaseFont=pikepdf.Name("/Helvetica-Bold"))
    page.Resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary(F1=helv, F2=helv_bold),
        Properties=pikepdf.Dictionary(L1=oc_layout, L2=oc_content),
        XObject=xobjects)
    page.Contents = pdf.make_stream(stream.encode("latin-1"))
    pdf.save(path)


def _place_asset(pdf: pikepdf.Pdf, xobjects: pikepdf.Dictionary, name: str,
                 panel: BoardPanel, page_h_pt: float) -> str:
    """Embed one asset 1:1 (letterbox, centered — the sidebar's exact k)
    and return the placement op. Raises on unreadable input; the caller
    keeps the frame and moves on."""
    from figspec import scaling
    llx = mm_to_pt(panel.x_mm)
    lly = page_h_pt - mm_to_pt(panel.y_mm + panel.h_mm)
    w_pt, h_pt = mm_to_pt(panel.w_mm), mm_to_pt(panel.h_mm)

    if str(panel.asset_path).lower().endswith(".pdf"):
        with pikepdf.open(panel.asset_path) as src:
            xobj = pdf.copy_foreign(src.pages[0].as_form_xobject())
        bbox = [float(v) for v in xobj.BBox]
        src_w, src_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if src_w <= 0 or src_h <= 0:
            raise ValueError("degenerate asset page")
        k = min(w_pt / src_w, h_pt / src_h)
        tx = llx + (w_pt - src_w * k) / 2 - k * bbox[0]
        ty = lly + (h_pt - src_h * k) / 2 - k * bbox[1]
        xobjects[f"/{name}"] = xobj
        return f"q {k:.6f} 0 0 {k:.6f} {tx:.3f} {ty:.3f} cm /{name} Do Q"

    from PIL import Image
    with Image.open(panel.asset_path) as im:
        rgb = im.convert("RGB")
        px_w, px_h = rgb.size
        raw = rgb.tobytes()
    src_mm = scaling.asset_size_mm((px_w, px_h), panel.asset_dpi or 96.0)
    k = scaling.placement_scale((panel.w_mm, panel.h_mm), src_mm)
    placed_w, placed_h = mm_to_pt(src_mm[0] * k), mm_to_pt(src_mm[1] * k)
    tx = llx + (w_pt - placed_w) / 2
    ty = lly + (h_pt - placed_h) / 2
    stream = pikepdf.Stream(pdf, raw)  # qpdf flate-compresses on save
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Image
    stream.Width = px_w
    stream.Height = px_h
    stream.ColorSpace = pikepdf.Name.DeviceRGB
    stream.BitsPerComponent = 8
    xobjects[f"/{name}"] = stream
    return (f"q {placed_w:.3f} 0 0 {placed_h:.3f} "
            f"{tx:.3f} {ty:.3f} cm /{name} Do Q")


def panel_artboard(panel: BoardPanel, path, *, constraints=None,
                   label_style: str = "lowercase") -> None:
    """A single panel's exact-size artboard: draw straight onto it in
    Illustrator and 1:1 is automatic."""
    shifted = BoardPanel(label=panel.label, x_mm=0.0, y_mm=0.0,
                         w_mm=panel.w_mm, h_mm=panel.h_mm,
                         asset_path=panel.asset_path,
                         asset_px=panel.asset_px, asset_dpi=panel.asset_dpi)
    note = None
    if constraints is not None:
        note = (f"panel {format_label(panel.label, label_style)} | "
                f"{panel.w_mm:.1f} x {panel.h_mm:.1f} mm | "
                f"fonts {constraints.min_font_pt:.1f}-"
                f"{constraints.max_font_pt:.1f} pt | "
                f"lines >= {constraints.min_linewidth_pt:g} pt")
    build_board(panel.w_mm, panel.h_mm, [shifted], path,
                constraints=constraints, label_style=label_style,
                annotate_mm=False, note_text=note)
