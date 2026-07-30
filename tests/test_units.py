import pytest
from figspec.units import parse_length, pt_to_mm, mm_to_pt

def test_parse_units():
    assert parse_length("6pt") == 6.0
    assert parse_length("183mm") == pytest.approx(518.74, abs=0.01)
    assert parse_length("1in") == 72.0
    assert parse_length("1.5 cm") == pytest.approx(42.52, abs=0.01)

def test_default_unit():
    assert parse_length("183", default_unit="mm") == pytest.approx(518.74, abs=0.01)
    assert parse_length("6", default_unit="pt") == 6.0

def test_roundtrip_and_errors():
    assert pt_to_mm(mm_to_pt(89.0)) == pytest.approx(89.0)
    with pytest.raises(ValueError):
        parse_length("abc")
    with pytest.raises(ValueError):
        parse_length("10 furlongs")
