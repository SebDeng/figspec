import pytest
from figspec.layout.tree import PanelNode, SplitNode, from_dict, to_dict
from figspec.layout.flatten import flatten
from figspec.layout.ops import (MIN_PANEL_MM, equalize_siblings, set_panel_size,
                                split_panel_n, swap_panels)

A, B, C = PanelNode("A"), PanelNode("B"), PanelNode("C")


def _rects(tree, w=183.0, h=100.0, g=4.0):
    return {r.panel_id: r for r in flatten(tree, w, h, g)}


def test_split_n_wraps_into_equal_children():
    out = split_panel_n(A, "A", "right", 3)
    assert isinstance(out, SplitNode) and out.orientation == "row"
    assert len(out.children) == 3
    assert out.ratios == pytest.approx((1 / 3, 1 / 3, 1 / 3))
    assert out.children[0] == A


def test_split_n_inlines_on_matching_parent():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = split_panel_n(root, "B", "right", 3)
    assert len(out.children) == 4
    assert out.ratios == pytest.approx((0.5, 0.5 / 3, 0.5 / 3, 0.5 / 3))


def test_split_n_bounds():
    with pytest.raises(ValueError):
        split_panel_n(A, "A", "right", 1)
    with pytest.raises(ValueError):
        split_panel_n(A, "A", "right", 9)


def test_split_n_min_size_guard():
    # 183mm page: 12-way... n max is 8; craft narrow: wrap A(10mm wide) — parent
    root = SplitNode("row", (10 / 179, 169 / 179), (A, B))  # A ~10mm on 183/4 page
    with pytest.raises(ValueError):
        # A is ~10mm; splitting into 8 → real children well under MIN_PANEL_MM
        split_panel_n(root, "A", "right", 8,
                      page_w_mm=183.0, page_h_mm=100.0, gutter_mm=4.0)
    # Structure-only mode (no page dims given) skips the size guard entirely.
    out = split_panel_n(root, "A", "right", 8)
    assert len(out.children) == 9


def test_split_n_dims_guard_catches_gutter_shrunk_sibling():
    # Reviewer repro: splitting C adds a gutter to the row, which alone (with
    # C's ratio unchanged) shrinks its sibling D from 5.2mm to 4.8mm -- below
    # MIN_PANEL_MM -- even though the guard only directly touches C's children.
    C2, D = PanelNode("C"), PanelNode("D")
    root = SplitNode("row", (0.9, 0.1), (C2, D))
    r = _rects(root, w=56.0, h=100.0, g=4.0)
    assert r["D"].w_mm == pytest.approx(5.2)  # fine before the op
    with pytest.raises(ValueError):
        split_panel_n(root, "C", "right", 2,
                      page_w_mm=56.0, page_h_mm=100.0, gutter_mm=4.0)


def test_split_n_dims_guard_ignores_preexisting_violation():
    # E is already ~3.84mm tall (root ratio 0.04 on a 96mm avail column) before
    # the op ever runs; the op only touches F, inside the unrelated row branch
    # alongside G. The op must not be blamed for a violation it didn't cause.
    F, G, E = PanelNode("F"), PanelNode("G"), PanelNode("E")
    top_row = SplitNode("row", (0.5, 0.5), (F, G))
    root = SplitNode("column", (0.96, 0.04), (top_row, E))
    before = _rects(root, w=100.0, h=100.0, g=4.0)
    assert before["E"].h_mm == pytest.approx(3.84)
    out = split_panel_n(root, "F", "right", 2,
                        page_w_mm=100.0, page_h_mm=100.0, gutter_mm=4.0)
    r = _rects(out, w=100.0, h=100.0, g=4.0)
    assert r["E"].h_mm == pytest.approx(3.84)  # untouched, still sub-5mm, no error
    assert r["F"].w_mm == pytest.approx(23.0)


def test_equalize_siblings():
    root = SplitNode("row", (0.7, 0.2, 0.1), (A, B, C))
    out = equalize_siblings(root, "B")
    assert out.ratios == pytest.approx((1 / 3, 1 / 3, 1 / 3))
    with pytest.raises(ValueError):
        equalize_siblings(A, "A")


def test_swap_panels_preserves_fields():
    b2 = PanelNode("B", content_hint="hero", aspect_lock=1.0)
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (b2, C))))
    out = swap_panels(root, "A", "B")
    assert out.children[0].id == "B" and out.children[0].content_hint == "hero"
    assert out.children[0].aspect_lock == 1.0
    inner = out.children[1].children[0]
    assert inner.id == "A"
    with pytest.raises(KeyError):
        swap_panels(root, "A", "zz")
    with pytest.raises(ValueError):
        swap_panels(root, "A", "A")


def test_set_panel_size_width():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = set_panel_size(root, "A", "w", 100.0, 183.0, 100.0, 4.0)
    r = _rects(out)
    assert r["A"].w_mm == pytest.approx(100.0)
    assert r["B"].w_mm == pytest.approx(79.0)  # 179 - 100


def test_set_panel_size_nested_height():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    out = set_panel_size(root, "B", "h", 60.0, 183.0, 100.0, 4.0)
    r = _rects(out)
    assert r["B"].h_mm == pytest.approx(60.0)
    assert r["C"].h_mm == pytest.approx(36.0)  # 96 - 60


def test_set_panel_size_not_adjustable():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    with pytest.raises(ValueError, match="not adjustable"):
        set_panel_size(root, "A", "h", 50.0, 183.0, 100.0, 4.0)  # h fixed by page


def test_set_panel_size_guard():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    with pytest.raises(ValueError):
        set_panel_size(root, "A", "w", 176.0, 183.0, 100.0, 4.0)  # B -> 3mm


def test_aspect_lock_roundtrip():
    p = PanelNode("p", aspect_lock=1.5)
    d = to_dict(p)
    assert d["aspect_lock"] == 1.5
    assert from_dict(d).aspect_lock == 1.5
    d2 = to_dict(PanelNode("q"))
    assert "aspect_lock" not in d2
    assert from_dict(d2).aspect_lock is None
