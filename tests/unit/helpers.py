"""Constructores compartidos para tests del motor de reglas."""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.spec import EstadoNormativo, TestSpec
from gcv.models import InstallationKind
from gcv.normalization.audit import CleaningLog
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.normalization.sampling import analyze_sampling


def make_dataset(df: pd.DataFrame) -> NormalizedDataset:
    return NormalizedDataset(
        df=df, mappings=[], quality=analyze_sampling(df),
        log=CleaningLog(), source_sha256="deadbeef")


def make_spec(
    test_id: str,
    variables: list[str],
    limites: dict,
    fs_min: float | None = None,
    aplica_a: InstallationKind = InstallationKind.CENTRAL_ELECTRICA,
    parametros_heredados: dict | None = None,
) -> TestSpec:
    """Spec de laboratorio VALIDADA (solo para ejercitar el motor en tests)."""
    return TestSpec(
        id=test_id, nombre=f"{test_id} (fixture)", aplica_a=aplica_a,
        manual_referencia="INTER", numeral="T.E.S.T (ficticio)",
        fuente_documental="fixture de test",
        variables_requeridas=variables,
        fs_minima_sugerida_hz=fs_min,
        estado_normativo=EstadoNormativo.VALIDADO,
        parametros_heredados=parametros_heredados or {},
        limites=limites,
    )


def ts(n: int, freq: str = "1s", start: str = "2026-07-01 10:00:00") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq=freq)
