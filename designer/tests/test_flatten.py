import pytest
from figspec_designer.model.tree import PanelNode, SplitNode
from figspec_designer.model.flatten import assign_labels, derive, flatten

TREE = SplitNode("row", (0.5, 0.5),
                 (PanelNode("A"),
                  SplitNode("column", (0.6, 0.4),
                            (PanelNode("B"), PanelNode("C")))))


def test_flatten_l_shape_exact():
    rects = {r.panel_id: r for r in flatten(TREE, 183.0, 100.0, 4.0)}
    a, b, c = rects["A"], rects["B"], rects["C"]
    assert (a.x_mm, a.y_mm, a.w_mm, a.h_mm) == (0.0, 0.0, 89.5, 100.0)
    assert (b.x_mm, b.y_mm, b.w_mm, b.h_mm) == (93.5, 0.0, 89.5, 57.6)
    assert (c.x_mm, c.y_mm, c.w_mm, c.h_mm) == (93.5, 61.6, 89.5, 38.4)


def test_labels_reading_order():
    labels = assign_labels(flatten(TREE, 183.0, 100.0, 4.0))
    assert labels == {"A": "a", "B": "b", "C": "c"}


def test_labels_beyond_z():
    from figspec_designer.model.flatten import PanelRect
    rects = [PanelRect(f"p{i}", float(i), 0.0, 1.0, 1.0) for i in range(28)]
    labels = assign_labels(rects)
    assert labels["p25"] == "z" and labels["p26"] == "aa" and labels["p27"] == "ab"


def test_derive():
    from figspec_designer.model.flatten import PanelRect
    w_px, h_px, figsize = derive(PanelRect("x", 0, 0, 89.5, 50.0), 600)
    assert (w_px, h_px) == (2114, 1181)
    assert figsize == (pytest.approx(3.524, abs=0.001), pytest.approx(1.969, abs=0.001))
