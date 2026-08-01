"""Archetype vocabulary, deterministic pseudo-data and content-hint
inference for panel stand-ins.

Pure Python, no Qt: the vocabulary and data live here so MCP/CLI (and a
future M1 starter-template picker) can reuse them; QPainter rendering is
the Designer's `ui/standin_painter.py`. Determinism is a hard rule — the
canvas repaints stand-ins on every rebuild and they must never shimmer —
so randomness is a sha256 stream keyed by (archetype, seed), never the
`random` module's global state.
"""
from __future__ import annotations
import hashlib
import math

ARCHETYPES: tuple[str, ...] = ("line", "scatter", "bar", "heatmap",
                               "micrograph")

# Keyword → archetype. Longest matching keyword wins, so "correlation
# matrix" (heatmap) beats "correlation" (scatter).
_HINT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "line": ("spectra", "spectrum", "curve", "time series", "timeseries",
             "trace", "kinetics", "line plot", "line chart"),
    "scatter": ("scatter", "correlation", "clustering"),
    "bar": ("bar", "histogram", "counts", "comparison"),
    "heatmap": ("heatmap", "heat map", "correlation matrix", "matrix",
                "colormap", "intensity map"),
    "micrograph": ("stem", "tem", "sem", "afm", "micrograph", "microscopy",
                   "image", "render", "rendering", "photo", "photograph"),
}


def infer(content_hint: str) -> str | None:
    """Best-guess archetype from a free-text hint; None when nothing
    matches. Longest keyword match wins; ties break by ARCHETYPES order."""
    text = (content_hint or "").lower()
    if not text.strip():
        return None
    best: tuple[int, int, str] | None = None  # (len, -order, archetype)
    for order, archetype in enumerate(ARCHETYPES):
        for kw in _HINT_KEYWORDS[archetype]:
            if kw in text:
                cand = (len(kw), -order, archetype)
                if best is None or cand > best:
                    best = cand
    return best[2] if best else None


def _stream(seed: str):
    """Deterministic uniform-[0,1) stream from a string seed."""
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for i in range(0, 32, 4):
            yield int.from_bytes(digest[i:i + 4], "big") / 2 ** 32
        counter += 1


def pseudo_data(archetype: str, seed: str, n_hint: int = 0) -> dict:
    """Plausible-looking, unit-square-normalized mock data. Same
    (archetype, seed, n_hint) → identical output, bit for bit."""
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype {archetype!r}")
    rng = _stream(f"{archetype}:{seed}")

    def nxt() -> float:
        return next(rng)

    if archetype == "line":
        n = n_hint or 24
        series = []
        for _ in range(2 + (nxt() > 0.5)):
            base = 0.25 + 0.5 * nxt()
            amp = 0.08 + 0.22 * nxt()
            phase = nxt() * 2 * math.pi
            freq = 1.0 + 2.0 * nxt()
            pts = [min(max(base + amp * math.sin(phase + freq * i / n * 2
                                                 * math.pi)
                           + 0.04 * (nxt() - 0.5), 0.0), 1.0)
                   for i in range(n)]
            series.append(pts)
        return {"series": series}
    if archetype == "scatter":
        n = n_hint or 40
        slope = 0.3 + 0.5 * nxt()
        points = []
        for _ in range(n):
            x = nxt()
            y = min(max(0.15 + slope * x + 0.18 * (nxt() - 0.5), 0.0), 1.0)
            points.append((x, y))
        return {"points": points, "fit": (slope, 0.15)}
    if archetype == "bar":
        groups = [[0.2 + 0.7 * nxt() for _ in range(4)] for _ in range(2)]
        errors = [[0.03 + 0.06 * nxt() for _ in range(4)] for _ in range(2)]
        return {"groups": groups, "errors": errors}
    if archetype == "heatmap":
        rows, cols = 6, 8
        cx, cy = nxt(), nxt()
        grid = [[min(max(1.0 - math.hypot(c / cols - cx, r / rows - cy)
                         + 0.15 * (nxt() - 0.5), 0.0), 1.0)
                 for c in range(cols)] for r in range(rows)]
        return {"grid": grid}
    # micrograph: a speckle tile, upscaled smoothly by the painter
    side = 32
    tile = [[nxt() for _ in range(side)] for _ in range(side)]
    return {"tile": tile}


def roles(constraints) -> dict:
    """Typography role table (decision log #1): furniture at the constraint
    FLOOR (the lint red line — the worst legal case is the information),
    data strokes at a typical published weight (3 × floor, capped 1 pt —
    nobody draws data at 0.25 pt; the floor would misrepresent)."""
    return {
        "furniture_font_pt": constraints.min_font_pt,
        "furniture_line_pt": constraints.min_linewidth_pt,
        "data_stroke_pt": min(3.0 * constraints.min_linewidth_pt, 1.0),
        "label_font_pt": constraints.max_font_pt,
    }
