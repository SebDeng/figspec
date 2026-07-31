from figspec.layout.flatten import assign_labels, flatten
from figspec.layout.tree import SplitNode, iter_panels
from figspec.templates import TEMPLATES


def _panel_count(key):
    return len(list(iter_panels(TEMPLATES[key].build())))


def test_registry_keys_and_metadata():
    assert set(TEMPLATES) == {"quantitative_grid", "hero_left",
                              "image_plate", "asymmetric"}
    for key, t in TEMPLATES.items():
        assert t.key == key
        assert t.title and t.description


def test_panel_counts():
    assert _panel_count("quantitative_grid") == 6
    assert _panel_count("hero_left") == 3
    assert _panel_count("image_plate") == 12
    assert _panel_count("asymmetric") == 4


def test_quantitative_grid_shape():
    tree = TEMPLATES["quantitative_grid"].build()
    assert isinstance(tree, SplitNode) and tree.orientation == "column"
    assert len(tree.children) == 2
    for row in tree.children:
        assert row.orientation == "row" and len(row.children) == 3
        assert all(abs(r - 1 / 3) < 1e-9 for r in row.ratios)


def test_hero_left_ratios():
    tree = TEMPLATES["hero_left"].build()
    assert tree.orientation == "row"
    assert tree.ratios == (0.6, 0.4)
    right = tree.children[1]
    assert right.orientation == "column" and len(right.children) == 2


def test_asymmetric_labels_read_top_then_bottom():
    tree = TEMPLATES["asymmetric"].build()
    rects = flatten(tree, 183.0, 100.0, 4.0)
    labels = set(assign_labels(rects).values())
    assert labels == {"a", "b", "c", "d"}


def test_build_returns_fresh_ids():
    t = TEMPLATES["hero_left"]
    ids1 = {p.id for p in iter_panels(t.build())}
    ids2 = {p.id for p in iter_panels(t.build())}
    assert ids1.isdisjoint(ids2)


def test_all_templates_respect_min_panel_on_default_page():
    # 183 x 100 mm, 4 mm gutter (nature_double defaults) — no panel < 5 mm
    for t in TEMPLATES.values():
        rects = flatten(t.build(), 183.0, 100.0, 4.0)
        assert all(r.w_mm >= 5.0 and r.h_mm >= 5.0 for r in rects), t.key
