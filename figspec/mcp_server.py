"""figspec MCP server (M0): stateless file-based tools over shipped capabilities.

The _impl layer is importable and testable without fastmcp; fastmcp is an
optional extra (pip install "figspec[mcp]").
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Literal

from figspec import presets
from figspec.document import DesignerDocument, MissingDesignerData
from figspec.layout import ops
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.report import render_json, summarize
from figspec.pdf.interpreter import LintInputError, extract
from figspec.spec import Constraints, SpecError, Target, parse_spec
from figspec.units import mm_to_pt

_KNOWN_TOP_LEVEL = {"figspec_version", "target", "constraints", "panels", "designer"}


def _error(msg: str, **extra) -> dict:
    return {"error": msg, **extra}


def _write_text(path: str, text: str) -> dict | None:
    """Write text; returns an error dict on failure, None on success."""
    try:
        Path(path).write_text(text)
    except OSError as e:
        return _error(f"cannot write {path}: {e}")
    return None


def _coerce_float(name: str, value):
    """Returns (float_value, None) or (None, error_dict)."""
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, _error(f"{name} must be a number, got {value!r}")


def lint_pdf_impl(pdf_path: str, width_mm: float | None = None,
                  min_font_pt: float = 5.0, min_linewidth_pt: float = 0.25,
                  strict: bool = False) -> dict:
    if width_mm is not None:
        width_mm, err = _coerce_float("width_mm", width_mm)
        if err:
            return err
    min_font_pt, err = _coerce_float("min_font_pt", min_font_pt)
    if err:
        return err
    min_linewidth_pt, err = _coerce_float("min_linewidth_pt", min_linewidth_pt)
    if err:
        return err
    cfg = LintConfig(min_font_pt=min_font_pt, min_linewidth_pt=min_linewidth_pt)
    if width_mm is not None:
        cfg.width_pt = mm_to_pt(width_mm)
    try:
        doc = extract(pdf_path)
    except LintInputError as e:
        return _error(f"cannot open: {e}")
    findings = run_checks(doc, cfg)
    return render_json(pdf_path, findings, summarize(findings, strict=strict))


def read_spec_impl(spec_path: str) -> dict:
    try:
        data = json.loads(Path(spec_path).read_text())
        _target, _constraints, panels, designer = parse_spec(data)
    except (OSError, json.JSONDecodeError, SpecError) as e:
        return _error(f"cannot read spec: {e}")
    return {
        "spec": data,
        "panel_count": len(panels),
        "labels": [p.label for p in panels],
        "has_designer_tree": bool(designer and "tree" in designer),
    }


def write_spec_impl(spec_path: str, spec: dict) -> dict:
    try:
        parse_spec(spec)
    except SpecError as e:
        return _error(f"invalid spec, not written: {e}")
    err = _write_text(spec_path, json.dumps(spec, indent=2) + "\n")
    if err:
        return err
    return {"written": spec_path}


def new_spec_impl(spec_path: str, preset: str = "nature_double",
                  height_mm: float = 100.0, overwrite: bool = False) -> dict:
    if preset not in presets.PRESETS:
        return _error(
            f"unknown preset {preset!r}; valid: {', '.join(sorted(presets.PRESETS))}")
    height_mm, err = _coerce_float("height_mm", height_mm)
    if err:
        return err
    if not overwrite and Path(spec_path).exists():
        return _error(f"{spec_path} already exists; pass overwrite=true to replace it")
    doc = DesignerDocument(
        tree=DesignerDocument.default().tree,
        target=Target(preset, presets.PRESETS[preset], height_mm,
                      presets.DEFAULT_DPI, presets.DEFAULT_GUTTER_MM),
        constraints=Constraints(**presets.PRESET_CONSTRAINTS[preset]),
    )
    err = _write_text(spec_path, doc.to_json())
    if err:
        return err
    return doc.to_spec_dict()


def _load_doc(spec_path: str):
    """Returns (raw_dict, DesignerDocument) or an error dict."""
    try:
        raw = json.loads(Path(spec_path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        return _error(f"cannot read spec: {e}")
    try:
        doc = DesignerDocument.from_spec_dict(raw)
    except MissingDesignerData as e:
        return _error(f"missing designer sidecar: {e}")
    except Exception as e:  # tree.from_dict raises bare ValueError etc.
        return _error(f"cannot parse spec: {e}")
    return raw, doc


def _panel_id_for_label(doc: DesignerDocument, label: str):
    for pid, lab in doc.labels().items():
        if lab == label:
            return pid
    return None


def _write_back(spec_path: str, raw: dict, doc: DesignerDocument) -> dict:
    out = doc.to_spec_dict()
    for key, value in raw.items():
        if key not in _KNOWN_TOP_LEVEL:
            out[key] = value
    err = _write_text(spec_path, json.dumps(out, indent=2) + "\n")
    if err:
        return err
    return {"panels": out["panels"]}


def _panel_op(spec_path: str, label: str, fn) -> dict:
    loaded = _load_doc(spec_path)
    if isinstance(loaded, dict):
        return loaded
    raw, doc = loaded
    pid = _panel_id_for_label(doc, label)
    if pid is None:
        existing = ", ".join(sorted(doc.labels().values()))
        return _error(f"no panel labeled {label!r}; existing: {existing}")
    try:
        doc.tree = fn(doc.tree, pid)
    except (ValueError, KeyError) as e:
        return _error(str(e))
    return _write_back(spec_path, raw, doc)


def split_panel_impl(spec_path: str, label: str,
                     direction: Literal["right", "down"]) -> dict:
    if direction not in ("right", "down"):
        return _error("direction must be 'right' or 'down'")
    return _panel_op(spec_path, label,
                     lambda tree, pid: ops.split_panel(tree, pid, direction))


def close_panel_impl(spec_path: str, label: str) -> dict:
    return _panel_op(spec_path, label, ops.close_panel)


def set_panel_hint_impl(spec_path: str, label: str, hint: str) -> dict:
    return _panel_op(spec_path, label,
                     lambda tree, pid: ops.set_content_hint(tree, pid, hint))


def list_presets_impl() -> dict:
    return {
        "presets": dict(presets.PRESETS),
        "constraints": {k: dict(v) for k, v in presets.PRESET_CONSTRAINTS.items()},
        "reference": "docs/journal-figure-specs.md (sourced values, verified 2026-07-30)",
    }


def build_server():
    try:
        from fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            'fastmcp is not installed; run: pip install "figspec[mcp]"') from e

    mcp = FastMCP("figspec")
    mcp.tool(lint_pdf_impl, name="lint_pdf",
             description="Lint a finished figure PDF for effective (post-scaling) "
                         "font sizes, line widths and raster DPI. Pass width_mm "
                         "(the journal's column width from list_presets) to also "
                         "verify the final page width. Returns figspec finding "
                         "JSON (check_id/level/message/evidence).")
    mcp.tool(read_spec_impl, name="read_spec",
             description="Read and validate a figspec.json; returns spec + summary.")
    mcp.tool(write_spec_impl, name="write_spec",
             description="Validate then write a full figspec.json document.")
    mcp.tool(new_spec_impl, name="new_spec",
             description="Create a new single-panel figspec.json from a journal "
                         "preset (see list_presets). Fails if spec_path already "
                         "exists unless overwrite=true.")
    mcp.tool(split_panel_impl, name="split_panel",
             description="Split a panel (by label) right or down; relabels panels "
                         "in reading order and rewrites the file.")
    mcp.tool(close_panel_impl, name="close_panel",
             description="Delete a panel by label; siblings absorb its space.")
    mcp.tool(set_panel_hint_impl, name="set_panel_hint",
             description="Set a panel's content_hint text.")
    mcp.tool(list_presets_impl, name="list_presets",
             description="Journal width presets and per-journal constraint "
                         "defaults with source reference.")
    return mcp


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="figspec-mcp",
        description="figspec MCP server (stdio): lint figure PDFs, create and "
                    "edit figspec.json layouts. Requires: pip install \"figspec[mcp]\"")
    from figspec import __version__
    parser.add_argument("--version", action="version",
                        version=f"figspec-mcp {__version__}")
    parser.parse_args(argv)
    try:
        server = build_server()
    except ImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
