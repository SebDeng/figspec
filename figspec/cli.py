"""figspec command line interface."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from figspec import __version__
from figspec.units import parse_length

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="figspec")
    parser.add_argument("--version", action="version", version=f"figspec {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    lint = sub.add_parser("lint", help="Check a finished figure PDF for effective "
                                       "font sizes and line widths")
    lint.add_argument("pdf", nargs="?", help="Finished figure PDF")
    lint.add_argument("--width", help="Expected figure width, e.g. 183mm (default unit: mm)")
    lint.add_argument("--min-font", type=float, default=5.0, metavar="PT",
                      help="Minimum effective font size in pt (default: 5)")
    lint.add_argument("--min-linewidth", type=float, default=0.25, metavar="PT",
                      help="Minimum effective stroke width in pt (default: 0.25)")
    lint.add_argument("--json", nargs="?", const="-", default=None, metavar="PATH",
                      help="Write JSON report to PATH, or stdout if no PATH given")
    lint.add_argument("--annotate", nargs="?", const="AUTO", default=None, metavar="PATH",
                      help="Write annotated PNG (default: <input>.lint.png)")
    lint.add_argument("--strict", action="store_true",
                      help="Treat WARN findings as not ready")
    lint.add_argument("--self-test", action="store_true",
                      help="Run built-in self test and exit")
    return parser

def _run_lint(args) -> int:
    from figspec.pdf.interpreter import LintInputError, extract
    from figspec.lint.checks import LintConfig, run_checks
    from figspec.lint.report import exit_code, render_json, render_text, summarize

    if args.self_test:
        from figspec.selftest import run_selftest
        return run_selftest()
    if not args.pdf:
        print("error: missing PDF argument (or use --self-test)", file=sys.stderr)
        return 2
    cfg = LintConfig(min_font_pt=args.min_font, min_linewidth_pt=args.min_linewidth)
    if args.width:
        try:
            cfg.width_pt = parse_length(args.width, default_unit="mm")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    try:
        doc = extract(args.pdf)
    except LintInputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = run_checks(doc, cfg)
    summary = summarize(findings, strict=args.strict)

    human = render_text(args.pdf, findings, summary)
    if args.json == "-":
        print(json.dumps(render_json(args.pdf, findings, summary), indent=2))
        print(human, file=sys.stderr)
    else:
        if args.json:
            Path(args.json).write_text(
                json.dumps(render_json(args.pdf, findings, summary), indent=2))
        print(human)
    if args.annotate:
        from figspec.lint.annotate import annotate
        out = (Path(args.pdf).with_suffix(".lint.png")
               if args.annotate == "AUTO" else Path(args.annotate))
        origins = {p.index: (p.origin_x_pt, p.origin_y_pt) for p in doc.pages}
        written = annotate(args.pdf, findings, out, origins=origins)
        for p in written:
            print(f"annotated: {p}", file=sys.stderr)
    return exit_code(summary)

def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "lint":
        return _run_lint(args)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
