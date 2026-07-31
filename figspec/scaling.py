"""Placement-scale math for hand-authored assets.

A source canvas (often pixel-based) gets scaled by k = panel / source when
placed; every nominal pt value inside it becomes nominal × k effective.
Pure functions shared by the Designer (sidebar calculator, specimen strip,
authoring card) and, later, MCP/CLI.
"""
from __future__ import annotations
import math

MM_PER_IN = 25.4


def asset_size_mm(asset_px: tuple[int, int], dpi: float) -> tuple[float, float]:
    """Physical size of a pixel canvas under a declared resolution."""
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    return (asset_px[0] / dpi * MM_PER_IN, asset_px[1] / dpi * MM_PER_IN)


def placement_scale(panel_mm: tuple[float, float],
                    src_mm: tuple[float, float]) -> float:
    """Uniform letterbox scale fitting src into panel: min of the two axis
    ratios (matches the canvas thumbnail's KeepAspectRatio placement)."""
    if src_mm[0] <= 0 or src_mm[1] <= 0:
        raise ValueError("source size must be positive")
    return min(panel_mm[0] / src_mm[0], panel_mm[1] / src_mm[1])


def effective_pt(nominal_pt: float, k: float) -> float:
    return nominal_pt * k


def required_nominal_pt(target_effective_pt: float, k: float) -> float:
    if k <= 0:
        raise ValueError("scale must be positive")
    return target_effective_pt / k


def required_px(panel_mm: tuple[float, float],
                min_effective_dpi: int) -> tuple[int, int]:
    """Smallest raster export (px) that still meets the DPI floor at panel
    size. Ceils: a fractional pixel short means a fractional dpi short."""
    return (math.ceil(panel_mm[0] / MM_PER_IN * min_effective_dpi),
            math.ceil(panel_mm[1] / MM_PER_IN * min_effective_dpi))


def authoring_card(panel_mm: tuple[float, float], constraints,
                   asset_px: tuple[int, int] | None = None,
                   asset_dpi: float | None = None) -> str:
    """The hand-tool counterpart of the matplotlib snippet: what to author
    at, in the tool's own units, so effective values land inside the
    constraints. Option 1 always; Options 2/3 only when a raster source
    exists (and 2 additionally needs a usable dpi declaration)."""
    w_mm, h_mm = panel_mm
    lines = [
        f"FigSpec authoring card — panel target {w_mm:.1f} × {h_mm:.1f} mm",
        "Option 1 — resize your canvas (golden path):",
        f"  Set your canvas to {w_mm:.1f} × {h_mm:.1f} mm "
        f"({w_mm / MM_PER_IN:.2f} × {h_mm / MM_PER_IN:.2f} in) "
        "and use final values:",
        f"  fonts {constraints.min_font_pt:.1f}–{constraints.max_font_pt:.1f} pt, "
        f"lines ≥ {constraints.min_linewidth_pt:g} pt.",
    ]
    if asset_px is not None and asset_dpi is not None and asset_dpi > 0:
        k = placement_scale(panel_mm, asset_size_mm(asset_px, asset_dpi))
        if k > 0:
            lines += [
                f"Option 2 — keep your canvas ({asset_px[0]} × {asset_px[1]} px "
                f"@ {asset_dpi:g} dpi, placed at ×{k:.3f}):",
                f"  fonts {required_nominal_pt(constraints.min_font_pt, k):.1f}"
                f"–{required_nominal_pt(constraints.max_font_pt, k):.1f} pt, "
                f"lines ≥ {required_nominal_pt(constraints.min_linewidth_pt, k):.1f} pt.",
            ]
    if asset_px is not None:
        px = required_px(panel_mm, constraints.min_effective_dpi)
        lines += [
            "Option 3 — raster export target:",
            f"  export at ≥ {px[0]} × {px[1]} px "
            f"for ≥ {constraints.min_effective_dpi} dpi effective.",
        ]
    return "\n".join(lines)
