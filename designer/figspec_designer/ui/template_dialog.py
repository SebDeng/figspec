"""File > New from Template… — list left, wireframe preview right."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QVBoxLayout)

from figspec.templates import TEMPLATES
from figspec_designer.ui.preview_export import render_layout_image


class TemplateDialog(QDialog):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New from Template")
        self._target = target

        self.list_widget = QListWidget()
        for key, t in TEMPLATES.items():
            item = QListWidgetItem(t.title)
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(260, 200)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.preview_label)
        right.addWidget(self.desc_label)
        right.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        top = QHBoxLayout()
        top.addWidget(self.list_widget, stretch=1)
        top.addLayout(right)
        outer = QVBoxLayout(self)
        outer.addLayout(top)
        outer.addWidget(buttons)

        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())

    def selected_key(self) -> str | None:
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _update_preview(self, *_args) -> None:
        key = self.selected_key()
        if key is None:
            return
        t = TEMPLATES[key]
        img = render_layout_image(t.build(), self._target, scale=1)
        pix = QPixmap.fromImage(img).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio,
            Qt.SmoothTransformation)
        self.preview_label.setPixmap(pix)
        self.desc_label.setText(t.description)
