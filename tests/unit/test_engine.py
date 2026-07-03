"""Tests del motor de reglas: matriz real, aplicabilidad y ciclo de BaseTest."""

import pandas as pd
import pytest

from gcv.config.settings import MATRIX_PATH
from gcv.evaluation.applicability import applicable_tests
from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.result import TestStatus
from gcv.evaluation.spec import EstadoNormativo, TestSpec, load_matrix
from gcv.models import Category, Installation, InstallationKind, Technology
from gcv.normalization.audit import CleaningLog
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.normalization.sampling import analyze_sampling


# ─── Matriz normativa real ────────────────────────────────────────────────────
def test_matriz_real_carga_completa():
    matrix = load_matrix(MATRIX_PATH)
    assert len(matrix) == 35
    assert "CE-F-01" in matrix and "CC-10" in matrix
    # FASE 1: ningún criterio puede estar VALIDADO sin fuente documental
    for spec in matrix.values():
        if spec.estado_normativo == EstadoNormativo.VALIDADO:
            assert spec.fuente_documental, f"{spec.id} VALIDADO sin fuente documental"


def test_aplicabilidad_por_tipo_instalacion():
    matrix = load_matrix(MATRIX_PATH)
    central = Installation(nombre="CE X", kind=InstallationKind.CENTRAL_ELECTRICA,
                           tech=Technology.ASINCRONA, category=Category.C)
    decisiones = {d.spec.id: d for d in applicable_tests(matrix, central)}
    assert decisiones["CE-F-01"].aplica
    assert not decisiones["CC-01"].aplica  # prueba de Centro de Carga
    # prueba sin categorías definidas → incluida pero dudosa
    assert decisiones["CE-F-06"].aplica and decisiones["CE-F-06"].dudosa


# ─── Ciclo del motor ─────────────────────────────────────────────────────────
def _dataset(df: pd.DataFrame) -> NormalizedDataset:
    return NormalizedDataset(
        df=df, mappings=[], quality=analyze_sampling(df), log=CleaningLog(),
        source_sha256="abc123")


def _freq_df(freqs: list[float], power: float = 50.0) -> pd.DataFrame:
    times = pd.date_range("2026-07-01 10:00:00", periods=len(freqs), freq="1s")
    return pd.DataFrame({"timestamp": times, "frequency": freqs,
                         "active_power": [power] * len(freqs)})


def _spec_validada(**limites) -> TestSpec:
    """Spec de laboratorio con criterio validado (solo para probar el motor)."""
    return TestSpec(
        id="CE-F-01", nombre="Rango de frecuencia",
        aplica_a=InstallationKind.CENTRAL_ELECTRICA,
        manual_referencia="INTER", numeral="X.Y.Z (ficticio de prueba)",
        fuente_documental="fixture de test",
        variables_requeridas=["timestamp", "frequency", "active_power"],
        fs_minima_sugerida_hz=1,
        estado_normativo=EstadoNormativo.VALIDADO,
        limites=limites,
    )


def test_sin_criterio_validado_no_hay_veredicto():
    prueba = get_test("CE-F-01")  # matriz real: PENDIENTE_VALIDACION_NORMATIVA
    result = prueba.run(_dataset(_freq_df([60.0, 60.01, 59.99, 60.0])))
    assert result.status == TestStatus.NO_EVALUABLE
    assert any("no validado" in w for w in result.warnings)
    # las mediciones sí se reportan
    assert any(m.nombre == "f_max" for m in result.measured_values)


def test_cumple_con_spec_validada():
    from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia

    spec = _spec_validada(bandas=[{"f_min": 59.5, "f_max": 60.5, "t_min_s": 2}])
    result = RangoFrecuencia(spec).run(_dataset(_freq_df([60.0, 60.01, 59.99, 60.0])))
    assert result.status == TestStatus.CUMPLE
    assert result.pass_fail_details[0].cumple is True
    assert result.pass_fail_details[0].referencia.numeral == "X.Y.Z (ficticio de prueba)"
    assert "conforme a INTER" in result.conclusion
    assert result.fuentes_sha256 == ["abc123"]


def test_no_cumple_permanencia_insuficiente():
    from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia

    # solo 1 muestra dentro de la banda alta → permanencia < 5 s exigidos
    spec = _spec_validada(bandas=[{"f_min": 60.5, "f_max": 61.5, "t_min_s": 5}])
    result = RangoFrecuencia(spec).run(_dataset(_freq_df([60.0, 61.0, 60.0, 60.0])))
    assert result.status == TestStatus.NO_CUMPLE
    assert "incumplimiento" in result.conclusion.lower()


def test_senal_faltante_bloquea():
    from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia

    spec = _spec_validada(bandas=[{"f_min": 59.5, "f_max": 60.5}])
    df = _freq_df([60.0, 60.0]).drop(columns=["frequency"])
    result = RangoFrecuencia(spec).run(_dataset(df))
    assert result.status == TestStatus.NO_EVALUABLE
    assert any("frequency" in w for w in result.warnings)


def test_fs_insuficiente_bloquea():
    from gcv.evaluation.frequency.rango_frecuencia import RangoFrecuencia

    spec = _spec_validada(bandas=[{"f_min": 59.5, "f_max": 60.5}])
    times = pd.date_range("2026-07-01", periods=4, freq="10s")  # 0.1 Hz < 1 Hz
    df = pd.DataFrame({"timestamp": times, "frequency": [60.0] * 4,
                       "active_power": [50.0] * 4})
    result = RangoFrecuencia(spec).run(_dataset(df))
    assert result.status == TestStatus.NO_EVALUABLE
    assert any("muestreo insuficiente" in w for w in result.warnings)


def test_registry():
    assert "CE-F-01" in implemented_ids()
    with pytest.raises(KeyError, match="matriz"):
        get_test("NO-EXISTE")
    with pytest.raises(KeyError, match="no tiene implementación"):
        get_test("CC-10")
