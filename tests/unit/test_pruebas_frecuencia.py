"""Tests de las pruebas de frecuencia FASE 3: CE-F-02 (ROCOF) y droop 03/04/05."""

import pandas as pd
import pytest

from gcv.evaluation.frequency.respuesta_frecuencia import (
    ControlPrimarioFrecuencia,
    RespuestaAltaFrecuencia,
    RespuestaBajaFrecuencia,
)
from gcv.evaluation.frequency.rocof import Rocof
from gcv.evaluation.result import TestStatus

from tests.unit.helpers import make_dataset, make_spec, ts

_VARS = ["timestamp", "frequency", "active_power"]


# ─── CE-F-02 ROCOF ────────────────────────────────────────────────────────────
def _rocof_df(power_drop: bool) -> pd.DataFrame:
    times = ts(41, freq="100ms")
    freq = [60.0] * 10 + [60.0 - 0.2 * i for i in range(1, 11)] + [58.0] * 21
    power = [50.0] * 41
    if power_drop:
        power = [50.0] * 25 + [0.0] * 16  # disparo tras el evento
    return pd.DataFrame({"timestamp": times, "frequency": freq, "active_power": power})


def _rocof_spec():
    return make_spec("CE-F-02", _VARS, limites={
        "rocof_inmunidad_hz_s": 2.0,
        "severidad_minima_hz_s": 1.9,
        "ventana_rocof_ms": 100,
        "umbral_desconexion_mw": 5.0,
    }, fs_min=10)


def test_rocof_cumple():
    result = Rocof(_rocof_spec()).run(make_dataset(_rocof_df(power_drop=False)))
    assert result.status == TestStatus.CUMPLE
    nombres = {c.nombre: c for c in result.pass_fail_details}
    assert nombres["severidad_del_evento"].cumple is True
    assert nombres["continuidad_operativa"].cumple is True
    assert nombres["severidad_del_evento"].valor_medido == pytest.approx(2.0, rel=1e-6)


def test_rocof_no_cumple_por_disparo():
    result = Rocof(_rocof_spec()).run(make_dataset(_rocof_df(power_drop=True)))
    assert result.status == TestStatus.NO_CUMPLE
    nombres = {c.nombre: c for c in result.pass_fail_details}
    assert nombres["continuidad_operativa"].cumple is False


def test_rocof_sin_limites_no_evaluable():
    spec = make_spec("CE-F-02", _VARS, limites={})
    result = Rocof(spec).run(make_dataset(_rocof_df(power_drop=False)))
    assert result.status == TestStatus.NO_EVALUABLE


# ─── Droop alta/baja/CPF ─────────────────────────────────────────────────────
def _droop_df(responde: bool, zona: str) -> pd.DataFrame:
    """80 muestras estables a 60 Hz / 80 MW, escalón y respuesta droop."""
    n_pre, n_post = 80, 120
    if zona == "alta":
        f_post, p_final = 60.8, 60.0   # S=5%, umbral 60.2 → ΔP = −20
    else:
        f_post, p_final = 59.2, 100.0  # umbral 59.8 → ΔP = +20
    times = ts(n_pre + n_post)
    freq = [60.0] * n_pre + [f_post] * n_post
    if responde:
        rampa = [80.0 + (p_final - 80.0) * min(i, 5) / 5 for i in range(n_post)]
        power = [80.0] * n_pre + rampa
    else:
        power = [80.0] * (n_pre + n_post)
    return pd.DataFrame({"timestamp": times, "frequency": freq, "active_power": power})


def _droop_limites(zona: str) -> dict:
    lim = {
        "tolerancia_pct_pref": 5.0,
        "cumplimiento_minimo_pct": 90.0,
        "estatismos_admisibles": [0.03, 0.05, 0.08],
    }
    if zona == "alta":
        lim["umbral_hz"] = 60.2
    elif zona == "baja":
        lim["umbral_hz"] = 59.8
    else:
        lim["banda_muerta_hz"] = 0.03
    return lim


_PARAMS = {"estatismo": 0.05, "p_ref_mw": 100.0}


def test_alta_frecuencia_cumple():
    spec = make_spec("CE-F-03", _VARS, limites=_droop_limites("alta"))
    result = RespuestaAltaFrecuencia(spec).run(make_dataset(_droop_df(True, "alta")), _PARAMS)
    assert result.status == TestStatus.CUMPLE
    medidos = {m.nombre: m for m in result.measured_values}
    assert medidos["p_op"].valor == pytest.approx(80.0)


def test_alta_frecuencia_no_cumple_sin_respuesta():
    spec = make_spec("CE-F-03", _VARS, limites=_droop_limites("alta"))
    result = RespuestaAltaFrecuencia(spec).run(make_dataset(_droop_df(False, "alta")), _PARAMS)
    assert result.status == TestStatus.NO_CUMPLE
    err = next(c for c in result.pass_fail_details if c.nombre == "error_respuesta")
    assert err.cumple is False


def test_baja_frecuencia_cumple():
    spec = make_spec("CE-F-04", _VARS, limites=_droop_limites("baja"))
    result = RespuestaBajaFrecuencia(spec).run(make_dataset(_droop_df(True, "baja")), _PARAMS)
    assert result.status == TestStatus.CUMPLE


def test_estatismo_no_admisible():
    spec = make_spec("CE-F-03", _VARS, limites=_droop_limites("alta"))
    params = {"estatismo": 0.04, "p_ref_mw": 100.0}
    result = RespuestaAltaFrecuencia(spec).run(make_dataset(_droop_df(True, "alta")), params)
    adm = next(c for c in result.pass_fail_details if c.nombre == "estatismo_admisible")
    assert adm.cumple is False
    assert result.status == TestStatus.NO_CUMPLE


def test_faltan_parametros_protocolo_bloquea():
    spec = make_spec("CE-F-03", _VARS, limites=_droop_limites("alta"))
    result = RespuestaAltaFrecuencia(spec).run(make_dataset(_droop_df(True, "alta")), {})
    assert result.status == TestStatus.NO_EVALUABLE
    assert any("estatismo" in w for w in result.warnings)
    assert any("p_ref_mw" in w for w in result.warnings)


def test_cpf_con_tiempos_de_establecimiento():
    lim = _droop_limites("ambas")
    lim["t_establecimiento_max_s"] = 30.0
    spec = make_spec("CE-F-05", _VARS, limites=lim)
    # CPF zona "ambas": el escenario de alta frecuencia también la activa
    result = ControlPrimarioFrecuencia(spec).run(make_dataset(_droop_df(True, "alta")), _PARAMS)
    t2 = next((c for c in result.pass_fail_details
               if c.nombre == "tiempo_de_establecimiento"), None)
    assert t2 is not None
    assert result.status in (TestStatus.CUMPLE, TestStatus.NO_CUMPLE)
