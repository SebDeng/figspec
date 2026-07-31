"""Pure tree operations. Every function returns a new tree."""
from __future__ import annotations
from dataclasses import replace
from figspec.layout.flatten import flatten
from figspec.layout.tree import Node, PanelNode, SplitNode, iter_panels, new_panel

_ORIENT = {"right": "row", "down": "column"}

MIN_PANEL_MM = 5.0


def _guard_min_panels(old_root: Node, new_root: Node, page_w_mm: float,
                      page_h_mm: float, gutter_mm: float, *,
                      produced_ids: frozenset[str] = frozenset()) -> None:
    """Compare every panel's real rect on old_root vs. new_root (via
    flatten) and raise ValueError for any panel -- one newly produced by
    the change (in produced_ids), or any pre-existing panel the change
    itself shrunk -- that ends up below MIN_PANEL_MM. Panels that were
    already sub-MIN_PANEL_MM before the change, and aren't newly produced,
    are left alone: the op isn't blamed for a violation it didn't cause.
    Shared by split_panel, split_panel_n and set_panel_size -- one guard
    implementation (spec A6: 所有产生新几何的操作拒绝 < 5mm panel)."""
    old_rects = {r.panel_id: r for r in flatten(old_root, page_w_mm, page_h_mm, gutter_mm)}
    new_rects = {r.panel_id: r for r in flatten(new_root, page_w_mm, page_h_mm, gutter_mm)}
    for pid, rect in new_rects.items():
        for dim in ("w_mm", "h_mm"):
            new_val = getattr(rect, dim)
            if new_val >= MIN_PANEL_MM - 1e-9:
                continue
            old_rect = old_rects.get(pid)
            was_fine_before = (old_rect is not None
                               and getattr(old_rect, dim) >= MIN_PANEL_MM - 1e-9)
            if pid in produced_ids or was_fine_before:
                raise ValueError(
                    f"operation would shrink a panel below {MIN_PANEL_MM:g} mm")


def split_panel(root: Node, panel_id: str, direction: str, *,
                page_w_mm: float | None = None, page_h_mm: float | None = None,
                gutter_mm: float | None = None) -> Node:
    """Split panel_id in two along direction. When page_w_mm, page_h_mm and
    gutter_mm are all given, applies the same before/after min-size guard
    as split_panel_n (see _guard_min_panels); with no dims given (the
    default), this is structure-only (ratio-space) with no size guard, for
    pure-tree callers that don't have page geometry on hand.
    """
    if direction not in _ORIENT:
        raise ValueError(f"direction must be right|down, got {direction!r}")
    orient = _ORIENT[direction]
    new_ids: list[str] = []

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id != panel_id:
                return node
            new = new_panel()
            new_ids.append(new.id)
            return SplitNode(orient, (0.5, 0.5), (node, new))
        children: list[Node] = []
        ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            if (isinstance(child, PanelNode) and child.id == panel_id
                    and node.orientation == orient):
                new = new_panel()
                new_ids.append(new.id)
                children.extend([child, new])
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

    if page_w_mm is not None and page_h_mm is not None and gutter_mm is not None:
        _guard_min_panels(root, out, page_w_mm, page_h_mm, gutter_mm,
                          produced_ids=frozenset({panel_id, *new_ids}))
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


def set_aspect_lock(root: Node, panel_id: str, value: float | None) -> Node:
    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                return replace(node, aspect_lock=value)
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


def split_panel_n(root: Node, panel_id: str, direction: str, n: int, *,
                  page_w_mm: float | None = None, page_h_mm: float | None = None,
                  gutter_mm: float | None = None) -> Node:
    """Split panel_id into n children along direction (inline on a matching-
    orientation parent, wrapped otherwise); when page_w_mm, page_h_mm and
    gutter_mm are all given, compares every panel's real rect before vs. after
    the split and raises ValueError for any panel -- one of the split's own
    children, or an unrelated sibling shrunk by the split's added gutters --
    that the op itself pushed below MIN_PANEL_MM (panels already sub-MIN_PANEL_MM
    beforehand are left alone), otherwise the split is structure-only
    (ratio-space) with no size guard.
    """
    if not 2 <= n <= 8:
        raise ValueError(f"n must be between 2 and 8, got {n}")
    if direction not in _ORIENT:
        raise ValueError(f"direction must be right|down, got {direction!r}")
    orient = _ORIENT[direction]
    new_ids: list[str] = []

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id != panel_id:
                return node
            ratios = tuple(1.0 / n for _ in range(n))
            new_children = tuple(new_panel() for _ in range(n - 1))
            new_ids.extend(c.id for c in new_children)
            return SplitNode(orient, ratios, (node,) + new_children)
        children: list[Node] = []
        ratios: list[float] = []
        for child, ratio in zip(node.children, node.ratios):
            if (isinstance(child, PanelNode) and child.id == panel_id
                    and node.orientation == orient):
                new_children = tuple(new_panel() for _ in range(n - 1))
                new_ids.extend(c.id for c in new_children)
                children.append(child)
                children.extend(new_children)
                ratios.extend([ratio / n] * n)
            else:
                children.append(rec(child))
                ratios.append(ratio)
        if len(children) == len(node.children) and \
                all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, tuple(ratios), tuple(children))

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)

    if page_w_mm is not None and page_h_mm is not None and gutter_mm is not None:
        _guard_min_panels(root, out, page_w_mm, page_h_mm, gutter_mm,
                          produced_ids=frozenset({panel_id, *new_ids}))

    return out


def equalize_siblings(root: Node, panel_id: str) -> Node:
    if isinstance(root, PanelNode):
        if root.id == panel_id:
            raise ValueError("panel has no siblings")
        raise KeyError(panel_id)

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            return node
        if any(isinstance(c, PanelNode) and c.id == panel_id
               for c in node.children):
            n = len(node.children)
            return SplitNode(node.orientation, tuple(1.0 / n for _ in range(n)),
                             node.children)
        children = tuple(rec(c) for c in node.children)
        if all(a is b for a, b in zip(children, node.children)):
            return node
        return SplitNode(node.orientation, node.ratios, children)

    out = rec(root)
    if out is root:
        raise KeyError(panel_id)
    return out


def swap_panels(root: Node, id_a: str, id_b: str) -> Node:
    if id_a == id_b:
        raise ValueError("cannot swap a panel with itself")
    lookup = {p.id: p for p in iter_panels(root)}
    if id_a not in lookup or id_b not in lookup:
        missing = {id_a, id_b} - lookup.keys()
        raise KeyError(", ".join(sorted(missing)))

    def rec(node: Node) -> Node:
        if isinstance(node, PanelNode):
            if node.id == id_a:
                return lookup[id_b]
            if node.id == id_b:
                return lookup[id_a]
            return node
        return SplitNode(node.orientation, node.ratios,
                         tuple(rec(c) for c in node.children))

    return rec(root)


def set_panel_size(root: Node, panel_id: str, axis: str, size_mm: float,
                   page_w_mm: float, page_h_mm: float, gutter_mm: float) -> Node:
    if axis not in ("w", "h"):
        raise ValueError(f"axis must be 'w' or 'h', got {axis!r}")
    controlling = "row" if axis == "w" else "column"
    target_path: list[int] | None = None

    def find(node: Node, path: list[int]) -> None:
        nonlocal target_path
        if isinstance(node, PanelNode):
            if node.id == panel_id:
                target_path = list(path)
            return
        for i, child in enumerate(node.children):
            find(child, path + [i])

    find(root, [])
    if target_path is None:
        raise KeyError(panel_id)

    # Deepest ancestor SplitNode controlling this axis (row -> w, column -> h)
    # that has >= 2 children -- that's the split whose ratios we adjust.
    best: tuple[list[int], int] | None = None  # (split path, child index within it)
    node: Node = root
    for depth, idx in enumerate(target_path):
        assert isinstance(node, SplitNode)
        if node.orientation == controlling and len(node.children) >= 2:
            best = (target_path[:depth], idx)
        node = node.children[idx]
    if best is None:
        raise ValueError(f"axis {axis!r} not adjustable for this panel")
    split_path, child_idx = best

    # Walk from the page rect down to that split, tracking rect extent along
    # both axes the same way flatten() does, to get the split's actual avail
    # mm along the controlling axis.
    rect_w, rect_h = page_w_mm, page_h_mm
    node = root
    for idx in split_path:
        assert isinstance(node, SplitNode)
        n = len(node.children)
        if node.orientation == "row":
            avail = rect_w - (n - 1) * gutter_mm
            rect_w = avail * node.ratios[idx]
        else:
            avail = rect_h - (n - 1) * gutter_mm
            rect_h = avail * node.ratios[idx]
        node = node.children[idx]
    assert isinstance(node, SplitNode)
    n = len(node.children)
    avail = (rect_w if controlling == "row" else rect_h) - (n - 1) * gutter_mm

    if not MIN_PANEL_MM <= size_mm <= avail - MIN_PANEL_MM * (n - 1):
        raise ValueError(
            f"size {size_mm:g} mm out of range ({MIN_PANEL_MM:g}-"
            f"{avail - MIN_PANEL_MM * (n - 1):g} mm here)")
    remainder = avail - size_mm
    old_others = sum(r for i, r in enumerate(node.ratios) if i != child_idx)
    new_ratios = []
    for i, r in enumerate(node.ratios):
        if i == child_idx:
            new_ratios.append(size_mm / avail)
        else:
            share = (r / old_others) if old_others > 0 else 1.0 / (n - 1)
            new_ratios.append(remainder * share / avail)
    new_root = set_ratios(root, tuple(split_path), tuple(new_ratios))
    # The direct-children check this used to be (any(nr * avail < MIN...))
    # only saw the controlling split's immediate children -- a shrunk
    # DIRECT sibling. It missed panels further down inside a sibling
    # subtree (e.g. a same-axis split nested under an unresized sibling)
    # getting squeezed below MIN_PANEL_MM by the ratio change. The shared
    # flatten guard checks every panel in the whole tree instead.
    _guard_min_panels(root, new_root, page_w_mm, page_h_mm, gutter_mm)
    return new_root
