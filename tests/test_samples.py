import pikepdf
from figspec.selftest.samples import write_samples

def test_samples_are_valid_pdfs(tmp_path):
    paths = write_samples(tmp_path)
    assert set(paths) == {"good", "bad", "form"}
    for p in paths.values():
        with pikepdf.open(p) as pdf:
            assert len(pdf.pages) == 1

def test_good_page_is_89mm(tmp_path):
    paths = write_samples(tmp_path)
    with pikepdf.open(paths["good"]) as pdf:
        box = pdf.pages[0].MediaBox
        assert abs(float(box[2]) - 252.28) < 0.5  # 89 mm in pt
