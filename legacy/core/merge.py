"""
core/merge.py — Empate de series temporales de distintos archivos.

Consolida el patrón repetido en P3, P8 y P9:
  - Cargar frecuencia (CSV) y potencia (Excel/GEN) por separado
  - Alinear fechas si los archivos son de días distintos
  - Cruzar por tiempo más cercano (merge_asof)
  - Simplificar la serie resultante para graficación eficiente
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.io import (
    _find_header,
    _parse_datetime_series,
    detect_columns,
    detect_time_column,
    load_table,
    prepare_dataframe,
)


MERGE_TOLERANCE_SECONDS = 1.0
POWER_SCALE_THRESHOLD = 100.0   # Si el p95 supera esto, se divide entre 1000 (kW → MW)


# ─── Carga de fuentes ─────────────────────────────────────────────────────────
def load_frequency_df(path: Path) -> pd.DataFrame:
    """Carga un archivo de frecuencia; devuelve DataFrame con columnas 'time' y 'frequency'."""
    raw = load_table(path)
    cols = detect_columns(raw.columns)
    if cols.frequency is None:
        raise ValueError(f"No se encontró la columna de frecuencia. Columnas disponibles: {list(raw.columns)}")
    time_col = cols.time.strip()
    freq_col = cols.frequency.strip()
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df[time_col] = _parse_datetime_series(df[time_col])
    df = (
        df[[time_col, freq_col]].copy()
        .dropna(subset=[time_col])
        .sort_values(time_col)
        .drop_duplicates(subset=[time_col])
        .reset_index(drop=True)
    )
    if df.empty:
        raise ValueError(f"Sin registros válidos de tiempo/frecuencia en {path.name}.")
    return df.rename(columns={time_col: "time", freq_col: "frequency"})


def load_power_df(path: Path) -> pd.DataFrame:
    """Carga un archivo de generación; devuelve DataFrame con columnas 'time' y 'active_power'.
    Convierte automáticamente de kW a MW si los valores son >100 kW (p95)."""
    raw = load_table(path)
    headers = [str(c).strip() for c in raw.columns]
    time_col = detect_time_column(headers)
    power_col = _find_header(headers, ("active", "power")) or _find_header(headers, ("potencia", "activa"))
    if power_col is None:
        raise ValueError(f"No se encontró la potencia activa. Columnas disponibles: {list(raw.columns)}")
    df = raw.copy()
    df.columns = headers
    df[time_col] = _parse_datetime_series(df[time_col])
    df[power_col] = pd.to_numeric(df[power_col], errors="coerce")
    df = (
        df[[time_col, power_col]].copy()
        .dropna(subset=[time_col])
        .sort_values(time_col)
        .drop_duplicates(subset=[time_col])
        .reset_index(drop=True)
    )
    df = df.rename(columns={time_col: "time", power_col: "active_power"})
    if df.empty:
        raise ValueError(f"Sin registros válidos de tiempo/potencia activa en {path.name}.")
    if df["active_power"].abs().quantile(0.95) > POWER_SCALE_THRESHOLD:
        df["active_power"] = df["active_power"] / 1000.0
    return df


# ─── Alineación de fechas ─────────────────────────────────────────────────────
def align_dates(freq_df: pd.DataFrame, power_df: pd.DataFrame) -> pd.DataFrame:
    """Si los archivos de frecuencia y potencia tienen fechas distintas (mismo horario, distinto día),
    desplaza la frecuencia al día de la potencia para que el merge funcione correctamente."""
    aligned = freq_df.copy()
    freq_start = aligned["time"].min()
    freq_end = aligned["time"].max()
    pw_start = power_df["time"].min()
    pw_end = power_df["time"].max()

    if any(pd.isna(v) for v in [freq_start, freq_end, pw_start, pw_end]):
        return aligned

    overlaps = not (freq_end < pw_start or freq_start > pw_end)
    if overlaps:
        return aligned

    day_delta = pw_start.normalize() - freq_start.normalize()
    if day_delta == pd.Timedelta(0):
        return aligned

    shifted = aligned.copy()
    shifted["time"] = shifted["time"] + day_delta
    shifted_overlaps = not (shifted["time"].max() < pw_start or shifted["time"].min() > pw_end)
    return shifted if shifted_overlaps else aligned


# ─── Empate temporal ───────────────────────────────────────────────────────────
def merge_time_series(
    freq_df: pd.DataFrame,
    power_df: pd.DataFrame,
    tolerance_s: float = MERGE_TOLERANCE_SECONDS,
) -> pd.DataFrame:
    """Cruza frecuencia y potencia por tiempo más cercano (merge_asof).
    Elimina filas con valores nulos o cero en cualquiera de las dos series."""
    freq_aligned = align_dates(freq_df, power_df)
    # Convertir a numérico por si vienen como strings
    freq_aligned["frequency"] = pd.to_numeric(freq_aligned["frequency"], errors="coerce")
    power_df = power_df.copy()
    power_df["active_power"] = pd.to_numeric(power_df["active_power"], errors="coerce")
    merged = pd.merge_asof(
        freq_aligned.sort_values("time"),
        power_df.sort_values("time"),
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=tolerance_s),
    )
    merged = merged.dropna(subset=["frequency", "active_power"]).copy()
    merged = merged.loc[
        ~(merged["frequency"].fillna(0).abs() < 1e-12)
        & ~(merged["active_power"].fillna(0).abs() < 1e-12)
    ].copy()
    if merged.empty:
        raise ValueError(
            "Sin registros válidos tras cruzar frecuencia y potencia. "
            "Verifica que los archivos sean del mismo período."
        )
    return merged.reset_index(drop=True)


# ─── Simplificación para graficación ─────────────────────────────────────────
def simplify_for_plot(
    df: pd.DataFrame,
    time_col: str = "time",
    freq_col: str = "frequency",
    power_col: str = "active_power",
    threshold: int = 800,
) -> pd.DataFrame:
    """Reduce el número de puntos manteniendo los cambios significativos.
    Solo actúa si el DataFrame tiene más de `threshold` filas."""
    df = df.copy().reset_index(drop=True)
    if len(df) <= threshold:
        return df

    freq_range = max(float(df[freq_col].max() - df[freq_col].min()), 1e-6)
    power_range = max(float(df[power_col].max() - df[power_col].min()), 1e-6)
    freq_delta = df[freq_col].diff().abs().fillna(0.0)
    power_delta = df[power_col].diff().abs().fillna(0.0)

    freq_tol = max(float(freq_delta.quantile(0.87)), freq_range * 0.01)
    power_tol = max(float(power_delta.quantile(0.87)), power_range * 0.01)
    significant = (freq_delta >= freq_tol) | (power_delta >= power_tol)

    keep = np.zeros(len(df), dtype=bool)
    keep[0] = True
    keep[-1] = True

    for idx in np.flatnonzero(significant.to_numpy()):
        left = max(0, idx - 2)
        right = min(len(df), idx + 3)
        keep[left:right] = True

    step = max(18, len(df) // 180)
    keep[::step] = True

    return df.loc[keep].copy().reset_index(drop=True)


# ─── Inferencia de drawstyle ──────────────────────────────────────────────────
def infer_drawstyle(freq_series: pd.Series) -> str:
    """Devuelve 'steps-post' si la serie de frecuencia tiene pocos valores únicos (señal discreta)."""
    unique_ratio = freq_series.nunique() / max(len(freq_series), 1)
    if unique_ratio < 0.20 or freq_series.nunique() <= 80:
        return "steps-post"
    return "default"
