"""Tests FASE 3: CE-V-01, CC-04, CE-P-01 y calidad de potencia CE-Q-01..05."""

import pandas as pd
import pytest

from gcv.evaluation.capacidad_instalada import CapacidadInstaladaNeta
from gcv.evaluation.load_center.factor_potencia import FactorPotenciaCentroCarga
from gcv.evaluation.power_quality.armonicos import ArmonicosTension
from gcv.evaluation.power_quality.desbalance import Desbalance
from gcv.evaluation.power_quality.flicker import Flicker
from gcv.evaluation.power_quality.variaciones_rapidas import VariacionesRapidasTension
from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.result import TestStatus
from gcv.evaluation.voltage.rango_tension import RangoTension
from gcv.models import InstallationKind

from tests.unit.helpers import make_dataset, make_spec, ts


# ─── CE-V-01 Rango de tensión ────────────────────────────────────────────────
def test_rango_tension_cumple():
    df = pd.DataFrame({"timestamp": ts(10), "voltage": [230_500.0] * 10})
    spec = make_spec("CE-V-01", ["timestamp", "voltage"], limites={
        "bandas": [{"v_min_pu": 0.95, "v_max_pu": 1.05, "t_min_s": 5}]})
    result = RangoTension(spec).run(make_dataset(df), {"v_base_v": 230_000.0})
    assert result.status == TestStatus.CUMPLE


def test_rango_tension_sin_base_bloquea():
    df = pd.DataFrame({"timestamp": ts(10), "voltage": [230_500.0] * 10})
    spec = make_spec("CE-V-01", ["timestamp", "voltage"], limites={"bandas": []})
    result = RangoTension(spec).run(make_dataset(df), {})
    assert result.status == TestStatus.NO_EVALUABLE
    assert any("v_base_v" in w for w in result.warnings)


# ─── CC-04 Factor de potencia ────────────────────────────────────────────────
def test_fp_cumple_con_senal_directa():
    df = pd.DataFrame({"timestamp": ts(20), "power_factor": [0.97] * 19 + [0.90]})
    spec = make_spec("CC-04", ["timestamp", "power_factor"],
                     limites={"fp_min": 0.95, "cumplimiento_minimo_pct": 90},
                     aplica_a=InstallationKind.CENTRO_DE_CARGA)
    result = FactorPotenciaCentroCarga(spec).run(make_dataset(df))
    assert result.status == TestStatus.CUMPLE
    assert result.pass_fail_details[0].valor_medido == pytest.approx(95.0)


def test_fp_derivado_de_p_y_q():
    df = pd.DataFrame({"timestamp": ts(10),
                       "active_power": [40.0] * 10, "reactive_power": [10.0] * 10})
    spec = make_spec("CC-04", ["timestamp", "power_factor"],
                     limites={"fp_min": 0.95, "cumplimiento_minimo_pct": 95},
                     aplica_a=InstallationKind.CENTRO_DE_CARGA)
    result = FactorPotenciaCentroCarga(spec).run(make_dataset(df))
    # |P|/√(P²+Q²) = 40/41.23 = 0.970 ≥ 0.95 en todas las muestras
    assert result.status == TestStatus.CUMPLE


def test_fp_no_cumple():
    df = pd.DataFrame({"timestamp": ts(10), "power_factor": [0.90] * 10})
    spec = make_spec("CC-04", ["timestamp", "power_factor"],
                     limites={"fp_min": 0.95, "cumplimiento_minimo_pct": 95},
                     aplica_a=InstallationKind.CENTRO_DE_CARGA)
    result = FactorPotenciaCentroCarga(spec).run(make_dataset(df))
    assert result.status == TestStatus.NO_CUMPLE


# ─── CE-P-01 Capacidad instalada neta ────────────────────────────────────────
def test_capacidad_cumple():
    df = pd.DataFrame({"timestamp": ts(60, freq="1min"),
                       "active_power": [98.0] * 60})
    spec = make_spec("CE-P-01", ["timestamp", "active_power"],
                     limites={"ventana_sostenimiento_s": 600, "tolerancia_pct": 5})
    result = CapacidadInstaladaNeta(spec).run(
        make_dataset(df), {"capacidad_declarada_mw": 100.0})
    assert result.status == TestStatus.CUMPLE  # 98 ≥ 95


def test_capacidad_no_cumple():
    df = pd.DataFrame({"timestamp": ts(60, freq="1min"),
                       "active_power": [90.0] * 60})
    spec = make_spec("CE-P-01", ["timestamp", "active_power"],
                     limites={"ventana_sostenimiento_s": 600, "tolerancia_pct": 5})
    result = CapacidadInstaladaNeta(spec).run(
        make_dataset(df), {"capacidad_declarada_mw": 100.0})
    assert result.status == TestStatus.NO_CUMPLE


# ─── CE-Q-04 Armónicos de tensión ────────────────────────────────────────────
def test_armonicos_cumple_y_reporta_faltantes():
    df = pd.DataFrame({
        "timestamp": ts(20),
        "thd_voltage": [2.5] * 20,
        "harmonic_voltage_5": [1.5] * 20,
    })
    spec = make_spec("CE-Q-04", ["timestamp", "thd_v"], limites={
        "percentil": 95, "thd_max_pct": 5.0, "armonicos": {5: 3.0, 7: 2.0}})
    result = ArmonicosTension(spec).run(make_dataset(df))
    # THD y h5 cumplen; h7 exigido sin medición → excluido con advertencia
    assert result.status == TestStatus.CUMPLE
    checks = {c.nombre: c for c in result.pass_fail_details}
    assert checks["thd_p95"].cumple is True
    assert checks["h5_p95"].cumple is True
    assert checks["h7_p95"].cumple is None
    assert any("no evaluables" in w for w in result.warnings)


def test_armonicos_no_cumple():
    df = pd.DataFrame({"timestamp": ts(20), "thd_voltage": [8.0] * 20})
    spec = make_spec("CE-Q-04", ["timestamp", "thd_v"],
                     limites={"thd_max_pct": 5.0})
    result = ArmonicosTension(spec).run(make_dataset(df))
    assert result.status == TestStatus.NO_CUMPLE


# ─── CE-Q-02 Flicker ─────────────────────────────────────────────────────────
def test_flicker_cumple():
    df = pd.DataFrame({"timestamp": ts(20), "pst": [0.7] * 20, "plt": [0.5] * 20})
    spec = make_spec("CE-Q-02", ["timestamp", "pst"],
                     limites={"pst_max": 1.0, "plt_max": 0.8, "percentil": 95})
    result = Flicker(spec).run(make_dataset(df))
    assert result.status == TestStatus.CUMPLE


def test_flicker_sin_senal_bloquea():
    df = pd.DataFrame({"timestamp": ts(5), "voltage": [230.0] * 5})
    spec = make_spec("CE-Q-02", ["timestamp", "pst"], limites={"pst_max": 1.0})
    result = Flicker(spec).run(make_dataset(df))
    assert result.status == TestStatus.NO_EVALUABLE


# ─── CE-Q-01 Desbalance ──────────────────────────────────────────────────────
def test_desbalance_nema_cumple():
    df = pd.DataFrame({
        "timestamp": ts(10),
        "voltage_a": [230.0] * 10, "voltage_b": [232.0] * 10, "voltage_c": [228.0] * 10})
    spec = make_spec("CE-Q-01", ["timestamp"], limites={
        "metodo": "nema", "limite_pct": 3.0, "percentil": 95})
    result = Desbalance(spec).run(make_dataset(df))
    assert result.status == TestStatus.CUMPLE
    assert result.pass_fail_details[0].valor_medido == pytest.approx(100 * 2 / 230, rel=1e-4)


def test_desbalance_metodo_no_calculable():
    df = pd.DataFrame({"timestamp": ts(10), "voltage": [230.0] * 10})
    spec = make_spec("CE-Q-01", ["timestamp"], limites={
        "metodo": "iec_ll", "limite_pct": 2.0})
    result = Desbalance(spec).run(make_dataset(df))
    assert result.status == TestStatus.NO_EVALUABLE


# ─── CE-Q-03 Variaciones rápidas ─────────────────────────────────────────────
def test_rvc_no_cumple_con_evento():
    df = pd.DataFrame({
        "timestamp": ts(120),
        "voltage": [230.0] * 60 + [200.0, 200.0] + [230.0] * 58})
    spec = make_spec("CE-Q-03", ["timestamp", "voltage"], limites={
        "limite_pct": 5.0, "max_eventos": 0, "ventana_estable_s": 30})
    result = VariacionesRapidasTension(spec).run(make_dataset(df), {"v_nominal_v": 230.0})
    assert result.status == TestStatus.NO_CUMPLE


def test_rvc_cumple_sin_eventos():
    df = pd.DataFrame({"timestamp": ts(60), "voltage": [230.0] * 60})
    spec = make_spec("CE-Q-03", ["timestamp", "voltage"], limites={
        "limite_pct": 5.0, "max_eventos": 0})
    result = VariacionesRapidasTension(spec).run(make_dataset(df), {"v_nominal_v": 230.0})
    assert result.status == TestStatus.CUMPLE


# ─── Integración con la matriz real ──────────────────────────────────────────
def test_todas_las_implementadas_instancian_con_matriz_real():
    for tid in implemented_ids():
        prueba = get_test(tid)
        assert prueba.spec.id == tid


def test_matriz_real_sigue_sin_veredicto():
    """Con la matriz real (criterios pendientes) el droop calcula pero no dictamina."""
    df = pd.DataFrame({
        "timestamp": ts(160),
        "frequency": [60.0] * 80 + [60.8] * 80,
        "active_power": [80.0] * 80 + [60.0] * 80})
    prueba = get_test("CE-F-03")
    result = prueba.run(make_dataset(df), {"estatismo": 0.05, "p_ref_mw": 100.0})
    assert result.status == TestStatus.NO_EVALUABLE
    assert result.estado_normativo == "HEREDADO_PROTOCOLO_SIN_CITA"
    assert any(m.nombre == "p_op" for m in result.measured_values)
