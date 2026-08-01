"""figspec.scaling golden tests — the 1472×879 @ 96 dpi → 60×36 mm example
that anchors the whole stand-in/true-scale plan."""
import pytest

from figspec import scaling
from figspec.layout.tree import PanelNode, from_dict, to_dict
from figspec.spec import Constraints

SRC_PX = (1472, 879)
SRC_DPI = 96.0
PANEL = (60.0, 36.0)
NATURE = Constraints(min_font_pt=5.0, max_font_pt=7.0, min_linewidth_pt=0.25,
                     min_effective_dpi=300)


def _k():
    return scaling.placement_scale(PANEL, scaling.asset_size_mm(SRC_PX, SRC_DPI))


def test_asset_size_mm():
    w, h = scaling.asset_size_mm(SRC_PX, SRC_DPI)
    assert w == pytest.approx(389.467, abs=0.01)
    assert h == pytest.approx(232.569, abs=0.01)


def test_asset_size_mm_rejects_bad_dpi():
    with pytest.raises(ValueError):
        scaling.asset_size_mm(SRC_PX, 0)


def test_placement_scale_letterbox_takes_smaller_axis():
    src = scaling.asset_size_mm(SRC_PX, SRC_DPI)
    assert scaling.placement_scale(PANEL, src) == pytest.approx(0.15406, abs=1e-4)
    # widen the panel until height becomes the tighter axis
    assert scaling.placement_scale((200.0, 36.0), src) == pytest.approx(
        36.0 / src[1], rel=1e-9)


def test_effective_pt_golden():
    assert scaling.effective_pt(8.0, _k()) == pytest.approx(1.232, abs=0.005)


def test_required_nominal_golden_and_inverse():
    k = _k()
    assert scaling.required_nominal_pt(5.0, k) == pytest.approx(32.46, abs=0.01)
    assert scaling.required_nominal_pt(7.0, k) == pytest.approx(45.44, abs=0.01)
    assert scaling.required_nominal_pt(
        scaling.effective_pt(8.0, k), k) == pytest.approx(8.0, rel=1e-9)


def test_required_px_ceils():
    assert scaling.required_px(PANEL, 300) == (709, 426)


def test_card_without_asset_is_golden_path_only():
    card = scaling.authoring_card(PANEL, NATURE)
    assert "Option 1 — resize your canvas (golden path):" in card
    assert "60.0 × 36.0 mm" in card
    assert "5.0–7.0 pt" in card
    assert "≥ 0.25 pt" in card
    assert "Option 2" not in card
    assert "Option 3" not in card


def test_card_with_asset_has_all_three_options():
    card = scaling.authoring_card(PANEL, NATURE, asset_px=SRC_PX,
                                  asset_dpi=SRC_DPI)
    assert "×0.154" in card
    assert "32.5–45.4 pt" in card
    assert "≥ 1.6 pt" in card
    assert "709 × 426 px" in card


def test_card_asset_without_dpi_omits_option_2():
    card = scaling.authoring_card(PANEL, NATURE, asset_px=SRC_PX)
    assert "Option 2" not in card
    assert "Option 3" in card and "709 × 426 px" in card


def test_card_reversibility():
    """The card's displayed (1-dp) nominal values, multiplied back by k,
    must land inside the constraint band within display precision."""
    k = _k()
    lo = round(scaling.required_nominal_pt(NATURE.min_font_pt, k), 1)
    hi = round(scaling.required_nominal_pt(NATURE.max_font_pt, k), 1)
    assert lo * k == pytest.approx(NATURE.min_font_pt, abs=0.05)
    assert hi * k == pytest.approx(NATURE.max_font_pt, abs=0.05)


# ---- asset_dpi sidecar round-trip (batch D task 2) ----------------------

def test_panel_node_asset_dpi_roundtrip():
    node = PanelNode(id="p1", asset="a.png", asset_px=(1472, 879),
                     asset_dpi=220.0)
    d = to_dict(node)
    assert d["asset_dpi"] == 220.0
    back = from_dict(d)
    assert back.asset_dpi == 220.0


def test_panel_node_no_dpi_writes_no_key():
    node = PanelNode(id="p1", asset="a.png", asset_px=(400, 300))
    d = to_dict(node)
    assert "asset_dpi" not in d
    assert from_dict(d).asset_dpi is None


def test_old_sidecar_without_dpi_parses():
    d = {"type": "panel", "id": "p1", "content_hint": "",
         "asset": "a.png", "asset_px": [400, 300]}
    assert from_dict(d).asset_dpi is None


# ---- pre-assembly prediction for vector assets (batch G) -----------------

def test_predict_pdf_golden(tmp_path):
    pytest.importorskip("matplotlib")
    from tests.fixtures import make_panel
    pdf = tmp_path / "panel.pdf"
    make_panel(pdf, fontsize=8.0, linewidth=0.5)  # 3.5 × 2.5 in intrinsic
    pred = scaling.predict_pdf(str(pdf), (30.0, 30.0), NATURE)
    assert pred["src_mm"][0] == pytest.approx(88.9, abs=0.5)
    k = pred["k"]
    assert k == pytest.approx(30.0 / 88.9, abs=0.005)  # width binds
    assert pred["text_absent"] is False
    eights = [e for e in pred["text"] if abs(e["source_pt"] - 8.0) < 0.15]
    assert eights, pred["text"]
    assert eights[0]["placed_pt"] == pytest.approx(8.0 * k, abs=0.05)
    assert eights[0]["verdict"] == "fail"  # ~2.7 pt, far under the 5 pt floor
    assert any(s["verdict"] == "fail" for s in pred["strokes"])  # 0.5 → ~0.17


def test_predict_pdf_text_absent(tmp_path):
    pytest.importorskip("matplotlib")
    from tests.fixtures import make_textpath_panel
    pdf = tmp_path / "outlined.pdf"
    make_textpath_panel(pdf)
    pred = scaling.predict_pdf(str(pdf), (60.0, 40.0), NATURE)
    assert pred["text_absent"] is True
    assert pred["text"] == []


def test_predict_pdf_known_sample(tmp_path):
    """The synthetic bad sample: 8 pt under a 0.4 content-stream scale is
    3.2 pt effective in-asset; placed into a same-width panel (k = 1) it
    stays 3.2 pt — red against the Nature floor."""
    from figspec.selftest.samples import write_samples
    paths = write_samples(tmp_path / "s")
    pred = scaling.predict_pdf(str(paths["bad"]), (183.0, 100.0), NATURE)
    assert pred["k"] == pytest.approx(1.0, abs=1e-6)
    assert [e["source_pt"] for e in pred["text"]] == [3.2]
    assert pred["text"][0]["verdict"] == "fail"
    assert pred["strokes"][0]["source_pt"] == pytest.approx(0.2)
    assert pred["strokes"][0]["verdict"] == "fail"
