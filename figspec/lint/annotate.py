"""Render violation boxes onto page rasters."""
from __future__ import annotations
from pathlib import Path
import pypdfium2 as pdfium
from PIL import ImageDraw

FAIL_COLOR = (220, 38, 38)
WARN_COLOR = (217, 119, 6)

def annotate(pdf_path, findings, out_path, dpi: float = 150,
             origins: dict[int, tuple[float, float]] | None = None) -> list[Path]:
    """origins: optional {page_index: (origin_x_pt, origin_y_pt)} mapping the
    render origin (CropBox else MediaBox lower-left) per page -- required
    for non-zero-origin MediaBoxes, since Finding.boxes_pt are in absolute
    PDF user-space coordinates but pdfium's raster (and page_h below) is
    relative to the box it renders. Default None -> (0.0, 0.0) per page,
    i.e. unchanged behavior for the common origin-0 case.
    """
    origins = origins or {}
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
            ox, oy = origins.get(page_index, (0.0, 0.0))
            img = page.render(scale=scale).to_pil().convert("RGB")
            draw = ImageDraw.Draw(img)
            for f in (f for f in drawable if f.page == page_index):
                color = FAIL_COLOR if f.level == "FAIL" else WARN_COLOR
                for (x0, y0, x1, y1) in f.boxes_pt:
                    px = ((x0 - ox) * scale, (page_h - (y1 - oy)) * scale,
                          (x1 - ox) * scale, (page_h - (y0 - oy)) * scale)
                    draw.rectangle(px, outline=color, width=2)
                label_y = max((page_h - (max(b[3] for b in f.boxes_pt) - oy)) * scale - 14, 0)
                label_x = (min(b[0] for b in f.boxes_pt) - ox) * scale
                tag = (f"{f.effective_pt:g} pt ✗" if f.effective_pt is not None
                       else f.check_id)
                try:
                    draw.text((label_x, label_y), tag, fill=color)
                except UnicodeEncodeError:
                    # Some Pillow builds fall back to a Latin-1 bitmap font
                    # (ImageFont.load_default()) that cannot encode U+2717
                    # (✗); retry with a plain "x" so annotation never crashes
                    # on font-encoding limits.
                    draw.text((label_x, label_y), tag.replace("✗", "x"), fill=color)
            target = out_path if n == 0 else out_path.with_name(
                f"{out_path.stem}-p{page_index + 1}{out_path.suffix}")
            img.save(target)
            written.append(target)
    finally:
        doc.close()
    return written
