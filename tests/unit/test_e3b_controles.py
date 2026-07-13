"""E3b: modos de control V/Q/FP (3.5.3) y limitación total/parcial (2.2.5/2.2.6)."""

import pandas as pd

from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.result import TestStatus

from tests.unit.helpers import make_dataset, ts


def _escalon_q(t_respuesta_s: float, error_final: float = 0.0) -> pd.DataFrame:
    """Consigna Q: 10 → 20 MVAr en t=60 s; respuesta rampa de t_respuesta_s."""
    n = 180
    times = ts(n)
    sp = [10.0] * 60 + [20.0] * 120
    q = []
    for i in range(n):
        if i < 60:
            q.append(10.0)
        else:
            avance = min((i - 60) / max(t_respuesta_s, 1e-9), 1.0)
            q.append(10.0 + 10.0 * avance + (error_final if avance >= 1.0 else 0.0))
    return pd.DataFrame({"timestamp": times, "reactive_power": q, "setpoint_q": sp})


def test_control_q_cumple():
    df = _escalon_q(t_respuesta_s=2.0)  # t90≈1.8s ≤3, estab ≤5, error 0
    r = get_test("CE-V-05").run(make_dataset(df), {"error_base": 50.0})  # Qmax 50 MVAr
    assert r.status == TestStatus.CUMPLE, [c.detalle for c in r.pass_fail_details]
    checks = {c.nombre: c for c in r.pass_fail_details}
    assert checks["alcance_90pct"].cumple is True
    assert checks["error_regimen_permanente"].cumple is True


def test_control_q_lento_no_cumple():
    df = _escalon_q(t_respuesta_s=20.0)  # t90 ≈ 18 s > 3 s
    r = get_test("CE-V-05").run(make_dataset(df), {"error_base": 50.0})
    assert r.status == TestStatus.NO_CUMPLE


def test_control_q_error_excesivo():
    df = _escalon_q(t_respuesta_s=2.0, error_final=2.0)  # error 2 MVAr = 4 % de 50 > 2 %
    r = get_test("CE-V-05").run(make_dataset(df), {"error_base": 50.0})
    checks = {c.nombre: c for c in r.pass_fail_details}
    assert checks["error_regimen_permanente"].cumple is False


def test_control_sin_consigna_no_evaluable():
    df = pd.DataFrame({"timestamp": ts(60), "reactive_power": [10.0] * 60,
                       "setpoint_q": [10.0] * 60})
    r = get_test("CE-V-05").run(make_dataset(df), {"error_base": 50.0})
    assert r.status == TestStatus.NO_EVALUABLE


# ─── CE-F-08 Limitación ──────────────────────────────────────────────────────
def _limitacion_df(t_caida_s: float, fs: str = "500ms") -> tuple[pd.DataFrame, str]:
    n_pre, n_post = 120, 240
    times = ts(n_pre + n_post, freq=fs)
    paso_s = 0.5 if fs == "500ms" else 1.0
    p = [50.0] * n_pre + [max(50.0 * (1 - (i * paso_s) / t_caida_s), 0.0)
                          for i in range(n_post)]
    df = pd.DataFrame({"timestamp": times, "active_power": p})
    return df, str(times[n_pre])


def test_limitacion_total_asincrona_cumple():
    df, t0 = _limitacion_df(t_caida_s=3.0)  # llega a ~0 en 3 s < 5 s
    r = get_test("CE-F-08").run(make_dataset(df), {
        "modo": "total", "tecnologia": "ASINCRONA", "umbral_cero_mw": 0.5,
        "t_consigna": t0})
    assert r.status == TestStatus.CUMPLE


def test_limitacion_total_sincrona_criterio_invertido():
    # síncrona: debe tardar MÁS de 5 s (rampa controlada); 3 s → NO CUMPLE
    df, t0 = _limitacion_df(t_caida_s=3.0)
    r = get_test("CE-F-08").run(make_dataset(df), {
        "modo": "total", "tecnologia": "SINCRONA", "umbral_cero_mw": 0.5,
        "t_consigna": t0})
    assert r.status == TestStatus.NO_CUMPLE
    # 30 s → CUMPLE para síncrona
    df2, t0b = _limitacion_df(t_caida_s=30.0)
    r2 = get_test("CE-F-08").run(make_dataset(df2), {
        "modo": "total", "tecnologia": "SINCRONA", "umbral_cero_mw": 0.5,
        "t_consigna": t0b})
    assert r2.status == TestStatus.CUMPLE


def test_limitacion_parcial_requiere_criterio_cenace():
    df, t0 = _limitacion_df(t_caida_s=3.0)
    r = get_test("CE-F-08").run(make_dataset(df), {"modo": "parcial", "t_consigna": t0})
    assert r.status == TestStatus.NO_EVALUABLE
    assert "CENACE" in (r.pass_fail_details[0].detalle or "")


def test_registro_e3b():
    assert {"CE-V-04", "CE-V-05", "CE-V-06", "CE-F-08"} <= set(implemented_ids())
