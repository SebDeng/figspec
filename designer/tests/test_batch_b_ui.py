"""Batch B UI tests: height warning, preset tooltips, label style, lint dock."""
from PySide6.QtCore import Qt

from figspec_designer.ui.main_window import MainWindow


def test_preset_tooltips(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    combo = win.topbar.preset_combo
    tip = combo.itemData(combo.findText("nature_double"), Qt.ToolTipRole)
    assert tip and "183" in tip
    assert combo.itemData(combo.findText("custom"), Qt.ToolTipRole) in (None, "")


def test_height_warning_flips_property(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    spin = win.topbar.height_spin
    assert spin.property("overLimit") is not True  # 100mm under 170 limit
    spin.setValue(180.0)  # nature_double limit 170
    assert spin.property("overLimit") is True
    assert "170" in spin.toolTip()
    spin.setValue(150.0)
    assert spin.property("overLimit") is not True
    assert spin.toolTip() == ""


def test_height_warning_tooltip_has_no_repo_path(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    spin = win.topbar.height_spin
    spin.setValue(180.0)  # nature_double limit 170
    tip = spin.toolTip()
    assert "170" in tip
    assert "docs/" not in tip
    assert "publisher figure guidelines" in tip


def test_no_warning_for_custom_or_aps(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("aps_single")
    win.topbar.height_spin.setValue(500.0)
    assert win.topbar.height_spin.property("overLimit") is not True
    win.topbar.preset_combo.setCurrentText("custom")
    assert win.topbar.height_spin.property("overLimit") is not True


def test_label_style_follows_preset(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    from figspec.layout.tree import iter_panels
    pid = next(iter_panels(win.doc.tree)).id
    win.topbar.preset_combo.setCurrentText("science_double")
    assert win.doc.constraints.panel_label_style == "uppercase"
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "A"
    win.do_action("select", pid)
    assert win.sidebar.lbl_label.text() == "A"
    win.topbar.preset_combo.setCurrentText("aps_double")
    assert win.canvas.panel_widgets()[pid].label_widget.text() == "(a)"
    # spec export keeps internal lowercase labels regardless of display
    assert win.doc.to_spec_dict()["panels"][0]["label"] == "a"


def test_label_style_survives_spec_roundtrip(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    data = win.doc.to_spec_dict()
    assert data["constraints"]["panel_label_style"] == "uppercase"


def test_sync_settings_preserves_min_effective_dpi(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.doc.constraints.min_effective_dpi = 450
    win.topbar.gutter_spin.setValue(5.0)  # triggers _on_settings_changed
    assert win.doc.constraints.min_effective_dpi == 450


def test_wireframe_export_uses_label_style(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.topbar.preset_combo.setCurrentText("science_double")
    from figspec_designer.ui.preview_export import render_layout_png
    out = tmp_path / "wf.png"
    assert render_layout_png(win.doc, out) is True
    # can't OCR the letter; assert the code path accepts the style without
    # error and the file is written (letter correctness is pinned by the
    # canvas/sidebar assertions above via the same format_label call)
    assert out.stat().st_size > 0


def test_lint_worker_success(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    from figspec.lint.checks import LintConfig
    from figspec.units import mm_to_pt
    from figspec_designer.ui.lint_runner import LintWorker
    paths = write_samples(tmp_path / "samples")
    cfg = LintConfig(min_font_pt=5.0, min_linewidth_pt=0.25,
                     width_pt=mm_to_pt(183.0))
    worker = LintWorker(str(paths["bad"]), cfg, tmp_path / "out")
    with qtbot.waitSignal(worker.finished_ok, timeout=90000) as blocker:
        worker.start()
    report, annotated = blocker.args
    # render_json shape: summary = {"ready": bool, "strict": bool,
    # "counts": {"PASS": n, "WARN": n, "FAIL": n}}; findings list of dicts
    assert set(report["summary"]["counts"]) == {"PASS", "WARN", "FAIL"}
    assert report["findings"] and "check_id" in report["findings"][0]
    assert isinstance(annotated, list)
    worker.wait()


def test_lint_worker_failure(qtbot, tmp_path):
    from figspec.lint.checks import LintConfig
    from figspec_designer.ui.lint_runner import LintWorker
    not_pdf = tmp_path / "x.pdf"
    not_pdf.write_bytes(b"not a pdf")
    worker = LintWorker(str(not_pdf), LintConfig(), tmp_path / "out")
    with qtbot.waitSignal(worker.failed, timeout=90000) as blocker:
        worker.start()
    assert blocker.args[0]  # non-empty error message
    worker.wait()


def test_lint_dock_populates(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    paths = write_samples(tmp_path / "samples")
    win._start_lint(str(paths["bad"]))
    assert not win.lint_action.isEnabled()  # disabled while running
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=90000)
    dock = win.lint_dock
    assert dock.findings_tree.topLevelItemCount() > 0
    assert dock.summary_label.text()  # verdict + counts populated


def test_lint_dock_error_path(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    bad = tmp_path / "x.pdf"
    bad.write_bytes(b"nope")
    win._start_lint(str(bad))
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=90000)
    assert win.lint_dock.error_label.isVisibleTo(win.lint_dock)


def test_lint_config_includes_min_raster_dpi(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.doc.constraints.min_effective_dpi = 450
    cfg = win._lint_config()
    assert cfg.min_raster_dpi == 450


def test_close_during_running_lint_no_crash(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    paths = write_samples(tmp_path / "samples")
    win._start_lint(str(paths["bad"]))
    # Worker is very likely still running here (just started); close() must
    # wait it out rather than let Qt destroy a running QThread (qFatal ->
    # SIGABRT, exit 134). qtbot.addWidget's own teardown close() would hit
    # this too if we didn't force it explicitly.
    win.close()
    assert win._lint_worker.isRunning() is False


def test_relint_button_reruns_lint(qtbot, tmp_path):
    from figspec.selftest.samples import write_samples
    win = MainWindow()
    qtbot.addWidget(win)
    paths = write_samples(tmp_path / "samples")
    win._start_lint(str(paths["good"]))
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=90000)
    first = win.lint_dock.summary_label.text()
    win.lint_dock.btn_relint.click()
    qtbot.waitUntil(lambda: win.lint_action.isEnabled(), timeout=90000)
    assert win.lint_dock.summary_label.text() == first  # same file, same verdict
