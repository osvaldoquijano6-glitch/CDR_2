"""E3: huecos de tensión (Zona A), reconexión automática, P25 240h, TDD Icc/IL."""

import pandas as pd
import pytest

from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.result import TestStatus
from gcv.quality_power.tdd import limite_armonica, resolver_fila

from tests.unit.helpers import make_dataset, ts

V_BASE = 230_000.0


# ─── CE-V-07 Huecos de tensión ───────────────────────────────────────────────
def _hueco_df(v_durante_pu: float, t_recupera_s: float) -> pd.DataFrame:
    """1 kHz: pre-falla 1.0 pu, hueco de 0.3 s, recuperación a 0.95 pu."""
    n_pre, n_falla, n_post = 500, 300, 1500
    times = ts(n_pre + n_falla + n_post, freq="1ms")
    v = ([V_BASE] * n_pre + [v_durante_pu * V_BASE] * n_falla
         + [0.95 * V_BASE] * n_post)
    return pd.DataFrame({"timestamp": times, "voltage": v})


def test_hueco_dentro_de_zona_a_cumple():
    # asíncrona B: envolvente inferior permite V=0 hasta 0.40 s → hueco de 0.3 s a 0.2 pu cumple
    df = _hueco_df(v_durante_pu=0.20, t_recupera_s=0.3)
    r = get_test("CE-V-07").run(make_dataset(df), {
        "v_base_v": V_BASE, "tecnologia": "ASINCRONA", "tipo_ce": "B"})
    assert r.status == TestStatus.CUMPLE, r.warnings


def test_hueco_fuera_de_zona_a_no_cumple_sincrona():
    # síncrona B: la envolvente exige V ≥ 0.70 pu desde t=0.25 s → 0.2 pu por 0.3 s viola
    df = _hueco_df(v_durante_pu=0.20, t_recupera_s=0.3)
    r = get_test("CE-V-07").run(make_dataset(df), {
        "v_base_v": V_BASE, "tecnologia": "SINCRONA", "tipo_ce": "B"})
    assert r.status == TestStatus.NO_CUMPLE


def test_hueco_sin_parametros_bloquea():
    df = _hueco_df(0.5, 0.3)
    r = get_test("CE-V-07").run(make_dataset(df), {"v_base_v": V_BASE})
    assert r.status == TestStatus.NO_EVALUABLE


# ─── CE-F-10 Reconexión automática ───────────────────────────────────────────
def _reconexion_df(rampa_mw_min: float, f_previa: float = 59.9):
    """10 min previos estables + reconexión con rampa dada (muestras 1 s)."""
    n_pre, n_post = 600, 600
    times = ts(n_pre + n_post)
    f = [f_previa] * n_pre + [60.0] * n_post
    v = [V_BASE] * (n_pre + n_post)
    p = [0.0] * n_pre + [min(rampa_mw_min * (i / 60.0), 50.0) for i in range(n_post)]
    df = pd.DataFrame({"timestamp": times, "frequency": f, "voltage": v, "active_power": p})
    return df, str(times[n_pre])


def test_reconexion_cumple():
    df, t_rec = _reconexion_df(rampa_mw_min=8.0)  # 8 MW/min ≤ 10 % de 100 MW
    r = get_test("CE-F-10").run(make_dataset(df), {
        "t_reconexion": t_rec, "cin_mw": 100.0, "v_base_v": V_BASE})
    assert r.status == TestStatus.CUMPLE, [c.detalle for c in r.pass_fail_details]


def test_reconexion_rampa_excedida():
    df, t_rec = _reconexion_df(rampa_mw_min=25.0)  # 25 MW/min > 10 MW/min
    r = get_test("CE-F-10").run(make_dataset(df), {
        "t_reconexion": t_rec, "cin_mw": 100.0, "v_base_v": V_BASE})
    assert r.status == TestStatus.NO_CUMPLE
    rampa = next(c for c in r.pass_fail_details if c.nombre == "rampa_toma_de_carga")
    assert rampa.cumple is False


def test_reconexion_frecuencia_previa_fuera():
    df, t_rec = _reconexion_df(rampa_mw_min=8.0, f_previa=60.5)  # fuera de 58.8-60.2
    r = get_test("CE-F-10").run(make_dataset(df), {
        "t_reconexion": t_rec, "cin_mw": 100.0, "v_base_v": V_BASE})
    assert r.status == TestStatus.NO_CUMPLE


# ─── CE-P-01 240 h / paro / no-inyección ─────────────────────────────────────
def _serie_5min(p_values_por_hora: list[float]) -> pd.DataFrame:
    """Serie 5-minutal (12 muestras/h) con f y V nominales."""
    p = [v for v in p_values_por_hora for _ in range(12)]
    times = pd.date_range("2026-06-01", periods=len(p), freq="5min")
    return pd.DataFrame({"timestamp": times, "active_power": p,
                         "frequency": [60.0] * len(p), "voltage": [V_BASE] * len(p)})


def test_capacidad_240h():
    df = _serie_5min([-2.0] * 250)  # 250 h sin inyección
    r = get_test("CE-P-01").run(make_dataset(df), {
        "capacidad_declarada_mw": 100.0, "umbral_operacion_mw": -100.0,
        "modalidad": "abasto_aislado"})
    assert r.status == TestStatus.CUMPLE
    nombres = {c.nombre for c in r.pass_fail_details}
    assert {"horas_de_operacion", "horas_de_paro", "no_inyeccion"} <= nombres


def test_capacidad_240h_con_inyeccion_no_cumple():
    df = _serie_5min([-2.0] * 247 + [1.5, 2.0, -1.0])  # horas con inyección
    r = get_test("CE-P-01").run(make_dataset(df), {
        "capacidad_declarada_mw": 100.0, "umbral_operacion_mw": -100.0,
        "modalidad": "abasto_aislado"})
    assert r.status == TestStatus.NO_CUMPLE


# ─── TDD por Icc/IL (Tablas 2.8) ─────────────────────────────────────────────
def test_resolver_tabla_tdd():
    fila = resolver_fila(v_kv=23.0, icc_il=35.0)   # ≤69 kV, fila 20-50
    assert fila["datd"] == 8.0
    assert limite_armonica(5, fila) == 7.0     # impar 2<h<11
    assert limite_armonica(4, fila) == pytest.approx(1.75)  # par = 25 %
    assert limite_armonica(13, fila) == 3.5    # 11≤h<17
    assert limite_armonica(50, fila) == pytest.approx(0.125)  # par de 35≤h≤50
    fila_at = resolver_fila(v_kv=230.0, icc_il=60.0)
    assert fila_at["datd"] == 3.75


def test_ce_q05_con_tabla_resuelta():
    df = pd.DataFrame({
        "timestamp": ts(20),
        "tdd": [6.0] * 20,                 # < 8.0 (fila 20-50, ≤69 kV)
        "harmonic_current_5": [5.0] * 20,  # < 7.0
        "harmonic_current_13": [4.0] * 20, # > 3.5 → NO CUMPLE
    })
    r = get_test("CE-Q-05").run(make_dataset(df), {"v_kv": 23.0, "icc_il": 35.0})
    assert r.status == TestStatus.NO_CUMPLE
    checks = {c.nombre: c for c in r.pass_fail_details}
    assert checks["tdd_p95"].cumple is True
    assert checks["h13_p95"].cumple is False


def test_registro_e3():
    assert {"CE-V-07", "CE-F-10"} <= set(implemented_ids())
