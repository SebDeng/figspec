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

# Height ceilings (mm, figure area incl. caption allowance) -- sources and
# the reasoning for each pick are in docs/journal-figure-specs.md
# ("FigSpec 取值决策"). None = publisher states no numeric limit -> no warning.
MAX_HEIGHT_MM: dict[str, float | None] = {
    "nature_single": 170.0,
    "nature_double": 170.0,
    "nature_research_single": 185.0,
    "nature_research_double": 185.0,
    "science_single": 199.0,
    "science_double": 199.0,
    "acs_single": 232.8,
    "acs_double": 232.8,
    "aps_single": None,
    "aps_double": None,
}

# Panel-letter display style per journal family. Internal/spec labels are
# ALWAYS lowercase a/b/c; only the display layer formats them.
PANEL_LABEL_STYLE: dict[str, str] = {
    "nature_single": "lowercase",
    "nature_double": "lowercase",
    "nature_research_single": "lowercase",
    "nature_research_double": "lowercase",
    "science_single": "uppercase",
    "science_double": "uppercase",
    "acs_single": "lowercase",
    "acs_double": "lowercase",
    "aps_single": "paren_lower",
    "aps_double": "paren_lower",
}

# One-line provenance shown as the preset dropdown's item tooltip.
PRESET_SOURCES: dict[str, str] = {
    "nature_single": "89 mm · Nature final-submission guide (nature.com/nature/for-authors)",
    "nature_double": "183 mm · Nature final-submission guide (nature.com/nature/for-authors)",
    "nature_research_single": "88 mm · NRJs guide to preparing final artwork (PDF)",
    "nature_research_double": "180 mm · NRJs guide to preparing final artwork (PDF)",
    "science_single": "90 mm · Science author prep guide 2025 (PDF)",
    "science_double": "183 mm · Science author prep guide 2025 (PDF)",
    "acs_single": "84.7 mm · ACS TOC/abstract graphics guidelines (pubsapp.acs.org)",
    "acs_double": "177.8 mm · ACS TOC/abstract graphics guidelines (pubsapp.acs.org)",
    "aps_single": "85 mm · APS Journals Style Guide Feb 2026 (PDF)",
    "aps_double": "178 mm · APS Journals Style Guide Feb 2026 (PDF)",
}

DEFAULT_HEIGHT_MM = 100.0
DEFAULT_DPI = 600
DEFAULT_GUTTER_MM = 4.0
