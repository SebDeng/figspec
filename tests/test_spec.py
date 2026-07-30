import pytest
from figspec.spec import (FIGSPEC_VERSION, Constraints, PanelSpec, SpecError,
                          Target, build_spec, parse_spec)

T = Target("nature_double", 183.0, 100.0)
C = Constraints()
P = PanelSpec("a", 0.0, 0.0, 89.5, 50.0, 2114, 1181, (3.524, 1.969), "STEM image")


def test_build_shape():
    d = build_spec(T, C, [P], designer={"tree": {"type": "panel", "id": "x"}})
    assert d["figspec_version"] == FIGSPEC_VERSION
    assert d["target"]["figure_width_mm"] == 183.0
    assert d["constraints"]["min_font_pt"] == 5.0
    assert d["panels"][0] == {
        "label": "a", "x_mm": 0.0, "y_mm": 0.0, "w_mm": 89.5, "h_mm": 50.0,
        "w_px": 2114, "h_px": 1181, "figsize_in": [3.524, 1.969],
        "content_hint": "STEM image",
    }
    assert d["designer"]["tree"]["id"] == "x"


def test_build_omits_designer_when_none():
    assert "designer" not in build_spec(T, C, [P])


def test_roundtrip():
    d = build_spec(T, C, [P], designer={"tree": {"k": 1}})
    t2, c2, panels2, designer2 = parse_spec(d)
    assert t2 == T and c2 == C and panels2 == [P]
    assert designer2 == {"tree": {"k": 1}}


def test_parse_errors():
    with pytest.raises(SpecError):
        parse_spec({})
    with pytest.raises(SpecError):
        parse_spec({"figspec_version": "0.1", "target": {}, "constraints": {},
                    "panels": "not-a-list"})
