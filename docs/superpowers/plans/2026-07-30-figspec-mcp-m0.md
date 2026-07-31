# figspec-mcp M0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `figspec-mcp` — a FastMCP stdio server exposing the shipped lint/spec/layout capabilities as agent tools — after hoisting the pure layout/document layers into the `figspec` package.

**Architecture:** Task 1 moves the Qt-free modules (`model/*`, `document.py`, `presets.py`) from the designer package into `figspec/` with one-line re-export shims left behind (zero designer churn). Task 2 adds `figspec/mcp_server.py`: a pure `_impl` function layer (testable without fastmcp) + `build_server()` FastMCP registration + `figspec-mcp` console script behind an optional `[mcp]` extra. All tools are stateless file operations returning result dicts or `{"error": ...}` — never exceptions.

**Tech Stack:** fastmcp>=2 (optional extra), existing figspec internals. No daemon, no rendering.

## Global Constraints

- Moved-module layout: `figspec/layout/{tree,ops,flatten,history}.py`, `figspec/document.py`, `figspec/presets.py`; shims at the old `figspec_designer` paths re-export the exact public names; designer source and its 74 tests are otherwise UNTOUCHED.
- figspec package stays Qt-free; `_impl` layer importable without fastmcp; fastmcp imported only inside `build_server()`/`main()` with a clear `pip install "figspec[mcp]"` error.
- Error contract: every tool returns a dict; failures are `{"error": "<actionable message>", ...}` — no exceptions cross the tool boundary.
- Unknown-top-level-key preservation (v0.3 兼容铁律): layout ops rewrite specs via `_merge_unknown` so keys outside {figspec_version, target, constraints, panels, designer} survive round-trips. Covered by test.
- Tests: figspec suite `.venv/bin/pytest tests/ -q` (78 + new), designer suite `.venv/bin/pytest designer/tests -q` (74, unmodified). Repo lives at /Users/dengyusong/dev/FigSpec (no iCloud workarounds needed; editable installs live).
- TDD: RED first for every new behavior.

---

### Task 1: Hoist pure layers into figspec (move + shims)

**Files:**
- Create: `figspec/layout/__init__.py` (empty)
- Move (git mv): `designer/figspec_designer/model/tree.py → figspec/layout/tree.py`, `.../model/ops.py → figspec/layout/ops.py`, `.../model/flatten.py → figspec/layout/flatten.py`, `.../model/history.py → figspec/layout/history.py`, `.../document.py → figspec/document.py`, `.../presets.py → figspec/presets.py`
- Create (shims, replacing moved files): `designer/figspec_designer/model/tree.py`, `ops.py`, `flatten.py`, `history.py`, `designer/figspec_designer/document.py`, `designer/figspec_designer/presets.py`
- Test: `tests/test_layout_hoist.py`

**Interfaces:**
- Produces: `figspec.layout.tree/ops/flatten/history`, `figspec.document`, `figspec.presets` with identical public APIs; old import paths keep working via shims.

- [ ] **Step 1: Write the failing test** (`tests/test_layout_hoist.py`)

```python
def test_new_locations_importable():
    from figspec.layout.tree import PanelNode, SplitNode, new_panel  # noqa: F401
    from figspec.layout.ops import split_panel, snap_ratios  # noqa: F401
    from figspec.layout.flatten import PanelRect, flatten, assign_labels, derive  # noqa: F401
    from figspec.layout.history import History  # noqa: F401
    from figspec.document import DesignerDocument, MissingDesignerData  # noqa: F401
    from figspec.presets import PRESETS, PRESET_CONSTRAINTS  # noqa: F401


def test_shims_are_same_objects():
    import figspec.layout.tree as new_tree
    import figspec_designer.model.tree as old_tree
    assert old_tree.PanelNode is new_tree.PanelNode
    import figspec.document as new_doc
    import figspec_designer.document as old_doc
    assert old_doc.DesignerDocument is new_doc.DesignerDocument
    import figspec.presets as new_p
    import figspec_designer.presets as old_p
    assert old_p.PRESETS is new_p.PRESETS


def test_figspec_stays_qt_free():
    import sys
    for mod in list(sys.modules):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import importlib
    import figspec.document, figspec.presets, figspec.layout.ops  # noqa: F401
    importlib.reload(figspec.document)
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

Note: this test file needs `figspec_designer` importable from the figspec suite — add a one-line `tests/conftest.py` addition (or new file if absent):
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "designer"))
```
(Check whether `tests/conftest.py` exists first; append if so.)

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_layout_hoist.py -q` → ImportError.

- [ ] **Step 3: Implement**

1. `git mv` the six files as listed; create empty `figspec/layout/__init__.py`.
2. Fix internal imports in the MOVED files: `figspec_designer.model.tree → figspec.layout.tree` (in ops.py, flatten.py), `figspec_designer.model.* / figspec_designer.presets → figspec.layout.* / figspec.presets` (in document.py). document.py's `figspec.spec` imports unchanged.
3. Write shims (exact content):

`designer/figspec_designer/model/tree.py`:
```python
"""Compatibility shim — moved to figspec.layout.tree."""
from figspec.layout.tree import (Node, PanelNode, SplitNode, from_dict,  # noqa: F401
                                 iter_panels, new_panel, to_dict)
```
`designer/figspec_designer/model/ops.py`:
```python
"""Compatibility shim — moved to figspec.layout.ops."""
from figspec.layout.ops import (close_panel, node_at, set_content_hint,  # noqa: F401
                                set_ratios, snap_ratios, split_panel)
```
`designer/figspec_designer/model/flatten.py`:
```python
"""Compatibility shim — moved to figspec.layout.flatten."""
from figspec.layout.flatten import PanelRect, assign_labels, derive, flatten  # noqa: F401
```
`designer/figspec_designer/model/history.py`:
```python
"""Compatibility shim — moved to figspec.layout.history."""
from figspec.layout.history import History  # noqa: F401
```
`designer/figspec_designer/document.py`:
```python
"""Compatibility shim — moved to figspec.document."""
from figspec.document import DesignerDocument, MissingDesignerData  # noqa: F401
```
`designer/figspec_designer/presets.py`:
```python
"""Compatibility shim — moved to figspec.presets."""
from figspec.presets import (DEFAULT_DPI, DEFAULT_GUTTER_MM,  # noqa: F401
                             DEFAULT_HEIGHT_MM, PRESET_CONSTRAINTS, PRESETS)
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/pytest tests/ -q` (expect 78 + 3 = 81) AND `.venv/bin/pytest designer/tests -q` (expect 74, unmodified). If a designer test fails, the shim is missing a name it uses — extend the shim, never edit the test.

- [ ] **Step 5: Commit** — `git add -A figspec designer tests && git commit -m "refactor: hoist layout/document/presets into figspec package"`

---

### Task 2: MCP server module

**Files:**
- Create: `figspec/mcp_server.py`
- Modify: `pyproject.toml` (extra + script)
- Test: `tests/test_mcp.py`

**Interfaces:**
- Produces: `_impl` functions `lint_pdf_impl(pdf_path, width_mm=None, min_font_pt=5.0, min_linewidth_pt=0.25, strict=False) -> dict`, `read_spec_impl(spec_path) -> dict`, `write_spec_impl(spec_path, spec) -> dict`, `new_spec_impl(spec_path, preset="nature_double", height_mm=100.0) -> dict`, `split_panel_impl(spec_path, label, direction) -> dict`, `close_panel_impl(spec_path, label) -> dict`, `set_panel_hint_impl(spec_path, label, hint) -> dict`, `list_presets_impl() -> dict`; `build_server()` (FastMCP instance), `main() -> int`.

- [ ] **Step 1: Write the failing test** (`tests/test_mcp.py`)

```python
import json
import pytest
from figspec.mcp_server import (close_panel_impl, lint_pdf_impl, list_presets_impl,
                                new_spec_impl, read_spec_impl, set_panel_hint_impl,
                                split_panel_impl, write_spec_impl)
from figspec.selftest.samples import write_samples


@pytest.fixture()
def samples(tmp_path):
    return write_samples(tmp_path)


def test_lint_bad_sample(samples):
    out = lint_pdf_impl(str(samples["bad"]), width_mm=183)
    assert out["summary"]["ready"] is False
    ids = {f["check_id"] for f in out["findings"]}
    assert "FONT-EFFECTIVE" in ids


def test_lint_missing_file():
    out = lint_pdf_impl("/nonexistent/x.pdf")
    assert "error" in out and "cannot open" in out["error"]


def test_new_read_roundtrip(tmp_path):
    p = tmp_path / "fig.figspec.json"
    created = new_spec_impl(str(p), preset="aps_single", height_mm=90.0)
    assert created["target"]["figure_width_mm"] == 85.0
    assert created["constraints"]["min_font_pt"] == 8.0
    seen = read_spec_impl(str(p))
    assert seen["panel_count"] == 1 and seen["has_designer_tree"] is True


def test_new_spec_unknown_preset(tmp_path):
    out = new_spec_impl(str(tmp_path / "x.json"), preset="cell_double")
    assert "error" in out and "nature_double" in out["error"]  # lists valid presets


def test_split_close_hint_flow(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    out = split_panel_impl(str(p), "a", "right")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b"]
    out = split_panel_impl(str(p), "b", "down")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b", "c"]
    out = set_panel_hint_impl(str(p), "b", "STEM image")
    assert out["panels"][1]["content_hint"] == "STEM image"
    out = close_panel_impl(str(p), "c")
    assert [pa["label"] for pa in out["panels"]] == ["a", "b"]
    out = close_panel_impl(str(p), "zz")
    assert "error" in out and "a, b" in out["error"]  # lists existing labels


def test_close_last_panel_error(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    out = close_panel_impl(str(p), "a")
    assert "error" in out


def test_ops_preserve_unknown_top_level(tmp_path):
    p = tmp_path / "fig.figspec.json"
    new_spec_impl(str(p))
    data = json.loads(p.read_text())
    data["x_custom_section"] = {"keep": "me"}
    p.write_text(json.dumps(data))
    split_panel_impl(str(p), "a", "right")
    after = json.loads(p.read_text())
    assert after["x_custom_section"] == {"keep": "me"}


def test_ops_without_sidecar(tmp_path):
    p = tmp_path / "plain.json"
    data = new_spec_impl(str(tmp_path / "t.json"))
    del data["designer"]
    p.write_text(json.dumps(data))
    out = split_panel_impl(str(p), "a", "right")
    assert "error" in out and "designer" in out["error"]


def test_write_spec_validates(tmp_path):
    p = tmp_path / "w.json"
    out = write_spec_impl(str(p), {"nope": 1})
    assert "error" in out and not p.exists()


def test_list_presets():
    out = list_presets_impl()
    assert out["presets"]["nature_double"] == 183.0
    assert out["constraints"]["acs_single"]["min_font_pt"] == 4.5


def test_build_server_smoke():
    fastmcp = pytest.importorskip("fastmcp")  # noqa: F841
    from figspec.mcp_server import build_server
    server = build_server()
    assert server.name == "figspec"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_mcp.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** (`figspec/mcp_server.py`)

```python
"""figspec MCP server (M0): stateless file-based tools over shipped capabilities.

The _impl layer is importable and testable without fastmcp; fastmcp is an
optional extra (pip install "figspec[mcp]").
"""
from __future__ import annotations
import json
from pathlib import Path

from figspec import presets
from figspec.document import DesignerDocument, MissingDesignerData
from figspec.layout import ops
from figspec.layout.tree import iter_panels
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.report import render_json, summarize
from figspec.pdf.interpreter import LintInputError, extract
from figspec.spec import Constraints, SpecError, Target, parse_spec
from figspec.units import mm_to_pt

_KNOWN_TOP_LEVEL = {"figspec_version", "target", "constraints", "panels", "designer"}


def _error(msg: str, **extra) -> dict:
    return {"error": msg, **extra}


def lint_pdf_impl(pdf_path: str, width_mm: float | None = None,
                  min_font_pt: float = 5.0, min_linewidth_pt: float = 0.25,
                  strict: bool = False) -> dict:
    cfg = LintConfig(min_font_pt=min_font_pt, min_linewidth_pt=min_linewidth_pt)
    if width_mm is not None:
        cfg.width_pt = mm_to_pt(float(width_mm))
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
    Path(spec_path).write_text(json.dumps(spec, indent=2) + "\n")
    return {"written": spec_path}


def new_spec_impl(spec_path: str, preset: str = "nature_double",
                  height_mm: float = 100.0) -> dict:
    if preset not in presets.PRESETS:
        return _error(
            f"unknown preset {preset!r}; valid: {', '.join(sorted(presets.PRESETS))}")
    doc = DesignerDocument(
        tree=DesignerDocument.default().tree,
        target=Target(preset, presets.PRESETS[preset], float(height_mm),
                      presets.DEFAULT_DPI, presets.DEFAULT_GUTTER_MM),
        constraints=Constraints(**presets.PRESET_CONSTRAINTS[preset]),
    )
    Path(spec_path).write_text(doc.to_json())
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
    except (SpecError, Exception) as e:  # tree.from_dict raises bare ValueError etc.
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
    Path(spec_path).write_text(json.dumps(out, indent=2) + "\n")
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
    except ValueError as e:
        return _error(str(e))
    return _write_back(spec_path, raw, doc)


def split_panel_impl(spec_path: str, label: str, direction: str) -> dict:
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
                         "font sizes, line widths and raster DPI. Returns the "
                         "figspec finding JSON (check_id/level/message/evidence).")
    mcp.tool(read_spec_impl, name="read_spec",
             description="Read and validate a figspec.json; returns spec + summary.")
    mcp.tool(write_spec_impl, name="write_spec",
             description="Validate then write a full figspec.json document.")
    mcp.tool(new_spec_impl, name="new_spec",
             description="Create a new single-panel figspec.json from a journal "
                         "preset (see list_presets).")
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


def main() -> int:
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`pyproject.toml` additions:
```toml
[project.optional-dependencies]
mcp = ["fastmcp>=2"]
# (keep existing dev extra unchanged)

[project.scripts]
figspec-mcp = "figspec.mcp_server:main"
# (keep existing figspec script)
```

- [ ] **Step 4: Install and verify pass**

Run: `.venv/bin/pip install -q -e ".[dev,mcp]" && .venv/bin/pytest tests/ -q && .venv/bin/pytest designer/tests -q`
Expected: figspec suite 81 + 12 = 93 passed; designer 74 passed. Note: if the installed fastmcp's registration API differs from `mcp.tool(fn, name=..., description=...)` (e.g. decorator-only), adapt `build_server` minimally and document — the _impl layer and tests must not change.

Also: `.venv/bin/figspec-mcp --help >/dev/null 2>&1; echo "exit=$?"` — any clean exit (0/1/2) acceptable; it must not traceback on import.

- [ ] **Step 5: Commit** — `git add figspec/mcp_server.py pyproject.toml tests/test_mcp.py && git commit -m "feat: figspec-mcp M0 server (lint, spec, layout tools)"`

---

### Task 3: README + final verification

**Files:**
- Modify: `README.md`, `README.zh-CN.md`

- [ ] **Step 1: Add MCP section to both READMEs** (after the Designer section; zh faithful translation, code blocks byte-identical):

````markdown
## MCP server (agent-native access)

`figspec-mcp` exposes the toolchain to AI agents over MCP (stdio): lint a
PDF, create/read/write figspec.json, and edit layouts (split/close panels,
set hints) — all stateless file operations.

```bash
pip install "figspec[mcp]"
claude mcp add figspec -- figspec-mcp
```

Tools: `lint_pdf`, `new_spec`, `read_spec`, `write_spec`, `split_panel`,
`close_panel`, `set_panel_hint`, `list_presets`.
````

- [ ] **Step 2: Full verification** — `.venv/bin/pytest tests/ -q && .venv/bin/pytest designer/tests -q && .venv/bin/figspec lint --self-test && PYTHONPATH=designer QT_QPA_PLATFORM=offscreen .venv/bin/python -m figspec_designer --smoke` — all green/exit 0.

- [ ] **Step 3: Commit** — `git add README.md README.zh-CN.md && git commit -m "docs: MCP server section in READMEs"`

---

## Self-Review Notes

- Spec §1 → Task 1 (moves + shims + Qt-free test); §2 → Task 2 (all 8 tools, error contract, unknown-key preservation via _write_back, optional-dep guard, script); §3 → per-task test steps + Task 3 verification; §4 boundaries — nothing beyond the 8 tools is implemented.
- Type consistency: _impl names in tests match implementations; `ops.close_panel(tree, pid)` signature matches `_panel_op`'s `fn(tree, pid)` (split/hint adapt via lambda); labels from `doc.labels()` values.
- Known risk: fastmcp 2.x API drift (Step 4 note authorizes minimal build_server adaptation); `new_spec_impl` writing then returning to_spec_dict (same content, one serialization).
