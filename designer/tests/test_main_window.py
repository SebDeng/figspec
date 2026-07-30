import json
from figspec.spec import parse_spec
from figspec_designer.model.tree import iter_panels
from figspec_designer.ui.main_window import MainWindow


def _first_panel(win):
    return next(iter_panels(win.doc.tree)).id


def test_split_and_labels(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    assert sorted(win.doc.labels().values()) == ["a", "b"]


def test_close_last_panel_is_noop(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("close", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 1


def test_undo_redo(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    assert len(list(iter_panels(win.doc.tree))) == 2
    win.undo()
    assert len(list(iter_panels(win.doc.tree))) == 1
    win.redo()
    assert len(list(iter_panels(win.doc.tree))) == 2


def test_apply_ratios_updates_model(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    win.apply_ratios((), (0.6, 0.4))
    rects = sorted(win.doc.panel_rects(), key=lambda r: r.x_mm)
    assert abs(rects[0].w_mm - (183 - 4) * 0.6) < 1e-6


def test_export_valid_and_copy(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_right", _first_panel(win))
    data = json.loads(win.export_json_text())
    target, constraints, panels, designer = parse_spec(data)
    assert len(panels) == 2 and designer is not None
    win.copy_json()
    from PySide6.QtWidgets import QApplication
    assert json.loads(QApplication.clipboard().text()) == data


def test_save_and_open_roundtrip(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.do_action("split_down", _first_panel(win))
    p = tmp_path / "layout.figspec.json"
    win.save_json(p)
    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.open_json(p) is None  # no error
    assert win2.doc.to_spec_dict() == win.doc.to_spec_dict()


def test_open_without_sidecar_reports_error(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    data = win.doc.to_spec_dict()
    del data["designer"]
    p = tmp_path / "plain.json"
    p.write_text(json.dumps(data))
    err = win.open_json(p)
    assert err is not None and "designer" in err


def test_smoke_flag():
    from figspec_designer.app import main
    assert main(["--smoke"]) == 0
