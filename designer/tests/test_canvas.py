import pytest
from figspec_designer.document import DesignerDocument
from figspec_designer.model.ops import split_panel
from figspec_designer.model.tree import iter_panels
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
