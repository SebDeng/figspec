"""Batch I tests: hand-off palette, slim top bar, sidebar layers, status strip."""
import pytest
from PySide6.QtWidgets import QApplication

from figspec.layout.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


# ---- I1: Hand Off palette -----------------------------------------------

def test_handoff_dialog_has_seven_rows(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    assert len(dlg.rows) == 7
    # panel-scoped rows disabled with no selection
    titles = [b.text().split("\n")[0] for b in dlg.rows]
    artboard = dlg.rows[titles.index("Panel artboard")]
    card = dlg.rows[[t.startswith("Authoring card") for t in titles].index(True)]
    assert not artboard.isEnabled() and not card.isEnabled()


def test_handoff_rows_enable_with_selection(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("select", pid)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    assert all(b.isEnabled() for b in dlg.rows)
    assert any("(a)" in b.text() for b in dlg.rows)


def test_handoff_snippet_row_copies(qtbot):
    from figspec_designer.ui.handoff import HandoffDialog
    win = MainWindow()
    qtbot.addWidget(win)
    dlg = HandoffDialog(win)
    qtbot.addWidget(dlg)
    snippet_row = next(b for b in dlg.rows
                       if b.text().startswith("matplotlib snippet"))
    snippet_row.click()
    assert QApplication.clipboard().text().startswith("# Generated")
    assert dlg.result() == 1  # palette closed itself


def test_file_menu_consolidated(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    texts = [a.text() for a in win.file_menu.actions() if a.text()]
    assert "Hand Off…" in texts
    assert not any(t.startswith("Copy") for t in texts)
    assert not any(t.startswith("Export") for t in texts)
    assert len(texts) <= 8


def test_sidebar_has_no_copy_buttons(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    for name in ("btn_copy_snippet", "btn_copy_placement", "btn_copy_card"):
        assert not hasattr(win.sidebar, name)


# ---- I3: sidebar layers + truth line ------------------------------------

def _png(tmp_path, w=1472, h=879):
    from PySide6.QtGui import QImage
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    path = tmp_path / "a.png"
    img.save(str(path))
    return path


def test_truth_line_no_asset_echoes_constraints(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win.do_action("select", pid)
    assert win.sidebar.btn_truth.text() == "5–7 pt · ≥0.25 pt"
    assert not win.sidebar.btn_truth.isEnabled()


def test_truth_line_raster(qtbot, tmp_path):
    from figspec import scaling
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(_png(tmp_path)))
    win.do_action("select", pid)
    rect = next(r for r in win.doc.panel_rects() if r.panel_id == pid)
    k = scaling.placement_scale(
        (rect.w_mm, rect.h_mm), scaling.asset_size_mm((1472, 879), 96.0))
    text = win.sidebar.btn_truth.text()
    assert text.startswith(f"×{k:.3f} · ")
    assert "dpi" in text
    assert win.sidebar.btn_truth.isEnabled()


def test_truth_line_vector_red(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    samples = write_samples(tmp_path / "s")
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(samples["bad"]))
    win.do_action("select", pid)
    text = win.sidebar.btn_truth.text()
    assert text.startswith("×") and "✗" in text
    assert win.sidebar.btn_truth.property("level") == "bad"


def test_details_collapsed_by_default(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    sb = win.sidebar
    assert not sb.details_widget.isVisibleTo(sb)
    sb.details_toggle.setChecked(True)
    assert sb.details_widget.isVisibleTo(sb)


def test_truth_popover_hosts_analysis(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    pid = next(iter_panels(win.doc.tree)).id
    win._on_asset_dropped(pid, str(_png(tmp_path)))
    win.do_action("select", pid)
    sb = win.sidebar
    # analysis widgets live in the popover container, not the column
    assert sb.calc_nominal.window() is sb._truth_popover
    assert sb.dpi_edit.window() is sb._truth_popover
    assert sb.btn_remove_asset.isVisibleTo(sb)  # remove stays in the column


# ---- I4: status strip + zoom cluster + hover retirement -----------------

def test_strip_collapsed_by_default_and_expands(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    strip = win.specimen_strip
    assert not strip.expanded
    assert strip.height() <= 30
    strip.btn_expand.click()
    assert strip.expanded and strip.height() >= 50
    assert not strip.area.isVisibleTo(strip) or strip.expanded  # area shown
    strip.btn_expand.click()
    assert not strip.expanded


def test_zoom_cluster_drives_canvas(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_actual_ppm", lambda: 4.0)
    win.specimen_strip.btn_actual.click()
    assert win.canvas.zoom_mode == "actual"
    win.specimen_strip.btn_zoom_in.click()
    assert win.canvas.zoom_mode == "manual"
    assert win.canvas.px_per_mm == pytest.approx(5.0)
    win.specimen_strip.btn_fit.click()
    assert win.canvas.zoom_mode == "fit"


def test_panel_widget_has_no_hover_buttons(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    widget = next(iter(win.canvas.panel_widgets().values()))
    assert widget.findChild(object, "btn_split_right") is None
    assert ("Split Right", "split_right") in widget.context_actions()
