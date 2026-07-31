"""Journal width presets (mm), per-preset constraint defaults, canvas defaults.

Values verified against publisher primary sources on 2026-07-30; per-value
citations, unit conversions and known publisher-side inconsistencies are in
docs/journal-figure-specs.md. aps min_font_pt is DERIVED from APS's 2 mm
cap-height rule (~7.9 pt nominal for Helvetica), not stated in pt by APS.
"""
PRESETS: dict[str, float] = {
    "nature_single": 89.0,
    "nature_double": 183.0,
    "nature_research_single": 88.0,
    "nature_research_double": 180.0,
    "science_single": 90.0,
    "science_double": 183.0,
    "acs_single": 84.7,
    "acs_double": 177.8,
    "aps_single": 85.0,
    "aps_double": 178.0,
}

_NATURE = {"min_font_pt": 5.0, "max_font_pt": 7.0, "min_linewidth_pt": 0.25}
_SCIENCE = {"min_font_pt": 5.0, "max_font_pt": 10.0, "min_linewidth_pt": 0.5}
_ACS = {"min_font_pt": 4.5, "max_font_pt": 8.0, "min_linewidth_pt": 0.5}
_APS = {"min_font_pt": 8.0, "max_font_pt": 10.0, "min_linewidth_pt": 0.5}

PRESET_CONSTRAINTS: dict[str, dict[str, float]] = {
    "nature_single": dict(_NATURE),
    "nature_double": dict(_NATURE),
    "nature_research_single": dict(_NATURE),
    "nature_research_double": dict(_NATURE),
    "science_single": dict(_SCIENCE),
    "science_double": dict(_SCIENCE),
    "acs_single": dict(_ACS),
    "acs_double": dict(_ACS),
    "aps_single": dict(_APS),
    "aps_double": dict(_APS),
}

DEFAULT_HEIGHT_MM = 100.0
DEFAULT_DPI = 600
DEFAULT_GUTTER_MM = 4.0
