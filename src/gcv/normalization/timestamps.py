"""Parsing y validación de estampas de tiempo.

Hereda del proyecto legado (core/io.py) el mecanismo validado en campo:
  * normalización de AM/PM en español ("a. m." → "AM"),
  * cascada de formatos explícitos antes del parser genérico,
  * desambiguación day-first vs month-first eligiendo la interpretación con
    mejor score de monotonía (menos saltos negativos y menos brincos anómalos).

Además: epoch unix (s/ms), combinación de columnas fecha+hora separadas y
localización de zona horaria explícita (nunca inferida en silencio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

_AMPM_REPLACEMENTS = [
    ("a. m.", "AM"), ("p. m.", "PM"),
    ("a.m.", "AM"), ("p.m.", "PM"),
    ("a m", "AM"), ("p m", "PM"),
]

_AMPM_FORMATS = [
    "%d/%m/%Y %I:%M:%S.%f %p",
    "%m/%d/%Y %I:%M:%S.%f %p",
    "%d/%m/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S %p",
]
_DAYFIRST_FORMATS = [
    "%d/%m/%Y %H:%M:%S:%f", "%d/%m/%Y %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
]
_MONTHFIRST_FORMATS = [
    "%m/%d/%Y %H:%M:%S:%f", "%m/%d/%Y %H:%M:%S.%f", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
]
_ISO_FORMATS = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]


@dataclass(frozen=True)
class ParseReport:
    """Trazabilidad del parsing: qué estrategia ganó y con qué confianza."""

    estrategia: str  # "iso" | "ampm" | "dayfirst" | "monthfirst" | "epoch" | "generico" | "nativo"
    n_total: int
    n_validos: int
    ambiguo_dia_mes: bool  # True si ambas interpretaciones eran posibles
    confianza: float  # 0..1; <1 debe mostrarse advertencia en UI


def normalize_ampm(value: str) -> str:
    text = str(value).strip()
    for old, new in _AMPM_REPLACEMENTS:
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    return text


def _parse_with_formats(series: pd.Series, formats: list[str]) -> pd.Series:
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in formats:
        mask = parsed.isna()
        if not mask.any():
            break
        parsed.loc[mask] = pd.to_datetime(series.loc[mask], errors="coerce", format=fmt)
    return parsed


def _monotonicity_score(parsed: pd.Series) -> tuple[int, int, int, float]:
    """Score del legado: (válidos, -saltos_negativos, -brincos_grandes, -paso_mediano).

    Mayor es mejor. Un parseo día/mes incorrecto produce saltos hacia atrás y
    brincos de días entre muestras consecutivas.
    """
    valid = parsed.dropna()
    if valid.empty:
        return (-1, -1, -1, float("-inf"))
    diffs = valid.diff().dropna()
    negative = int((diffs < pd.Timedelta(0)).sum())
    if diffs.empty:
        return (len(valid), 0, 0, 0.0)
    positive = diffs[diffs > pd.Timedelta(0)]
    median = positive.median() if not positive.empty else pd.Timedelta(0)
    threshold = max(median * 12, pd.Timedelta(days=2)) if median > pd.Timedelta(0) else pd.Timedelta(days=2)
    large = int((diffs > threshold).sum())
    median_s = float(median.total_seconds()) if median > pd.Timedelta(0) else 0.0
    return (len(valid), -negative, -large, -median_s)


def _try_epoch(series: pd.Series) -> pd.Series | None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() < 0.9:
        return None
    med = numeric.dropna().median()
    # ventana plausible 2001–2065 en segundos o milisegundos
    if 1e9 <= med < 3e9:
        return pd.to_datetime(numeric, unit="s", errors="coerce")
    if 1e12 <= med < 3e12:
        return pd.to_datetime(numeric, unit="ms", errors="coerce")
    return None


def parse_datetime_series(series: pd.Series, dayfirst: bool | None = None) -> tuple[pd.Series, ParseReport]:
    """Parsea una serie de estampas de tiempo heterogéneas.

    `dayfirst`: declaración explícita del proyecto (fuente confiable). Si es
    None se desambigua por score de monotonía y se reporta la ambigüedad.
    """
    n = len(series)
    if pd.api.types.is_datetime64_any_dtype(series):
        return series, ParseReport("nativo", n, int(series.notna().sum()), False, 1.0)

    epoch = _try_epoch(series)
    if epoch is not None and epoch.notna().mean() >= 0.9:
        return epoch, ParseReport("epoch", n, int(epoch.notna().sum()), False, 1.0)

    normalized = series.astype(str).map(normalize_ampm)

    iso = _parse_with_formats(normalized, _ISO_FORMATS)
    if iso.notna().mean() >= 0.9:
        return iso, ParseReport("iso", n, int(iso.notna().sum()), False, 1.0)

    ampm = _parse_with_formats(normalized, _AMPM_FORMATS)
    if ampm.notna().mean() >= 0.9:
        return ampm, ParseReport("ampm", n, int(ampm.notna().sum()), False, 1.0)

    if dayfirst is True:
        parsed = _parse_with_formats(normalized, _DAYFIRST_FORMATS)
        if parsed.notna().any():
            return parsed, ParseReport("dayfirst", n, int(parsed.notna().sum()), False, 1.0)
    elif dayfirst is False:
        parsed = _parse_with_formats(normalized, _MONTHFIRST_FORMATS)
        if parsed.notna().any():
            return parsed, ParseReport("monthfirst", n, int(parsed.notna().sum()), False, 1.0)
    else:
        day = _parse_with_formats(normalized, _DAYFIRST_FORMATS)
        month = _parse_with_formats(normalized, _MONTHFIRST_FORMATS)
        day_score, month_score = _monotonicity_score(day), _monotonicity_score(month)
        if day.notna().any() or month.notna().any():
            both_possible = bool(day.notna().mean() >= 0.9 and month.notna().mean() >= 0.9)
            if day_score >= month_score:
                winner, name = day, "dayfirst"
            else:
                winner, name = month, "monthfirst"
            # confianza reducida si ambas interpretaciones eran parseables
            conf = 0.7 if both_possible and day_score[:3] == month_score[:3] else (0.9 if both_possible else 1.0)
            return winner, ParseReport(name, n, int(winner.notna().sum()), both_possible, conf)

    generic = pd.to_datetime(normalized, errors="coerce")
    if generic.isna().all():
        raise ValueError("No se pudo interpretar la columna de tiempo con ninguna estrategia.")
    return generic, ParseReport("generico", n, int(generic.notna().sum()), False, 0.8)


def combine_date_time(date_col: pd.Series, time_col: pd.Series, dayfirst: bool | None = None) -> tuple[pd.Series, ParseReport]:
    """Une columnas separadas de fecha y hora en un solo timestamp."""
    combined = date_col.astype(str).str.strip() + " " + time_col.astype(str).str.strip()
    return parse_datetime_series(combined, dayfirst=dayfirst)


def localize(series: pd.Series, tz: str | None) -> pd.Series:
    """Aplica zona horaria explícita. tz=None conserva naive (se registra en bitácora)."""
    if tz is None:
        return series
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_convert(tz)
    return series.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
