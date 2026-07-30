import math
import pytest
from figspec.pdf.geometry import Mat

def test_identity_and_apply():
    assert Mat().apply(3, 4) == (3, 4)
    assert Mat(2, 0, 0, 2, 10, 0).apply(1, 1) == (12, 2)

def test_compose_scale_then_translate():
    m = Mat(0.5, 0, 0, 0.5, 0, 0) @ Mat(1, 0, 0, 1, 100, 50)
    assert m.apply(10, 10) == (105.0, 55.0)

def test_vertical_scale():
    assert Mat(0.4, 0, 0, 0.4, 0, 0).vertical_scale() == pytest.approx(0.4)
    rot90 = Mat(0, 1, -1, 0, 0, 0)  # 90-degree rotation
    assert rot90.vertical_scale() == pytest.approx(1.0)
    aniso = Mat(2.0, 0, 0, 0.3, 0, 0)
    assert aniso.vertical_scale() == pytest.approx(0.3)

def test_singular_values():
    s_max, s_min = Mat(2.0, 0, 0, 0.5, 0, 0).singular_values()
    assert (s_max, s_min) == (pytest.approx(2.0), pytest.approx(0.5))
    c, s = math.cos(0.7), math.sin(0.7)
    s_max, s_min = Mat(c, s, -s, c, 0, 0).singular_values()
    assert s_max == pytest.approx(1.0) and s_min == pytest.approx(1.0)

def test_from_seq():
    assert Mat.from_seq([1, 0, 0, 1, 5, 6]) == Mat(1, 0, 0, 1, 5, 6)
