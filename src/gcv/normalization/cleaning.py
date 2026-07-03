"""Limpieza de datos con registro obligatorio en bitácora.

Principios:
  * Ninguna transformación silenciosa: cada paso escribe en CleaningLog.
  * Los outliers se marcan, no se eliminan, salvo política explícita.
  * Las correcciones manuales vienen de un archivo YAML/JSON del proyecto y
    también quedan en la bitácora (qué, por qué, cuántas filas).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from gcv.normalization.audit import CleaningLog
from gcv.normalization.sampling import flag_outliers_mad

_MODULO = "normalization.cleaning"


@dataclass
class ManualCorrections:
    """Correcciones declaradas por el usuario (config/correcciones.yaml).

    rename_columns:  {"columna_original": "nueva"}
    drop_time_ranges: [(inicio, fin)] — filas a excluir con motivo
    force_units:     {"columna": "kW"} — sobreescribe unidad detectada
    dayfirst:        interpretación declarada de fechas
    tz:              zona horaria de las estampas
    """

    rename_columns: dict[str, str] = field(default_factory=dict)
    drop_time_ranges: list[tuple[datetime, datetime]] = field(default_factory=list)
    force_units: dict[str, str] = field(default_factory=dict)
    dayfirst: bool | None = None
    tz: str | None = None
    motivo: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ManualCorrections":
        ranges = [
            (pd.to_datetime(r[0]).to_pydatetime(), pd.to_datetime(r[1]).to_pydatetime())
            for r in data.get("drop_time_ranges", [])
        ]
        return cls(
            rename_columns=dict(data.get("rename_columns", {})),
            drop_time_ranges=ranges,
            force_units=dict(data.get("force_units", {})),
            dayfirst=data.get("dayfirst"),
            tz=data.get("tz"),
            motivo=data.get("motivo"),
        )


def coerce_numeric(df: pd.DataFrame, cols: list[str], log: CleaningLog) -> pd.DataFrame:
    """Convierte columnas a numérico registrando cuántos valores se perdieron."""
    out = df.copy()
    for col in cols:
        before_nan = out[col].isna().sum()
        out[col] = pd.to_numeric(
            out[col].astype(str).str.replace(",", ".", regex=False).str.strip(),
            errors="coerce",
        )
        lost = int(out[col].isna().sum() - before_nan)
        if lost:
            log.add(_MODULO, "coercion_numerica",
                    f"Columna '{col}': {lost} valores no numéricos → NaN",
                    columna=col, valores_perdidos=lost)
    return out


def drop_invalid_time(df: pd.DataFrame, time_col: str, log: CleaningLog) -> pd.DataFrame:
    before = len(df)
    out = df.dropna(subset=[time_col])
    if len(out) != before:
        log.add(_MODULO, "drop_tiempo_invalido",
                f"{before - len(out)} filas sin estampa de tiempo válida eliminadas",
                filas_antes=before, filas_despues=len(out))
    return out


def sort_by_time(df: pd.DataFrame, time_col: str, log: CleaningLog) -> pd.DataFrame:
    if df[time_col].is_monotonic_increasing:
        return df
    out = df.sort_values(time_col, kind="stable").reset_index(drop=True)
    log.add(_MODULO, "reordenamiento_temporal",
            "Registros no monotónicos: dataset reordenado por estampa de tiempo",
            filas_antes=len(df), filas_despues=len(out))
    return out


def dedup_timestamps(df: pd.DataFrame, time_col: str, log: CleaningLog, keep: str = "first") -> pd.DataFrame:
    before = len(df)
    out = df.drop_duplicates(subset=[time_col], keep=keep).reset_index(drop=True)
    if len(out) != before:
        log.add(_MODULO, "dedup_timestamps",
                f"{before - len(out)} estampas duplicadas eliminadas (keep={keep})",
                filas_antes=before, filas_despues=len(out), keep=keep)
    return out


def mark_outliers(df: pd.DataFrame, cols: list[str], log: CleaningLog, threshold: float = 6.0) -> dict[str, int]:
    """Marca outliers por columna (no elimina). Devuelve conteos por columna."""
    counts: dict[str, int] = {}
    for col in cols:
        mask = flag_outliers_mad(df[col], threshold=threshold)
        n = int(mask.sum())
        counts[col] = n
        if n:
            log.add(_MODULO, "outliers_marcados",
                    f"Columna '{col}': {n} valores con z-robusto > {threshold} (marcados, no eliminados)",
                    columna=col, n_outliers=n, umbral=threshold)
    return counts


def apply_manual_corrections(
    df: pd.DataFrame,
    corrections: ManualCorrections,
    time_col: str,
    log: CleaningLog,
) -> pd.DataFrame:
    out = df
    if corrections.rename_columns:
        out = out.rename(columns=corrections.rename_columns)
        log.add(_MODULO, "rename_manual",
                f"Renombrado manual de columnas: {corrections.rename_columns}",
                motivo=corrections.motivo)
    for start, end in corrections.drop_time_ranges:
        before = len(out)
        mask = (out[time_col] >= pd.Timestamp(start)) & (out[time_col] <= pd.Timestamp(end))
        out = out[~mask].reset_index(drop=True)
        log.add(_MODULO, "drop_rango_manual",
                f"Exclusión manual {start} → {end}: {before - len(out)} filas",
                filas_antes=before, filas_despues=len(out),
                inicio=str(start), fin=str(end), motivo=corrections.motivo)
    return out
