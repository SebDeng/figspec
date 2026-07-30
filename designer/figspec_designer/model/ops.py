"""Pure tree operations. Every function returns a new tree."""
from __future__ import annotations
from dataclasses import replace
from figspec_designer.model.tree import Node, PanelNode, SplitNode, new_panel

_ORIENT = {"right": "row", "down": "column"}


def split_panel(root: Node, panel_id: str, direction: str) -> Node:
    if direction not in _ORIENT:
        raise ValueError(f"direction must be right|down, got {direction!r}")
    orient = _ORIENT[direction]

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id != panel_id:
                return node
            return SplitNode(orient, (0.5, 0.5), (node, new_panel()))
        children: list[Node] = []
        ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            if (isinstance(child, PanelNode) and child.id == panel_id
                    and node.orientation == orient):
                children.extend([child, new_panel()])
                ratios.extend([ratio / 2, ratio / 2])
            else:
                children.append(rec(child))
                ratios.append(ratio)
        if all(a is b for a, b in zip(children, node.children)) \
                and len(children) == len(node.children):
            return node
        return SplitNode(node.orientation, tuple(ratios), tuple(children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def close_panel(root: Node, panel_id: str) -> Node:
    if isinstance(root, PanelNode):
        if root.id == panel_id:
            raise ValueError("cannot close the last remaining panel")
        raise KeyError(panel_id)

    def rec(node: Node):
        if isinstance(node, PanelNode):
            return None if node.id == panel_id else node
        kept_children: list[Node] = []
        kept_ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            rc = rec(child)
            if rc is not None:
                kept_children.append(rc)
                kept_ratios.append(ratio)
        unchanged = (len(kept_children) == len(node.children)
                     and all(a is b for a, b in zip(kept_children, node.children)))
        if unchanged:
            return node
        if not kept_children:
            return None
        if len(kept_children) == 1:
            return kept_children[0]
        total = sum(kept_ratios)
        return SplitNode(node.orientation,
                         tuple(r / total for r in kept_ratios),
                         tuple(kept_children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    if out is None:
        raise ValueError("cannot close the last remaining panel")
    return out


def node_at(root: Node, path: tuple[int, ...]) -> Node:
    node = root
    for i in path:
        node = node.children[i]
    return node


def set_ratios(root: Node, path: tuple[int, ...], ratios) -> Node:
    ratios = tuple(float(r) for r in ratios)
    total = sum(ratios)
    if total <= 0:
        raise ValueError("ratios must sum to a positive value")
    ratios = tuple(r / total for r in ratios)

    def rec(node: Node, path: tuple[int, ...]) -> Node:
        if not path:
            if not isinstance(node, SplitNode) or len(ratios) != len(node.children):
                raise ValueError("path does not address a matching SplitNode")
            return SplitNode(node.orientation, ratios, node.children)
        if not isinstance(node, SplitNode):
            raise ValueError("path descends through a panel")
        i = path[0]
        children = list(node.children)
        children[i] = rec(children[i], path[1:])
        return SplitNode(node.orientation, node.ratios, tuple(children))

    return rec(root, tuple(path))


def set_content_hint(root: Node, panel_id: str, text: str) -> Node:
    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                return replace(node, content_hint=text)
            return node
        children = tuple(rec(c) for c in node.children)
        if all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, node.ratios, children)

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def snap_ratios(ratios, avail_mm: float, step: float = 0.5) -> tuple[float, ...]:
    ratios = tuple(float(r) for r in ratios)
    sizes = [r * avail_mm for r in ratios]
    snapped = [round(s / step) * step for s in sizes[:-1]]
    if any(s < step for s in snapped):
        return ratios
    last = avail_mm - sum(snapped)
    if last < step:
        return ratios
    snapped.append(last)
    return tuple(s / avail_mm for s in snapped)
