def test_new_locations_importable():
    from figspec.layout.tree import PanelNode, SplitNode, new_panel  # noqa: F401
    from figspec.layout.ops import split_panel, snap_ratios  # noqa: F401
    from figspec.layout.flatten import PanelRect, flatten, assign_labels, derive  # noqa: F401
    from figspec.layout.history import History  # noqa: F401
    from figspec.document import DesignerDocument, MissingDesignerData  # noqa: F401
    from figspec.presets import PRESETS, PRESET_CONSTRAINTS  # noqa: F401


def test_shims_are_same_objects():
    import figspec.layout.tree as new_tree
    import figspec_designer.model.tree as old_tree
    assert old_tree.PanelNode is new_tree.PanelNode
    import figspec.document as new_doc
    import figspec_designer.document as old_doc
    assert old_doc.DesignerDocument is new_doc.DesignerDocument
    import figspec.presets as new_p
    import figspec_designer.presets as old_p
    assert old_p.PRESETS is new_p.PRESETS


def test_figspec_stays_qt_free():
    import sys
    for mod in list(sys.modules):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import importlib
    import figspec.document, figspec.presets, figspec.layout.ops  # noqa: F401
    importlib.reload(figspec.document)
    assert not any(m.startswith("PySide6") for m in sys.modules)
