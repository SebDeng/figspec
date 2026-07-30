from figspec_designer.model.history import History


def test_undo_redo_cycle():
    h = History("s0")
    assert h.current == "s0" and not h.can_undo() and not h.can_redo()
    h.push("s1")
    h.push("s2")
    assert h.current == "s2" and h.can_undo()
    assert h.undo() == "s1"
    assert h.undo() == "s0"
    assert h.undo() == "s0"  # bottoms out
    assert h.redo() == "s1"
    h.push("s1b")  # push clears redo
    assert not h.can_redo()
    assert h.current == "s1b"
