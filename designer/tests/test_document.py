import json
import pytest
from figspec.spec import SpecError
from figspec_designer.document import DesignerDocument, MissingDesignerData
from figspec_designer.model.ops import split_panel
from figspec_designer.model.tree import iter_panels


def _two_panel_doc():
    doc = DesignerDocument.default()
    first = next(iter_panels(doc.tree)).id
    doc.tree = split_panel(doc.tree, first, "right")
    return doc


def test_default_document():
    doc = DesignerDocument.default()
    assert doc.target.journal_preset == "nature_double"
    assert doc.target.figure_width_mm == 183.0
    assert len(list(iter_panels(doc.tree))) == 1


def test_to_spec_dict_shape():
    doc = _two_panel_doc()
    d = doc.to_spec_dict()
    assert [p["label"] for p in d["panels"]] == ["a", "b"]
    a = d["panels"][0]
    assert a["x_mm"] == 0.0 and a["w_mm"] == 89.5  # (183-4)/2
    assert a["w_px"] == 2114
    assert d["designer"]["tree"]["type"] == "split"


def test_json_roundtrip():
    doc = _two_panel_doc()
    data = json.loads(doc.to_json())
    doc2 = DesignerDocument.from_spec_dict(data)
    assert doc2.to_spec_dict() == doc.to_spec_dict()


def test_open_without_designer_sidecar():
    data = _two_panel_doc().to_spec_dict()
    del data["designer"]
    with pytest.raises(MissingDesignerData):
        DesignerDocument.from_spec_dict(data)


def test_open_malformed_spec():
    with pytest.raises(SpecError):
        DesignerDocument.from_spec_dict({"nope": 1})
