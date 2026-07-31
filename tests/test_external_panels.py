import json
from pathlib import Path

import pytest

from figspec.document import (DesignerDocument, absolutize_assets,
                              relativize_assets, resolve_asset)
from figspec.layout import ops
from figspec.layout.flatten import effective_dpi
from figspec.layout.tree import PanelNode, SplitNode, from_dict, iter_panels, to_dict
from figspec.spec import Constraints, parse_spec


def _two_panel_tree():
    return SplitNode("row", (0.5, 0.5),
                     (PanelNode(id="aaaa1111"), PanelNode(id="bbbb2222")))


def test_set_asset_and_clear():
    tree = _two_panel_tree()
    t2 = ops.set_asset(tree, "aaaa1111", "/abs/img.png", (2000, 1000))
    panel = next(p for p in iter_panels(t2) if p.id == "aaaa1111")
    assert panel.asset == "/abs/img.png"
    assert panel.asset_px == (2000, 1000)
    # other panel untouched
    other = next(p for p in iter_panels(t2) if p.id == "bbbb2222")
    assert other.asset is None
    # clear
    t3 = ops.set_asset(t2, "aaaa1111", None, None)
    panel3 = next(p for p in iter_panels(t3) if p.id == "aaaa1111")
    assert panel3.asset is None and panel3.asset_px is None


def test_set_asset_errors():
    tree = _two_panel_tree()
    with pytest.raises(KeyError):
        ops.set_asset(tree, "nope", "/a.png", (10, 10))
    with pytest.raises(ValueError):
        ops.set_asset(tree, "aaaa1111", "/a.png", None)
    with pytest.raises(ValueError):
        ops.set_asset(tree, "aaaa1111", None, (10, 10))


def test_sidecar_roundtrip_with_asset():
    tree = ops.set_asset(_two_panel_tree(), "aaaa1111", "img/a.png", (800, 600))
    d = to_dict(tree)
    back = from_dict(d)
    panel = next(p for p in iter_panels(back) if p.id == "aaaa1111")
    assert panel.asset == "img/a.png"
    assert panel.asset_px == (800, 600)  # tuple, not list
    # panel WITHOUT asset serializes with no asset keys
    plain = to_dict(tree)["children"][1]
    assert "asset" not in plain and "asset_px" not in plain


def test_effective_dpi():
    # 2000px over 89mm = 2000 / 3.504in = 570.8 dpi; height axis smaller
    dpi = effective_dpi((2000, 1000), 89.0, 89.0)
    assert dpi == pytest.approx(1000 / (89.0 / 25.4), rel=1e-6)
    with pytest.raises(ValueError):
        effective_dpi((100, 100), 0.0, 10.0)


def test_constraints_min_effective_dpi_default_and_compat():
    assert Constraints().min_effective_dpi == 300
    # old-style constraints dict (no key) still parses
    old = {"figspec_version": "0.1",
           "target": {"journal_preset": "custom", "figure_width_mm": 100.0,
                      "figure_height_mm": 60.0},
           "constraints": {"min_font_pt": 5.0, "max_font_pt": 8.0,
                           "min_linewidth_pt": 0.5},
           "panels": []}
    _t, c, _p, _d = parse_spec(old)
    assert c.min_effective_dpi == 300


def test_spec_export_external_vs_generated():
    doc = DesignerDocument.default()
    doc.tree = ops.set_asset(
        SplitNode("row", (0.5, 0.5),
                  (PanelNode(id="p1"), PanelNode(id="p2"))),
        "p1", "/abs/stem.tif", (4096, 4096))
    spec = doc.to_spec_dict()
    by_label = {p["label"]: p for p in spec["panels"]}
    ext = by_label["a"]
    assert ext["type"] == "external"
    assert ext["asset"] == "/abs/stem.tif"
    assert ext["asset_px"] == [4096, 4096]
    gen = by_label["b"]
    assert "type" not in gen and "asset" not in gen and "asset_px" not in gen
    # round-trip through parse (unknown-key tolerance for the new fields)
    _t, _c, panels, designer = parse_spec(spec)
    assert designer is not None
    # sidecar restore keeps asset
    doc2 = DesignerDocument.from_spec_dict(spec)
    p1 = next(p for p in iter_panels(doc2.tree) if p.id == "p1")
    assert p1.asset == "/abs/stem.tif" and p1.asset_px == (4096, 4096)


def test_relativize_and_resolve(tmp_path):
    img = tmp_path / "figs" / "a.png"
    img.parent.mkdir()
    img.write_bytes(b"fake")
    tree = ops.set_asset(_two_panel_tree(), "aaaa1111", str(img), (10, 10))
    rel = relativize_assets(tree, tmp_path)
    panel = next(p for p in iter_panels(rel) if p.id == "aaaa1111")
    assert panel.asset == "figs/a.png"
    # already-relative path passes through
    rel2 = relativize_assets(rel, tmp_path)
    assert next(p for p in iter_panels(rel2) if p.id == "aaaa1111").asset == "figs/a.png"
    # resolve: relative + base_dir -> absolute existing path
    assert resolve_asset("figs/a.png", tmp_path) == img
    # missing file / no base_dir -> None
    assert resolve_asset("figs/missing.png", tmp_path) is None
    assert resolve_asset("figs/a.png", None) is None
    assert resolve_asset(str(img), None) == img  # absolute needs no base


def test_absolutize_assets(tmp_path):
    img = tmp_path / "figs" / "a.png"
    img.parent.mkdir()
    img.write_bytes(b"fake")
    tree = ops.set_asset(_two_panel_tree(), "aaaa1111", "figs/a.png", (10, 10))
    absolute = absolutize_assets(tree, tmp_path)
    panel = next(p for p in iter_panels(absolute) if p.id == "aaaa1111")
    assert panel.asset == str(img.resolve())
    # already-absolute path passes through unchanged
    absolute2 = absolutize_assets(absolute, tmp_path)
    assert next(p for p in iter_panels(absolute2)
               if p.id == "aaaa1111").asset == str(img.resolve())
    # missing file still absolutizes -- the missing-state must be shown
    # against the right path, not silently skipped
    tree_missing = ops.set_asset(_two_panel_tree(), "aaaa1111",
                                 "figs/missing.png", (10, 10))
    absolutized_missing = absolutize_assets(tree_missing, tmp_path)
    missing_panel = next(p for p in iter_panels(absolutized_missing)
                         if p.id == "aaaa1111")
    assert missing_panel.asset == str((tmp_path / "figs/missing.png").resolve())


def test_to_json_relativizes_only_with_base_dir(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"fake")
    doc = DesignerDocument.default()
    doc.tree = ops.set_asset(PanelNode(id="p1"), "p1", str(img), (10, 10))
    # no base_dir: absolute path kept (clipboard path)
    data = json.loads(doc.to_json())
    assert data["panels"][0]["asset"] == str(img)
    # base_dir: relative in both panels list and sidecar
    data2 = json.loads(doc.to_json(base_dir=tmp_path))
    assert data2["panels"][0]["asset"] == "a.png"
    assert data2["designer"]["tree"]["asset"] == "a.png"
    # in-memory tree still absolute (to_json must not mutate)
    assert next(iter_panels(doc.tree)).asset == str(img)
