import json
import pytest
from figspec.mcp_server import (close_panel_impl, lint_pdf_impl, list_presets_impl,
                                new_spec_impl, read_spec_impl, set_panel_hint_impl,
                                split_panel_impl, write_spec_impl)
from figspec.selftest.samples import write_samples


@pytest.fixture()
def samples(tmp_path):
    return write_samples(tmp_path)


def test_lint_bad_sample(samples):
    out = lint_pdf_impl(str(samples["bad"]), width_mm=183)
    assert out["summary"]["ready"] is False
    ids = {f["check_id"] for f in out["findings"]}
    assert "FONT-EFFECTIVE" in ids


def test_lint_missing_file():
    out = lint_pdf_impl("/nonexistent/x.pdf")
    assert "error" in out and "cannot open" in out["error"]


def test_new_read_roundtrip(tmp_path):
    p = tmp_path / "fig.figspec.json"
    created = new_spec_impl(str(p), preset="aps_single", height_mm=90.0)
    assert created["target"]["figure_width_mm"] == 85.0
    assert created["constraints"]["min_font_pt"] == 8.0
    seen = read_spec_impl(str(p))
    assert seen["panel_count"] == 1 and seen["has_designer_tree"] is True


def test_new_spec_unknown_preset(tmp_path):
    out = new_spec_impl(str(tmp_path / "x.json"), preset="cell_double")
    assert "error" in out and "nature_double" in out["error"]  # lists valid presets


def test_split_close_hint_flow(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    out = split_panel_impl(str(p), "a", "right")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b"]
    out = split_panel_impl(str(p), "b", "down")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b", "c"]
    out = set_panel_hint_impl(str(p), "b", "STEM image")
    assert out["panels"][1]["content_hint"] == "STEM image"
    out = close_panel_impl(str(p), "c")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b"]
    out = close_panel_impl(str(p), "zz")
    assert "error" in out and "a, b" in out["error"]  # lists existing labels


def test_close_last_panel_error(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    out = close_panel_impl(str(p), "a")
    assert "error" in out


def test_ops_preserve_unknown_top_level(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    data = json.loads(p.read_text())
    data["x_custom_section"] = {"keep": "me"}
    p.write_text(json.dumps(data))
    split_panel_impl(str(p), "a", "right")
    after = json.loads(p.read_text())
    assert after["x_custom_section"] == {"keep": "me"}


def test_ops_without_sidecar(tmp_path):
    p = tmp_path / "plain.json"
    data = new_spec_impl(str(tmp_path / "t.json"))
    del data["designer"]
    p.write_text(json.dumps(data))
    out = split_panel_impl(str(p), "a", "right")
    assert "error" in out and "designer" in out["error"]


def test_write_spec_validates(tmp_path):
    p = tmp_path / "w.json"
    out = write_spec_impl(str(p), {"nope": 1})
    assert "error" in out and not p.exists()


def test_list_presets():
    out = list_presets_impl()
    assert out["presets"]["nature_double"] == 183.0
    assert out["constraints"]["acs_single"]["min_font_pt"] == 4.5


def test_build_server_smoke():
    fastmcp = pytest.importorskip("fastmcp")  # noqa: F841
    from figspec.mcp_server import build_server
    server = build_server()
    assert server.name == "figspec"
