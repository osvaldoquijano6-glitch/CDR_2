import pandas as pd
import pytest

from gcv.signal_processing.derivatives import max_abs_rocof, rocof_series
from gcv.signal_processing.droop import DroopParams, derive_p_op, expected_power, response_error
from gcv.signal_processing.events import detect_disconnection, detect_signal_loss
from gcv.signal_processing.statistics import sustained_max, time_in_bands
from gcv.signal_processing.steps import detect_steps, response_times

from tests.unit.helpers import ts


# ─── ROCOF ────────────────────────────────────────────────────────────────────
def test_rocof_rampa_conocida():
    # 60 → 58 Hz en 1 s (muestreo 100 ms) → df/dt = −2 Hz/s
    times = pd.Series(ts(21, freq="100ms"))
    freq = pd.Series([60.0] * 5 + [60.0 - 0.2 * i for i in range(1, 11)] + [58.0] * 6)
    peak = max_abs_rocof(times, freq, window_s=0.1)
    assert peak["rocof_max_abs_hz_s"] == pytest.approx(2.0, rel=1e-6)
    assert peak["signo"] == -1.0


def test_rocof_ignora_timestamps_duplicados():
    times = pd.Series(pd.to_datetime(
        ["2026-07-01 10:00:00", "2026-07-01 10:00:00", "2026-07-01 10:00:01"]))
    freq = pd.Series([60.0, 61.0, 60.5])
    serie = rocof_series(times, freq, window_s=0)
    assert pd.isna(serie.iloc[1])  # Δt = 0 no produce derivada infinita


# ─── Escalones y tiempos de respuesta ────────────────────────────────────────
def test_detect_steps_y_response_times():
    times = pd.Series(ts(120))
    freq = pd.Series([60.0] * 60 + [60.8] * 60)
    steps = detect_steps(times, freq, min_delta=0.5, window_s=5)
    assert len(steps) == 1
    assert steps[0].delta == pytest.approx(0.8, abs=0.05)

    # potencia baja de 80 a 60 con rampa de 10 s tras el escalón
    power = pd.Series([80.0] * 60 + [80.0 - 2.0 * min(i, 10) for i in range(60)])
    rt = response_times(times, power, steps[0].t, target=60.0, tolerance=2.0)
    assert rt["t1_s"] == pytest.approx(9.0, abs=2.0)
    assert rt["t2_s"] is not None
    assert rt["en_banda_final"] is True


def test_response_times_nunca_llega():
    times = pd.Series(ts(20))
    power = pd.Series([80.0] * 20)
    rt = response_times(times, power, times.iloc[5], target=60.0, tolerance=2.0)
    assert rt["t1_s"] is None and rt["t2_s"] is None


# ─── Droop ────────────────────────────────────────────────────────────────────
def test_expected_power_alta():
    dp = DroopParams(p_ref_mw=100.0, estatismo=0.05, zona="alta", umbral_hz=60.2)
    f = pd.Series([60.0, 60.2, 60.8])
    exp = expected_power(f, p_op=80.0, params=dp)
    # pendiente = 100/(0.05·60) = 33.33 MW/Hz; a 60.8: 80 − 0.6·33.33 = 60
    assert exp.iloc[0] == pytest.approx(80.0)
    assert exp.iloc[1] == pytest.approx(80.0)
    assert exp.iloc[2] == pytest.approx(60.0, abs=1e-6)


def test_expected_power_baja_y_ambas():
    dp_baja = DroopParams(p_ref_mw=100.0, estatismo=0.05, zona="baja", umbral_hz=59.8)
    exp = expected_power(pd.Series([59.2]), p_op=80.0, params=dp_baja)
    assert exp.iloc[0] == pytest.approx(80.0 + 0.6 * 100 / (0.05 * 60))

    dp_cpf = DroopParams(p_ref_mw=100.0, estatismo=0.05, zona="ambas", banda_muerta_hz=0.03)
    exp2 = expected_power(pd.Series([60.0, 60.02, 60.63]), p_op=80.0, params=dp_cpf)
    assert exp2.iloc[0] == pytest.approx(80.0)
    assert exp2.iloc[1] == pytest.approx(80.0)  # dentro de banda muerta
    assert exp2.iloc[2] == pytest.approx(80.0 - 0.6 * 100 / (0.05 * 60))


def test_droop_params_invalidos():
    with pytest.raises(ValueError, match="umbral_hz"):
        DroopParams(p_ref_mw=100, estatismo=0.05, zona="alta")
    with pytest.raises(ValueError, match="Zona"):
        DroopParams(p_ref_mw=100, estatismo=0.05, zona="lateral")


def test_derive_p_op_segmento_estable():
    times = pd.Series(ts(200))
    freq = pd.Series([60.0] * 80 + [60.8] * 120)
    power = pd.Series([80.0] * 80 + [60.0] * 120)
    p_op = derive_p_op(times, freq, power)
    assert p_op["p_op_mw"] == pytest.approx(80.0)
    assert p_op["metodo"] == "segmento_estable_pre_escalon"


def test_response_error_en_zona_activa():
    power = pd.Series([80.0, 61.0, 59.5])
    expected = pd.Series([80.0, 60.0, 60.0])
    active = pd.Series([False, True, True])
    err = response_error(power, expected, active)
    assert err["n"] == 2
    assert err["error_abs_max_mw"] == pytest.approx(1.0)


# ─── Eventos y estadísticos ──────────────────────────────────────────────────
def test_detect_disconnection():
    times = pd.Series(ts(10))
    power = pd.Series([50.0] * 4 + [0.0, 0.0] + [50.0] * 4)
    eps = detect_disconnection(times, power, threshold=5.0)
    assert len(eps) == 1
    assert eps[0].muestras == 2


def test_detect_signal_loss():
    times = pd.Series(ts(6))
    values = pd.Series([1.0, None, None, None, 1.0, 1.0])
    eps = detect_signal_loss(times, values)
    assert len(eps) == 1 and eps[0].muestras == 3


def test_time_in_bands_y_sustained_max():
    times = pd.Series(ts(10))
    values = pd.Series([59.9] * 5 + [60.5] * 5)
    bandas = time_in_bands(times, values, [(59.8, 60.0), (60.4, 60.6)])
    assert bandas[0]["muestras"] == 5 and bandas[0]["permanencia_s"] == pytest.approx(5.0)

    sm = sustained_max(times, pd.Series([10.0] * 5 + [100.0] * 5), window_s=3)
    assert sm["valor"] == pytest.approx(100.0)
