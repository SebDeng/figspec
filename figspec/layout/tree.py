"""Pure layout tree. No Qt imports allowed in this package."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Iterator, Union


@dataclass(frozen=True)
class PanelNode:
    id: str
    content_hint: str = ""
    aspect_lock: float | None = None
    asset: str | None = None
    asset_px: tuple[int, int] | None = None
    asset_dpi: float | None = None  # declared source resolution; None = assumed


@dataclass(frozen=True)
class SplitNode:
    orientation: str  # "row" = children side by side; "column" = stacked
    ratios: tuple[float, ...]
    children: tuple["Node", ...]

    def __post_init__(self):
        if self.orientation not in ("row", "column"):
            raise ValueError(f"orientation must be row|column, got {self.orientation!r}")
        if len(self.ratios) != len(self.children):
            raise ValueError("ratios and children must have equal length")


Node = Union[PanelNode, SplitNode]


def new_panel() -> PanelNode:
    return PanelNode(id=uuid.uuid4().hex[:8])


def iter_panels(node: Node) -> Iterator[PanelNode]:
    if isinstance(node, PanelNode):
        yield node
    else:
        for child in node.children:
            yield from iter_panels(child)


def to_dict(node: Node) -> dict:
    if isinstance(node, PanelNode):
        d = {"type": "panel", "id": node.id, "content_hint": node.content_hint}
        if node.aspect_lock is not None:
            d["aspect_lock"] = node.aspect_lock
        if node.asset is not None:
            d["asset"] = node.asset
            d["asset_px"] = list(node.asset_px)
        if node.asset_dpi is not None:
            d["asset_dpi"] = node.asset_dpi
        return d
    return {
        "type": "split",
        "orientation": node.orientation,
        "ratios": list(node.ratios),
        "children": [to_dict(c) for c in node.children],
    }


def from_dict(d: dict) -> Node:
    kind = d.get("type")
    if kind == "panel":
        raw_px = d.get("asset_px")
        raw_dpi = d.get("asset_dpi")
        return PanelNode(id=d["id"], content_hint=d.get("content_hint", ""),
                         aspect_lock=d.get("aspect_lock"),
                         asset=d.get("asset"),
                         asset_px=tuple(int(v) for v in raw_px) if raw_px else None,
                         asset_dpi=float(raw_dpi) if raw_dpi is not None else None)
    if kind == "split":
        return SplitNode(
            d["orientation"],
            tuple(float(r) for r in d["ratios"]),
            tuple(from_dict(c) for c in d["children"]),
        )
    raise ValueError(f"unknown node type: {kind!r}")
