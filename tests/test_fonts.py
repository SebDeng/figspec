import pikepdf
import pytest
from figspec.pdf.fonts import load_font, decode_codes

def _simple_font(pdf):
    return pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.TrueType,
        BaseFont=pikepdf.Name("/Test"), FirstChar=65, LastChar=67,
        Widths=pikepdf.Array([500, 600, 700]),
    )

def test_simple_font_widths():
    pdf = pikepdf.Pdf.new()
    fi = load_font(_simple_font(pdf))
    assert fi.code_size == 1
    assert fi.widths[65] == pytest.approx(0.5) and fi.widths[67] == pytest.approx(0.7)
    assert decode_codes(fi, b"ABC") == [(65, "A"), (66, "B"), (67, "C")]  # latin-1 fallback

def test_type3_widths_use_fontmatrix():
    pdf = pikepdf.Pdf.new()
    f = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type3,
        FontMatrix=pikepdf.Array([0.0005, 0, 0, 0.0005, 0, 0]),
        FirstChar=65, LastChar=65, Widths=pikepdf.Array([1000]),
    )
    fi = load_font(f)
    assert fi.widths[65] == pytest.approx(0.5)  # 1000 glyph units * 0.0005

def test_tounicode_bfchar_and_bfrange():
    pdf = pikepdf.Pdf.new()
    cmap = (b"begincmap\n"
            b"2 beginbfchar\n<0041> <0058>\n<0042> <0059>\nendbfchar\n"
            b"1 beginbfrange\n<0050> <0052> <0061>\nendbfrange\n"
            b"endcmap")
    f = _simple_font(pdf)
    f.ToUnicode = pdf.make_stream(cmap)
    fi = load_font(f)
    assert fi.to_unicode[0x41] == "X"
    assert fi.to_unicode[0x51] == "b"  # 0x50->a, 0x51->b, 0x52->c

def test_cid_font_w_array():
    pdf = pikepdf.Pdf.new()
    desc = pikepdf.Dictionary(
        Subtype=pikepdf.Name.CIDFontType2, DW=1000,
        W=pikepdf.Array([3, pikepdf.Array([400, 500]), 10, 12, 600]),
    )
    f = pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        DescendantFonts=pikepdf.Array([desc]),
    )
    fi = load_font(f)
    assert fi.code_size == 2
    assert fi.widths[3] == pytest.approx(0.4) and fi.widths[4] == pytest.approx(0.5)
    assert fi.widths[11] == pytest.approx(0.6)
    assert fi.default_width == pytest.approx(1.0)
    assert [c for c, _ in decode_codes(fi, b"\x00\x03\x00\x0b")] == [3, 11]
