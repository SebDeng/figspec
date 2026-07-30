import pytest
from figspec_designer.model.tree import (PanelNode, SplitNode, from_dict,
                                         iter_panels, new_panel, to_dict)


def test_new_panel_ids_unique():
    a, b = new_panel(), new_panel()
    assert a.id != b.id and len(a.id) == 8


def test_split_validation():
    p = PanelNode("p1")
    with pytest.raises(ValueError):
        SplitNode("diagonal", (1.0,), (p,))
    with pytest.raises(ValueError):
        SplitNode("row", (0.5,), (p, PanelNode("p2")))


def test_iter_panels_order():
    tree = SplitNode("row", (0.5, 0.5),
                     (PanelNode("a"),
                      SplitNode("column", (0.5, 0.5),
                                (PanelNode("b"), PanelNode("c")))))
    assert [p.id for p in iter_panels(tree)] == ["a", "b", "c"]


def test_dict_roundtrip():
    tree = SplitNode("row", (0.6, 0.4),
                     (PanelNode("a", content_hint="hero"), PanelNode("b")))
    d = to_dict(tree)
    assert d["type"] == "split" and d["children"][0]["content_hint"] == "hero"
    assert from_dict(d) == tree
    with pytest.raises(ValueError):
        from_dict({"type": "mystery"})
