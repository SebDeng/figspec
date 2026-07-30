"""Built-in self test: synthesizes known-ground-truth PDFs and lints them."""
from __future__ import annotations
import tempfile
from pathlib import Path

def run_selftest() -> int:
    from figspec.lint.checks import LintConfig, run_checks
    from figspec.lint.report import summarize
    from figspec.pdf.interpreter import extract
    from figspec.selftest.samples import (
        BAD_EFFECTIVE_FONT, BAD_EFFECTIVE_LINE, FORM_EFFECTIVE_FONT, write_samples)

    results: list[tuple[str, bool]] = []

    def expect(label: str, cond: bool):
        results.append((label, cond))

    with tempfile.TemporaryDirectory() as td:
        paths = write_samples(Path(td))
        cfg = LintConfig()

        good = run_checks(extract(paths["good"]), cfg)
        expect("good sample is ready", summarize(good, strict=False)["ready"])

        bad = run_checks(extract(paths["bad"]), cfg)
        font = [f for f in bad if f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL"]
        line = [f for f in bad if f.check_id == "LINEWIDTH-EFFECTIVE" and f.level == "FAIL"]
        expect("bad sample: tiny text detected",
               bool(font) and abs(font[0].effective_pt - BAD_EFFECTIVE_FONT) < 0.05)
        expect("bad sample: thin line detected",
               bool(line) and abs(line[0].effective_pt - BAD_EFFECTIVE_LINE) < 0.05)

        form = run_checks(extract(paths["form"]), cfg)
        ffont = [f for f in form if f.check_id == "FONT-EFFECTIVE" and f.level == "FAIL"]
        expect("form xobject: nested scaling detected",
               bool(ffont) and abs(ffont[0].effective_pt - FORM_EFFECTIVE_FONT) < 0.05)

    ok = all(c for _, c in results)
    for label, cond in results:
        print(f"[{'ok' if cond else 'FAIL'}] {label}")
    print("self-test " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1
