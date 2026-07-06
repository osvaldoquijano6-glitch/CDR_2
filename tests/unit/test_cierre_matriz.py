"""Cierre 35/35: documentales, rampas, reactivos, CD, P constante y CC."""

import pandas as pd

from gcv.config.settings import MATRIX_PATH
from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.result import TestStatus
from gcv.evaluation.spec import load_matrix

from tests.unit.helpers import make_dataset, ts


def test_cobertura_total():
    assert set(load_matrix(MATRIX_PATH)) == set(implemented_ids())


def test_checklist_documental_estados():
    docs = {"checklist": {
        "Modelo de estado estacionario en versión de software solicitada por CENACE":
            {"cumple": True, "evidencia": "Oficio 123"},
    }}
    df = pd.DataFrame({"timestamp": ts(2)})
    r = get_test("CE-D-01").run(make_dataset(df), docs)
    assert r.status == TestStatus.PENDIENTE_DOCUMENTAL  # faltan ítems por declarar
    # todos declarados con evidencia → CUMPLE
    spec_items = get_test("CE-D-01").spec.limites["checklist"]
    todos = {"checklist": {i: {"cumple": True, "evidencia": "Oficio"} for i in spec_items}}
    r2 = get_test("CE-D-01").run(make_dataset(df), todos)
    assert r2.status == TestStatus.CUMPLE
    # uno en falso → NO_CUMPLE
    malo = {"checklist": {**todos["checklist"],
                          spec_items[0]: {"cumple": False, "evidencia": "n/a"}}}
    assert get_test("CE-D-01").run(make_dataset(df), malo).status == TestStatus.NO_CUMPLE


def test_rampa_variacion_carga():
    times = ts(300)
    p = [min(i * 0.1, 25.0) for i in range(300)]  # 6 MW/min
    df = pd.DataFrame({"timestamp": times, "active_power": p})
    r = get_test("CE-F-09").run(make_dataset(df), {"pn_mw": 100.0})
    assert r.status == TestStatus.CUMPLE  # 6 ≤ 10 MW/min
    p2 = [min(i * 0.5, 60.0) for i in range(300)]  # 30 MW/min
    r2 = get_test("CE-F-09").run(make_dataset(
        pd.DataFrame({"timestamp": times, "active_power": p2})), {"pn_mw": 100.0})
    assert r2.status == TestStatus.NO_CUMPLE


def test_capacidad_reactiva_ambos_sentidos():
    df = pd.DataFrame({"timestamp": ts(40),
                       "active_power": [50.0] * 40,
                       "reactive_power": [15.0] * 20 + [-15.0] * 20})  # FP≈0.958 ambos
    r = get_test("CE-V-02").run(make_dataset(df))
    assert r.status == TestStatus.CUMPLE
    # sin barrer adelanto → no evaluable ese check
    df2 = pd.DataFrame({"timestamp": ts(20), "active_power": [50.0] * 20,
                        "reactive_power": [15.0] * 20})
    r2 = get_test("CE-V-02").run(make_dataset(df2))
    adel = next(c for c in r2.pass_fail_details if c.nombre == "fp_en_adelanto")
    assert adel.cumple is None


def test_perfil_q_pmax():
    df = pd.DataFrame({"timestamp": ts(30), "active_power": [80.0] * 30,
                       "reactive_power": [35.0] * 15 + [-35.0] * 15})
    r = get_test("CE-V-03").run(make_dataset(df), {"pmax_mw": 100.0})
    assert r.status == TestStatus.CUMPLE  # ±0.35 ≥ ±0.33


def test_inyeccion_cd():
    df = pd.DataFrame({"timestamp": ts(20), "corriente_dc": [0.02] * 20})
    r = get_test("CE-Q-06").run(make_dataset(df), {"umbral_deteccion_a": 0.1})
    assert r.status == TestStatus.CUMPLE
    df2 = pd.DataFrame({"timestamp": ts(20), "corriente_dc": [0.5] * 20})
    r2 = get_test("CE-Q-06").run(make_dataset(df2), {"umbral_deteccion_a": 0.1})
    assert r2.status == TestStatus.NO_CUMPLE


def test_potencia_constante():
    f = [60.05] * 50
    df = pd.DataFrame({"timestamp": ts(50), "frequency": f,
                       "active_power": [80.0, 80.2] * 25})
    r = get_test("CE-F-07").run(make_dataset(df), {"tolerancia_mw": 1.0})
    assert r.status == TestStatus.CUMPLE
    r2 = get_test("CE-F-07").run(make_dataset(df), {"tolerancia_mw": 0.05})
    assert r2.status == TestStatus.NO_CUMPLE


def test_tension_frecuencia_cc():
    n = 100
    df = pd.DataFrame({"timestamp": ts(n),
                       "voltage": [230_000.0] * n, "frequency": [60.0] * n})
    r_v = get_test("CC-01").run(make_dataset(df), {"v_nominal_v": 230_000.0})
    assert r_v.status == TestStatus.CUMPLE
    r_f = get_test("CC-02").run(make_dataset(df))
    assert r_f.status == TestStatus.CUMPLE
    # fuera del rango temporal → NO_CUMPLE
    df2 = df.assign(frequency=[57.0] * n)
    assert get_test("CC-02").run(make_dataset(df2)).status == TestStatus.NO_CUMPLE


def test_calidad_cc():
    df = pd.DataFrame({"timestamp": ts(30), "pst": [0.7] * 30, "plt": [0.5] * 30,
                       "unbalance": [1.2] * 30})
    r = get_test("CC-08").run(make_dataset(df))
    assert r.status == TestStatus.CUMPLE
    nombres = {c.nombre for c in r.pass_fail_details}
    assert "tdd_corriente" in nombres  # remite a CE-Q-05, no dictamina en falso
