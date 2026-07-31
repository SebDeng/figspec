"""Document = layout tree + target + constraints; bridges model and figspec.spec."""
from __future__ import annotations
import json
from dataclasses import dataclass
from figspec.spec import Constraints, PanelSpec, Target, build_spec, parse_spec
from figspec import presets
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
        panels = []
        for rect in sorted(rects, key=lambda r: (round(r.y_mm, 1), r.x_mm)):
            w_px, h_px, figsize = derive(rect, self.target.dpi)
            panels.append(PanelSpec(
                label=labels[rect.panel_id],
                x_mm=rect.x_mm, y_mm=rect.y_mm, w_mm=rect.w_mm, h_mm=rect.h_mm,
                w_px=w_px, h_px=h_px, figsize_in=figsize,
                content_hint=hints[rect.panel_id],
            ))
        return build_spec(self.target, self.constraints, panels,
                          designer={"tree": to_dict(self.tree)})

    def to_json(self) -> str:
        return json.dumps(self.to_spec_dict(), indent=2) + "\n"

    @classmethod
    def from_spec_dict(cls, data: dict) -> "DesignerDocument":
        target, constraints, _panels, designer = parse_spec(data)
        if not designer or "tree" not in designer:
            raise MissingDesignerData(
                "this figspec.json has no designer layout data; "
                "V1 cannot reconstruct a tree from panel rectangles")
        return cls(tree=from_dict(designer["tree"]), target=target,
                   constraints=constraints)
