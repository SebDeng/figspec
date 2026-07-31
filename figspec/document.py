"""Document = layout tree + target + constraints; bridges model and figspec.spec."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path
from figspec.spec import Constraints, PanelSpec, Target, build_spec, parse_spec
from figspec import presets
from figspec.layout import ops
from figspec.layout.flatten import PanelRect, assign_labels, derive, flatten
from figspec.layout.tree import Node, from_dict, iter_panels, new_panel, to_dict


class MissingDesignerData(Exception):
    """figspec.json lacks the designer.tree sidecar needed for editing."""


@dataclass
class DesignerDocument:
    tree: Node
    target: Target
    constraints: Constraints

    @classmethod
    def default(cls) -> "DesignerDocument":
        return cls(
            tree=new_panel(),
            target=Target("nature_double", presets.PRESETS["nature_double"],
                          presets.DEFAULT_HEIGHT_MM, presets.DEFAULT_DPI,
                          presets.DEFAULT_GUTTER_MM),
            constraints=Constraints(**presets.PRESET_CONSTRAINTS["nature_double"]),
        )

    def panel_rects(self) -> list[PanelRect]:
        return flatten(self.tree, self.target.figure_width_mm,
                       self.target.figure_height_mm, self.target.gutter_mm)

    def labels(self) -> dict[str, str]:
        return assign_labels(self.panel_rects())

    def to_spec_dict(self) -> dict:
        rects = self.panel_rects()
        labels = self.labels()
        hints = {p.id: p.content_hint for p in iter_panels(self.tree)}
        assets = {p.id: (p.asset, p.asset_px) for p in iter_panels(self.tree)}
        panels = []
        for rect in sorted(rects, key=lambda r: (round(r.y_mm, 1), r.x_mm)):
            w_px, h_px, figsize = derive(rect, self.target.dpi)
            asset, asset_px = assets[rect.panel_id]
            panels.append(PanelSpec(
                label=labels[rect.panel_id],
                x_mm=rect.x_mm, y_mm=rect.y_mm, w_mm=rect.w_mm, h_mm=rect.h_mm,
                w_px=w_px, h_px=h_px, figsize_in=figsize,
                content_hint=hints[rect.panel_id],
                type="external" if asset else None,
                asset=asset, asset_px=asset_px,
            ))
        return build_spec(self.target, self.constraints, panels,
                          designer={"tree": to_dict(self.tree)})

    def to_json(self, base_dir=None) -> str:
        doc = self
        if base_dir is not None:
            doc = DesignerDocument(relativize_assets(self.tree, base_dir),
                                   self.target, self.constraints)
        return json.dumps(doc.to_spec_dict(), indent=2) + "\n"

    @classmethod
    def from_spec_dict(cls, data: dict) -> "DesignerDocument":
        target, constraints, _panels, designer = parse_spec(data)
        if not designer or "tree" not in designer:
            raise MissingDesignerData(
                "this figspec.json has no designer layout data; "
                "V1 cannot reconstruct a tree from panel rectangles")
        return cls(tree=from_dict(designer["tree"]), target=target,
                   constraints=constraints)


def relativize_assets(tree: Node, base_dir) -> Node:
    """Return a tree whose absolute asset paths are rewritten relative to
    base_dir (best effort — unconvertible paths pass through unchanged)."""
    out = tree
    for p in iter_panels(tree):
        if p.asset and Path(p.asset).is_absolute():
            try:
                rel = os.path.relpath(p.asset, base_dir)
            except ValueError:
                continue
            out = ops.set_asset(out, p.id, rel, p.asset_px)
    return out


def absolutize_assets(tree: Node, base_dir) -> Node:
    """Return a tree whose relative asset paths are rewritten to absolute,
    resolved against base_dir (mirrors relativize_assets). A missing file
    still absolutizes -- the caller needs the right path to show the
    missing-state against, not a silent skip."""
    out = tree
    for p in iter_panels(tree):
        if p.asset and not Path(p.asset).is_absolute():
            abs_path = str((Path(base_dir) / p.asset).resolve())
            out = ops.set_asset(out, p.id, abs_path, p.asset_px)
    return out


def resolve_asset(asset: str, base_dir) -> Path | None:
    """Absolute or base_dir-relative asset path -> existing Path, else None."""
    p = Path(asset)
    if not p.is_absolute():
        if base_dir is None:
            return None
        p = Path(base_dir) / p
    return p if p.exists() else None
