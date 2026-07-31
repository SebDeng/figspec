"""Archetype layout templates, shared by the Designer and (later) the MCP
server. build() returns a fresh tree — new panel ids — on every call."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from figspec.layout.tree import Node, SplitNode, new_panel


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    description: str
    build: Callable[[], Node]


def _row(cols: int) -> SplitNode:
    return SplitNode("row", tuple(1 / cols for _ in range(cols)),
                     tuple(new_panel() for _ in range(cols)))


def _grid(rows: int, cols: int) -> Node:
    if rows == 1:
        return _row(cols)
    return SplitNode("column", tuple(1 / rows for _ in range(rows)),
                     tuple(_row(cols) for _ in range(rows)))


def _hero_left() -> Node:
    right = SplitNode("column", (0.5, 0.5), (new_panel(), new_panel()))
    return SplitNode("row", (0.6, 0.4), (new_panel(), right))


def _asymmetric() -> Node:
    return SplitNode("column", (0.5, 0.5), (new_panel(), _row(3)))


TEMPLATES: dict[str, Template] = {
    "quantitative_grid": Template(
        "quantitative_grid", "Quantitative grid",
        "2 × 3 equal grid — parameter sweeps, spectra series.",
        lambda: _grid(2, 3)),
    "hero_left": Template(
        "hero_left", "Hero left",
        "Full-height feature panel (60%) with two stacked companions.",
        _hero_left),
    "image_plate": Template(
        "image_plate", "Image plate",
        "3 × 4 micrograph plate — pair with a small gutter.",
        lambda: _grid(3, 4)),
    "asymmetric": Template(
        "asymmetric", "Asymmetric",
        "Full-width hero row over three equal panels.",
        _asymmetric),
}
