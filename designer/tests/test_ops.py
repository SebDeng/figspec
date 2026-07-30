import pytest
from figspec_designer.model.tree import PanelNode, SplitNode
from figspec_designer.model.ops import (close_panel, node_at, set_content_hint,
                                        set_ratios, snap_ratios, split_panel)

A, B, C = PanelNode("A"), PanelNode("B"), PanelNode("C")


def test_split_wraps_when_orientation_differs():
    out = split_panel(A, "A", "right")
    assert isinstance(out, SplitNode) and out.orientation == "row"
    assert out.ratios == (0.5, 0.5) and out.children[0] == A


def test_split_inlines_when_orientation_matches():
    root = SplitNode("row", (0.5, 0.3, 0.2), (A, B, C))
    out = split_panel(root, "B", "right")
    assert len(out.children) == 4
    assert out.children[1] == B
    assert out.ratios == pytest.approx((0.5, 0.15, 0.15, 0.2))


def test_split_down_wraps_inside_row():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = split_panel(root, "B", "down")
    inner = out.children[1]
    assert isinstance(inner, SplitNode) and inner.orientation == "column"
    assert inner.children[0] == B


def test_split_errors():
    with pytest.raises(KeyError):
        split_panel(A, "nope", "right")
    with pytest.raises(ValueError):
        split_panel(A, "A", "sideways")


def test_close_renormalizes_and_collapses():
    root = SplitNode("row", (0.5, 0.3, 0.2), (A, B, C))
    out = close_panel(root, "B")
    assert [c.id for c in out.children] == ["A", "C"]
    assert out.ratios == pytest.approx((0.5 / 0.7, 0.2 / 0.7))
    # closing down to one child collapses the split entirely
    assert close_panel(out, "C") == A


def test_close_collapses_nested_single_child():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    out = close_panel(root, "C")
    assert out.children[1] == B  # inner split collapsed away


def test_close_last_panel_forbidden():
    with pytest.raises(ValueError):
        close_panel(A, "A")


def test_set_ratios_by_path():
    root = SplitNode("row", (0.5, 0.5),
                     (A, SplitNode("column", (0.5, 0.5), (B, C))))
    assert node_at(root, (1,)).orientation == "column"
    out = set_ratios(root, (1,), (0.6, 0.4))
    assert out.children[1].ratios == pytest.approx((0.6, 0.4))
    out2 = set_ratios(root, (), (2.0, 2.0))  # normalizes
    assert out2.ratios == pytest.approx((0.5, 0.5))
    with pytest.raises(ValueError):
        set_ratios(root, (0,), (1.0,))  # path points at a panel


def test_set_content_hint():
    root = SplitNode("row", (0.5, 0.5), (A, B))
    out = set_content_hint(root, "B", "inset")
    assert out.children[1].content_hint == "inset"
    with pytest.raises(KeyError):
        set_content_hint(root, "zz", "x")


def test_snap_ratios():
    # 100 mm avail, ratios .333/.667 -> sizes 33.3/66.7 -> snap to 33.5/66.5
    out = snap_ratios((0.333, 0.667), 100.0)
    assert out == pytest.approx((0.335, 0.665))
    # snapping that would starve a child returns input unchanged
    tiny = snap_ratios((0.001, 0.999), 100.0)
    assert tiny == pytest.approx((0.001, 0.999))
