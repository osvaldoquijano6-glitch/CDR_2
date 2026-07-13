import pandas as pd
import pytest

from gcv.quality_power.harmonics import harmonic_columns, percentile_by_harmonic, series_percentile
from gcv.quality_power.rvc import detect_rvc
from gcv.quality_power.unbalance import unbalance_iec_ll, unbalance_nema

from tests.unit.helpers import ts


def test_harmonic_columns_y_percentiles():
    df = pd.DataFrame({
        "harmonic_voltage_3": [1.0, 1.2, 1.1],
        "harmonic_voltage_5": [2.0, 2.4, 2.2],
        "harmonic_current_5": [3.0, 3.1, 3.2],
        "otra": [0, 0, 0],
    })
    assert list(harmonic_columns(df, "voltage")) == [3, 5]
    pcts = percentile_by_harmonic(df, "voltage", 95)
    assert pcts[5] == pytest.approx(2.38, abs=0.01)
    assert series_percentile(pd.Series([1.0, 2.0, 3.0]), 50) == pytest.approx(2.0)
    assert series_percentile(pd.Series([None, None]), 95) is None


def test_unbalance_nema():
    # 230/232/228: media 230, desviación máx 2 → 0.8696 %
    u = unbalance_nema(pd.Series([230.0]), pd.Series([232.0]), pd.Series([228.0]))
    assert u.iloc[0] == pytest.approx(100 * 2 / 230, rel=1e-6)


def test_unbalance_iec_ll_balanceado_es_cero():
    v = pd.Series([230.0, 230.0])
    u = unbalance_iec_ll(v, v, v)
    assert u.iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_unbalance_iec_ll_desbalanceado_positivo():
    u = unbalance_iec_ll(pd.Series([230.0]), pd.Series([225.0]), pd.Series([235.0]))
    assert 0.5 < u.iloc[0] < 5.0


def test_detect_rvc():
    times = pd.Series(ts(120))
    v = pd.Series([230.0] * 60 + [200.0, 200.0] + [230.0] * 58)
    eventos = detect_rvc(times, v, v_nominal=230.0, threshold_pct=5.0, steady_window_s=30)
    assert len(eventos) >= 1
    assert max(e.delta_v_pct_max for e in eventos) == pytest.approx(100 * 30 / 230, abs=0.5)

    sin_eventos = detect_rvc(times, pd.Series([230.0] * 120), 230.0, 5.0)
    assert sin_eventos == []


def test_detect_rvc_base_invalida():
    with pytest.raises(ValueError):
        detect_rvc(pd.Series(ts(3)), pd.Series([1.0, 2.0, 3.0]), 0.0, 5.0)
