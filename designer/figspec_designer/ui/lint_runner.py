"""Background PDF lint: QThread wrapper around figspec.lint -- no new logic."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from figspec.lint.annotate import annotate
from figspec.lint.checks import LintConfig, run_checks
from figspec.lint.report import render_json, summarize
from figspec.pdf.interpreter import LintInputError, extract


class LintWorker(QThread):
    finished_ok = Signal(dict, list)  # (render_json dict, [annotated PNG paths])
    failed = Signal(str)

    def __init__(self, pdf_path: str, cfg: LintConfig, out_dir, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._cfg = cfg
        self._out_dir = Path(out_dir)

    def run(self) -> None:
        try:
            doc = extract(self._pdf_path)
            findings = run_checks(doc, self._cfg)
            summary = summarize(findings, strict=False)
            report = render_json(self._pdf_path, findings, summary)
            self._out_dir.mkdir(parents=True, exist_ok=True)
            origins = {p.index: (p.origin_x_pt, p.origin_y_pt)
                       for p in doc.pages}
            written = annotate(self._pdf_path, findings,
                               self._out_dir / "lint.png", origins=origins)
        except LintInputError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:  # never crash the app over a bad PDF
            self.failed.emit(f"lint failed: {e}")
            return
        self.finished_ok.emit(report, [str(p) for p in written])
