"""figspec.json schema helpers shared by the Designer and the CLI.

Coordinate convention (normative): panel ``x_mm``/``y_mm`` use a TOP-LEFT
origin with y increasing DOWNWARD, in millimetres. Consumers working in PDF
coordinates (bottom-left origin, y up) must convert internally.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

FIGSPEC_VERSION = "0.1"


class SpecError(ValueError):
    """Raised when a figspec.json document is malformed."""


@dataclass
class Target:
    journal_preset: str
    figure_width_mm: float
    figure_height_mm: float
    dpi: int = 600
    gutter_mm: float = 4.0


@dataclass
class Constraints:
    min_font_pt: float = 5.0
    max_font_pt: float = 8.0
    min_linewidth_pt: float = 0.5
    min_effective_dpi: int = 300


@dataclass
class PanelSpec:
    label: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    w_px: int
    h_px: int
    figsize_in: tuple[float, float]
    content_hint: str = ""
    type: str | None = None
    asset: str | None = None
    asset_px: tuple[int, int] | None = None


def _panel_dict(p: PanelSpec) -> dict:
    d = {**asdict(p), "figsize_in": [p.figsize_in[0], p.figsize_in[1]]}
    for key in ("type", "asset", "asset_px"):
        if d[key] is None:
            del d[key]
    if "asset_px" in d:
        d["asset_px"] = list(d["asset_px"])
    return d


def build_spec(target: Target, constraints: Constraints,
               panels: list[PanelSpec], designer: dict | None = None) -> dict:
    doc = {
        "figspec_version": FIGSPEC_VERSION,
        "target": asdict(target),
        "constraints": asdict(constraints),
        "panels": [_panel_dict(p) for p in panels],
    }
    if designer is not None:
        doc["designer"] = designer
    return doc


def _require(data: dict, key: str):
    if key not in data:
        raise SpecError(f"missing key: {key}")
    return data[key]


def parse_spec(data: dict):
    if not isinstance(data, dict):
        raise SpecError(f"spec root must be an object, got {type(data).__name__}")
    _require(data, "figspec_version")
    try:
        target = Target(**_require(data, "target"))
        constraints = Constraints(**_require(data, "constraints"))
        raw_panels = _require(data, "panels")
        if not isinstance(raw_panels, list):
            raise SpecError("panels must be a list")
        panels = [
            PanelSpec(**{
                **p,
                "figsize_in": tuple(p["figsize_in"]),
                **({"asset_px": tuple(p["asset_px"])} if p.get("asset_px") else {}),
            })
            for p in raw_panels
        ]
    except SpecError:
        raise
    except (TypeError, KeyError, ValueError) as e:
        raise SpecError(f"malformed spec: {e}") from e
    return target, constraints, panels, data.get("designer")
