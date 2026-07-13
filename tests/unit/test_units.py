import pandas as pd
import pytest

from gcv.normalization.units import convert_series, parse_unit, pu_to_physical, unit_from_header


def test_parse_unit_familias():
    kw = parse_unit("kW")
    assert kw.cantidad == "active_power" and kw.canonica == "MW" and kw.factor == 1e-3
    kv = parse_unit("kV")
    assert kv.canonica == "V" and kv.factor == 1e3
    assert parse_unit("kvar").factor == 1e-3
    assert parse_unit("Hz").factor == 1.0
    assert parse_unit("ms").factor == 1e-3
    assert parse_unit("desconocida") is None
    assert parse_unit(None) is None


def test_unit_from_header():
    assert unit_from_header("P [kW]") == "kW"
    assert unit_from_header("Tension (kV)") == "kV"
    # el texto entre paréntesis que no es unidad no se confunde
    assert unit_from_header("Potencia (total)") is None
    assert unit_from_header("frequency") is None


def test_convert_series():
    s = pd.Series([1000.0, 2000.0])
    out = convert_series(s, parse_unit("kW"))
    assert out.tolist() == [1.0, 2.0]


def test_pu_requiere_base_positiva():
    with pytest.raises(ValueError):
        pu_to_physical(pd.Series([1.0]), base=0)
    assert pu_to_physical(pd.Series([1.05]), base=230.0).iloc[0] == pytest.approx(241.5)
