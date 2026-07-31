"""figspec.standins: vocabulary, determinism, inference, role table."""
import pytest

from figspec import standins
from figspec.spec import Constraints


def test_vocabulary_frozen():
    assert standins.ARCHETYPES == ("line", "scatter", "bar", "heatmap",
                                   "micrograph")


def test_infer_keywords():
    assert standins.infer("STEM image + FFT inset") == "micrograph"
    assert standins.infer("Raman spectra") == "line"
    assert standins.infer("size distribution HISTOGRAM") == "bar"
    assert standins.infer("correlation matrix") == "heatmap"  # beats scatter
    assert standins.infer("correlation of x vs y") == "scatter"
    assert standins.infer("") is None
    assert standins.infer("something unrecognizable") is None


def test_pseudo_data_deterministic():
    for archetype in standins.ARCHETYPES:
        a = standins.pseudo_data(archetype, "panel-1")
        b = standins.pseudo_data(archetype, "panel-1")
        c = standins.pseudo_data(archetype, "panel-2")
        assert a == b
        assert a != c


def test_pseudo_data_in_unit_range():
    d = standins.pseudo_data("line", "s")
    assert all(0.0 <= y <= 1.0 for pts in d["series"] for y in pts)
    d = standins.pseudo_data("heatmap", "s")
    assert all(0.0 <= v <= 1.0 for row in d["grid"] for v in row)
    d = standins.pseudo_data("scatter", "s")
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in d["points"])


def test_pseudo_data_rejects_unknown():
    with pytest.raises(ValueError):
        standins.pseudo_data("piechart", "s")


def test_roles_nature_and_science():
    nature = standins.roles(Constraints(min_font_pt=5.0, max_font_pt=7.0,
                                        min_linewidth_pt=0.25))
    assert nature["furniture_font_pt"] == 5.0
    assert nature["furniture_line_pt"] == 0.25
    assert nature["data_stroke_pt"] == pytest.approx(0.75)
    science = standins.roles(Constraints(min_font_pt=5.0, max_font_pt=10.0,
                                         min_linewidth_pt=0.5))
    assert science["data_stroke_pt"] == 1.0  # 3× capped at 1 pt
