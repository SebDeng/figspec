"""Batch H UI tests: Illustrator board / panel artboard entry points."""
import pytest

from figspec.layout.tree import iter_panels
from figspec.pdf.interpreter import extract
from figspec.units import mm_to_pt
from figspec_designer.ui.main_window import MainWindow


def _patch_save(monkeypatch, path):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))


def test_export_ai_board(qtbot, tmp_path, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    out = tmp_path / "board.pdf"
    _patch_save(monkeypatch, out)
    win.export_ai_board()
    assert out.exists()
    doc = extract(out)
    assert doc.pages[0].width_pt == pytest.approx(mm_to_pt(183.0), abs=0.1)
    assert any(r.text == "a" for r in doc.text_runs)


def test_export_ai_board_embeds_assets(qtbot, tmp_path, monkeypatch):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    samples = write_samples(tmp_path / "s")
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(samples["bad"]))
    out = tmp_path / "board.pdf"
    _patch_save(monkeypatch, out)
    win.export_ai_board()
    doc = extract(out)
    assert any(r.text == "Scaled tiny text" for r in doc.text_runs)


def test_export_panel_artboard_via_action(qtbot, tmp_path, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    rect = next(r for r in win.doc.panel_rects() if r.panel_id == pid)
    out = tmp_path / "artboard.pdf"
    _patch_save(monkeypatch, out)
    win.do_action("export_artboard", pid)
    assert out.exists()
    doc = extract(out)
    assert doc.pages[0].width_pt == pytest.approx(mm_to_pt(rect.w_mm),
                                                  abs=0.1)
    assert doc.pages[0].height_pt == pytest.approx(mm_to_pt(rect.h_mm),
                                                   abs=0.1)
    assert any(t.text.startswith("panel a") for t in doc.text_runs)
    assert "Illustrator" in win.statusBar().currentMessage()


def test_export_cancelled_dialog_is_noop(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    win.export_ai_board()  # must not raise or write anything
    assert not list(tmp_path.iterdir())
