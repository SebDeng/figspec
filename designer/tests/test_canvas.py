import pytest
from figspec.spec import Target
from figspec_designer.document import DesignerDocument
from figspec_designer.model.ops import MIN_PANEL_MM, split_panel
from figspec_designer.model.tree import PanelNode, iter_panels
from figspec_designer.ui.canvas import Canvas


def _doc_two_panels():
    doc = DesignerDocument.default()
    first = next(iter_panels(doc.tree)).id
    doc.tree = split_panel(doc.tree, first, "right")
    return doc


def test_canvas_builds_widgets(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    assert set(canvas.panel_widgets()) == {p.id for p in iter_panels(doc.tree)}
    labels = doc.labels()
    for pid, w in canvas.panel_widgets().items():
        assert w.label_widget.text() == labels[pid]


def test_panel_action_forwarded(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    got = []
    canvas.panel_action.connect(lambda a, pid: got.append((a, pid)))
    pid = next(iter(canvas.panel_widgets()))
    canvas.panel_widgets()[pid].action.emit("split_down", pid)
    assert got == [("split_down", pid)]


def test_commit_splitter_emits_snapped_ratios(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    (path, splitter), = canvas.splitters().items()
    assert path == ()
    got = []
    canvas.ratios_committed.connect(lambda p, r: got.append((p, r)))
    # force uneven pixel sizes then commit
    total = sum(splitter.sizes())
    splitter.setSizes([int(total * 0.333), total - int(total * 0.333)])
    canvas.commit_splitter(splitter, alt_held=False)
    (p, ratios), = got
    assert p == ()
    # snapped ratios correspond to whole 0.5mm sizes over avail = 183-4 = 179mm
    sizes_mm = [r * 179.0 for r in ratios]
    for s in sizes_mm:
        assert s == pytest.approx(round(s * 2) / 2, abs=1e-6)


def test_commit_splitter_clamp_holds_floor_after_snap(qtbot):
    # Reviewer repro: with the clamp applied BEFORE snap_ratios, snap's own
    # 0.5mm rounding of the *other* child's remainder can independently push
    # a near-floor child back under MIN_PANEL_MM after the clamp already ran
    # -- e.g. avail 50.3mm, drag to [45.3, 5.0] snaps to [45.5, 4.8]. Clamp
    # must run AFTER snap (then renormalize) to actually hold the floor.
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(4000, 3000)  # generous px/mm so the drag below lands precisely
    doc = _doc_two_panels()
    doc.target = Target("custom", 50.3, 20.0, 600, 0.0)  # avail_mm == 50.3 exactly
    canvas.set_document(doc)
    (path, splitter), = canvas.splitters().items()
    got = []
    canvas.ratios_committed.connect(lambda p, r: got.append((p, r)))
    # setSizes() rescales proportionally to the splitter's true current
    # width regardless of the sum passed in -- so passing the ratio
    # 45.3 : 5.0 (scaled by 10) reliably reproduces the reviewer's repro
    # position regardless of exact pixel geometry.
    splitter.setSizes([453, 50])
    canvas.commit_splitter(splitter, alt_held=False)
    (p, ratios), = got
    avail_mm = 50.3
    for r in ratios:
        assert r * avail_mm >= MIN_PANEL_MM - 1e-9


def test_selection_highlight(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    pid = next(iter(canvas.panel_widgets()))
    canvas.apply_selection(pid)
    assert canvas.panel_widgets()[pid].property("selected") is True
    canvas.apply_selection(None)
    assert canvas.panel_widgets()[pid].property("selected") is False


def test_selection_persists_across_rebuild(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    pid = next(iter(canvas.panel_widgets()))
    canvas.apply_selection(pid)
    # simulate a rebuild (e.g. triggered by a resizeEvent): new PanelWidget
    # instances are created, so the selection must be reapplied afterward.
    canvas.set_document(doc)
    assert canvas.panel_widgets()[pid].property("selected") is True


def test_swap_armed_highlight(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    pid = next(iter(canvas.panel_widgets()))
    canvas.apply_swap_armed(pid)
    assert canvas.panel_widgets()[pid].property("swapArmed") is True
    canvas.apply_swap_armed(None)
    assert canvas.panel_widgets()[pid].property("swapArmed") is False


def test_swap_armed_persists_across_rebuild(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    pid = next(iter(canvas.panel_widgets()))
    canvas.apply_swap_armed(pid)
    # simulate a rebuild: new PanelWidget instances are created, so the
    # armed cue must be reapplied afterward -- same contract as selection.
    canvas.set_document(doc)
    assert canvas.panel_widgets()[pid].property("swapArmed") is True


def test_load_thumb_caps_larger_axis(qtbot, tmp_path):
    # Regression: _load_thumb capped only pix.width(), so a tall portrait
    # asset (e.g. 100x3000) bypassed the 1200px cap entirely on height.
    from PySide6.QtGui import QImage
    img = QImage(100, 3000, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    path = tmp_path / "tall.png"
    img.save(str(path))
    canvas = Canvas()
    qtbot.addWidget(canvas)
    node = PanelNode(id="p1", asset=str(path), asset_px=(100, 3000))
    thumb, missing = canvas._load_thumb(node)
    assert missing is False
    assert thumb.height() <= 1200


def test_blank_canvas_click_emits_select_none(qtbot):
    from PySide6.QtCore import QPointF, Qt as QtCore
    from PySide6.QtGui import QMouseEvent
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    doc = _doc_two_panels()
    canvas.set_document(doc)
    got = []
    canvas.panel_action.connect(lambda a, pid: got.append((a, pid)))
    # A point inside the canvas but outside the page/panels (the margin).
    event = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(2, 2), QPointF(2, 2),
                        QtCore.LeftButton, QtCore.LeftButton, QtCore.NoModifier)
    canvas.mousePressEvent(event)
    assert got == [("select", None)]
