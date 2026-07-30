"""Pure layout tree. No Qt imports allowed in this package."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Iterator, Union


@dataclass(frozen=True)
class PanelNode:
    id: str
    content_hint: str = ""


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
        return {"type": "panel", "id": node.id, "content_hint": node.content_hint}
    return {
        "type": "split",
        "orientation": node.orientation,
        "ratios": list(node.ratios),
        "children": [to_dict(c) for c in node.children],
    }


def from_dict(d: dict) -> Node:
    kind = d.get("type")
    if kind == "panel":
        return PanelNode(id=d["id"], content_hint=d.get("content_hint", ""))
    if kind == "split":
        return SplitNode(
            d["orientation"],
            tuple(float(r) for r in d["ratios"]),
            tuple(from_dict(c) for c in d["children"]),
        )
    raise ValueError(f"unknown node type: {kind!r}")
