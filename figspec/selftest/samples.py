"""Hand-authored sample PDFs with exactly known geometry (no matplotlib needed)."""
from pathlib import Path
import pikepdf

GOOD_SIZES = {7.0, 6.0}
BAD_EFFECTIVE_FONT = 3.2   # 8 pt * 0.4 cm-scale
BAD_EFFECTIVE_LINE = 0.2   # 0.5 w * 0.4
FORM_EFFECTIVE_FONT = 3.0  # 10 pt * 0.5 form matrix * 0.6 ctm

_GOOD = b"""q
BT /F1 7 Tf 1 0 0 1 20 60 Tm (Good 7pt label) Tj ET
BT /F1 6 Tf 0 1 -1 0 240 20 Tm (Rotated 6pt) Tj ET
0.75 w 20 30 m 200 30 l S
Q"""

_BAD = b"""q
0.4 0 0 0.4 10 10 cm
BT /F1 8 Tf 1 0 0 1 20 120 Tm (Scaled tiny text) Tj ET
0.5 w 20 30 m 400 30 l S
Q"""

_FORM_INNER = b"BT /F1 10 Tf 1 0 0 1 5 5 Tm (Inner form text) Tj ET"
_FORM_PAGE = b"q 0.6 0 0 0.6 20 20 cm /Fm1 Do Q"

def _helvetica() -> pikepdf.Dictionary:
    return pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica
    )

def _simple_pdf(stream: bytes, width_pt: float, height_pt: float, path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(width_pt, height_pt))
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=_helvetica()))
    page.Contents = pdf.make_stream(stream)
    pdf.save(path)

def _form_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    form = pdf.make_stream(_FORM_INNER)
    form.Type = pikepdf.Name.XObject
    form.Subtype = pikepdf.Name.Form
    form.BBox = pikepdf.Array([0, 0, 100, 50])
    form.Matrix = pikepdf.Array([0.5, 0, 0, 0.5, 0, 0])
    form.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=_helvetica()))
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm1=form))
    page.Contents = pdf.make_stream(_FORM_PAGE)
    pdf.save(path)

def write_samples(dirpath: Path) -> dict[str, Path]:
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    good, bad, form = dirpath / "good.pdf", dirpath / "bad.pdf", dirpath / "form.pdf"
    _simple_pdf(_GOOD, 89 * 72 / 25.4, 200, good)    # 89 mm wide
    _simple_pdf(_BAD, 183 * 72 / 25.4, 200, bad)     # 183 mm wide
    _form_pdf(form)
    return {"good": good, "bad": bad, "form": form}
