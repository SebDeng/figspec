import pytest

from figspec import presets
from figspec.layout.flatten import format_label
from figspec.spec import Constraints, parse_spec


def test_journal_dicts_cover_every_preset():
    for d in (presets.MAX_HEIGHT_MM, presets.PANEL_LABEL_STYLE,
              presets.PRESET_SOURCES):
        assert set(d) == set(presets.PRESETS)


def test_max_height_values():
    assert presets.MAX_HEIGHT_MM["nature_double"] == 170.0
    assert presets.MAX_HEIGHT_MM["nature_research_double"] == 185.0
    assert presets.MAX_HEIGHT_MM["science_single"] == 199.0
    assert presets.MAX_HEIGHT_MM["acs_double"] == 232.8
    assert presets.MAX_HEIGHT_MM["aps_single"] is None


def test_panel_label_styles():
    assert presets.PANEL_LABEL_STYLE["nature_double"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["nature_research_single"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["acs_single"] == "lowercase"
    assert presets.PANEL_LABEL_STYLE["science_double"] == "uppercase"
    assert presets.PANEL_LABEL_STYLE["aps_double"] == "paren_lower"


def test_preset_sources_mention_width():
    for key, text in presets.PRESET_SOURCES.items():
        assert f"{presets.PRESETS[key]:g}" in text, key


def test_format_label():
    assert format_label("a", "lowercase") == "a"
    assert format_label("b", "uppercase") == "B"
    assert format_label("c", "paren_lower") == "(c)"
    assert format_label("aa", "uppercase") == "AA"
    # unknown style falls back to identity, never raises
    assert format_label("a", "bogus") == "a"


def test_constraints_style_default_and_compat():
    assert Constraints().panel_label_style == "lowercase"
    old = {"figspec_version": "0.1",
           "target": {"journal_preset": "custom", "figure_width_mm": 100.0,
                      "figure_height_mm": 60.0},
           "constraints": {"min_font_pt": 5.0, "max_font_pt": 8.0,
                           "min_linewidth_pt": 0.5},
           "panels": []}
    _t, c, _p, _d = parse_spec(old)
    assert c.panel_label_style == "lowercase"
