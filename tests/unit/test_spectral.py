"""Tests del cálculo espectral de armónicos desde forma de onda."""

import numpy as np
import pandas as pd
import pytest

from gcv.quality_power.spectral import (
    columnas_armonicas_desde_onda, espectro_desde_forma_de_onda)


def _onda(fs=7680.0, dur_s=1.0, armonicos=None, f0=60.0):
    """Señal sintética: fundamental 1 pu + armónicos {orden: amplitud_pu}."""
    t = np.arange(0, dur_s, 1.0 / fs)
    x = np.sin(2 * np.pi * f0 * t)
    for h, amp in (armonicos or {}).items():
        x = x + amp * np.sin(2 * np.pi * h * f0 * t)
    ts = pd.date_range("2026-01-01", periods=len(t), freq=pd.Timedelta(seconds=1.0 / fs))
    return pd.DataFrame({"timestamp": ts, "voltage": x})


def test_espectro_recupera_armonicos():
    df = _onda(armonicos={5: 0.05, 7: 0.03})   # 5 % de h5, 3 % de h7
    esp = espectro_desde_forma_de_onda(df, "voltage")
    assert esp is not None and esp.n_ventanas >= 4
    assert esp.magnitudes_pct[5] == pytest.approx(5.0, abs=0.15)
    assert esp.magnitudes_pct[7] == pytest.approx(3.0, abs=0.15)
    assert esp.magnitudes_pct[3] < 0.2          # inexistente ≈ 0
    assert esp.thd_pct == pytest.approx(np.hypot(5.0, 3.0), abs=0.3)


def test_espectro_limita_orden_por_nyquist():
    df = _onda(fs=1920.0, armonicos={5: 0.05})  # Nyquist: orden 16
    esp = espectro_desde_forma_de_onda(df, "voltage")
    assert esp is not None
    assert max(esp.magnitudes_pct) <= 16
    assert any("Nyquist" in a or "limita" in a for a in esp.advertencias)


def test_espectro_rechaza_muestreo_irregular():
    df = _onda()
    ts = df["timestamp"].copy()
    ts.iloc[100:] = ts.iloc[100:] + pd.Timedelta(seconds=0.05)  # salto
    assert espectro_desde_forma_de_onda(df.assign(timestamp=ts), "voltage") is None


def test_columnas_para_evaluador():
    from gcv.evaluation.power_quality.armonicos import ArmonicosTension
    from gcv.evaluation.result import TestStatus
    from tests.unit.helpers import make_dataset, make_spec

    df = columnas_armonicas_desde_onda(_onda(armonicos={5: 0.04}), "voltage", "voltage")
    assert df is not None and "harmonic_voltage_5" in df.columns
    spec = make_spec("CE-Q-04", ["timestamp", "thd_v"], limites={
        "thd_max_pct": 5.0, "armonicos": {5: 5.0}})
    result = ArmonicosTension(spec).run(make_dataset(df))
    assert result.status == TestStatus.CUMPLE
    check = {c.nombre: c for c in result.pass_fail_details}["h5_p95"]
    assert check.valor_medido == pytest.approx(4.0, abs=0.15)
