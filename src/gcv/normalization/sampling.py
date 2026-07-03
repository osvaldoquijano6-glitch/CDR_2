"""Análisis de muestreo: frecuencia efectiva, huecos, duplicados, monotonía."""

from __future__ import annotations

import pandas as pd

from gcv.models import DataQualityReport, GapInfo


def analyze_sampling(
    df: pd.DataFrame,
    time_col: str = "timestamp",
    gap_factor: float = 3.0,
    max_gaps_reported: int = 100,
) -> DataQualityReport:
    """Caracteriza el eje temporal y la completitud de un dataset normalizado.

    Un "hueco" es un Δt mayor que `gap_factor` veces el periodo mediano.
    No modifica los datos: solo reporta (la corrección es decisión aparte y
    queda en la bitácora si se aplica).
    """
    report = DataQualityReport(n_filas=len(df))
    if df.empty or time_col not in df.columns:
        return report

    times = pd.to_datetime(df[time_col], errors="coerce").dropna()
    if times.empty:
        return report

    report.inicio = times.min().to_pydatetime()
    report.fin = times.max().to_pydatetime()
    report.duracion_s = float((times.max() - times.min()).total_seconds())
    report.timestamps_duplicados = int(times.duplicated().sum())

    diffs = times.diff().dropna()
    report.saltos_no_monotonicos = int((diffs < pd.Timedelta(0)).sum())

    positive = diffs[diffs > pd.Timedelta(0)]
    if not positive.empty:
        median = positive.median()
        median_s = float(median.total_seconds())
        report.periodo_mediano_s = median_s
        report.fs_detectada_hz = (1.0 / median_s) if median_s > 0 else None

        threshold = median * gap_factor
        gap_mask = diffs > threshold
        for ts, delta in diffs[gap_mask].head(max_gaps_reported).items():
            end = times.loc[ts] if ts in times.index else None
            start = end - delta if end is not None else None
            if start is None or end is None:
                continue
            report.huecos.append(
                GapInfo(
                    inicio=start.to_pydatetime(),
                    fin=end.to_pydatetime(),
                    duracion_s=float(delta.total_seconds()),
                    muestras_faltantes_estimadas=max(int(delta / median) - 1, 1),
                )
            )

    value_cols = [c for c in df.columns if c != time_col]
    for col in value_cols:
        report.nan_por_columna[col] = int(pd.to_numeric(df[col], errors="coerce").isna().sum())

    return report


def flag_outliers_mad(series: pd.Series, threshold: float = 6.0) -> pd.Series:
    """Marca outliers con z-score robusto (mediana/MAD). Devuelve máscara booleana.

    Solo señala: la decisión de excluir es del usuario o de una política
    explícita, y siempre pasa por la bitácora.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    median = numeric.median()
    mad = (numeric - median).abs().median()
    if pd.isna(mad) or mad == 0:
        return pd.Series(False, index=series.index)
    robust_z = 0.6745 * (numeric - median).abs() / mad
    return robust_z > threshold
