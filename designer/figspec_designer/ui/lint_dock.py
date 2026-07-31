"""Right-side dock showing figspec lint results: summary, findings, images."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPixmap
from PySide6.QtWidgets import (QDockWidget, QLabel, QPushButton, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from figspec_designer.ui.theme import DPI_BAD, DPI_OK, DPI_WARN

_LEVEL_GLYPH = {"FAIL": "●", "WARN": "●", "PASS": "○"}
_LEVEL_COLOR = {"FAIL": DPI_BAD, "WARN": DPI_WARN, "PASS": DPI_OK}


class LintDock(QDockWidget):
    relint_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Lint", parent)
        self.setObjectName("lintDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("lintSummary")
        self.summary_label.setWordWrap(True)
        lay.addWidget(self.summary_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("lintError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        lay.addWidget(self.error_label)

        self.btn_relint = QPushButton("Re-lint Same File")
        self.btn_relint.clicked.connect(self.relint_requested.emit)
        self.btn_relint.setEnabled(False)
        lay.addWidget(self.btn_relint)

        self.findings_tree = QTreeWidget()
        self.findings_tree.setHeaderHidden(True)
        self.findings_tree.setRootIsDecorated(True)
        lay.addWidget(self.findings_tree, stretch=1)

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_label = QLabel("No annotated pages")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        lay.addWidget(self.image_scroll, stretch=1)

        self.setWidget(body)

    def show_running(self, pdf_path: str) -> None:
        self.error_label.setVisible(False)
        self.btn_relint.setEnabled(False)
        self.summary_label.setText(f"Linting {pdf_path}…")
        self.findings_tree.clear()
        self.image_label.setText("Running…")
        self.image_label.setPixmap(QPixmap())

    def show_report(self, report: dict, annotated: list[str]) -> None:
        self.error_label.setVisible(False)
        self.btn_relint.setEnabled(True)
        s = report["summary"]
        verdict = ("READY FOR SUBMISSION" if s["ready"]
                   else "FIX BEFORE SUBMISSION")  # mirrors report.render_text
        self.summary_label.setText(
            f"{verdict} — " + ", ".join(
                f"{k}: {v}" for k, v in s["counts"].items()))
        self.findings_tree.clear()
        for f in report["findings"]:
            head = QTreeWidgetItem(
                [f"{_LEVEL_GLYPH.get(f['level'], '·')} {f['level']} "
                 f"{f['check_id']}: {f['message']}"])
            head.setData(0, Qt.UserRole, f["level"])
            color = _LEVEL_COLOR.get(f["level"])
            if color:
                head.setForeground(0, QBrush(QColor(color)))
            for ev in f.get("evidence", []):
                head.addChild(QTreeWidgetItem([ev]))
            self.findings_tree.addTopLevelItem(head)
        if annotated:
            self.image_label.setPixmap(QPixmap(annotated[0]))
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No annotatable violations")

    def show_error(self, message: str) -> None:
        self.btn_relint.setEnabled(True)
        self.summary_label.setText("Lint failed")
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.findings_tree.clear()
