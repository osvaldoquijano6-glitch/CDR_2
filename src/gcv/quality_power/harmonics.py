"""Armónicos: percentiles por orden y de THD/TDD sobre agregaciones del analizador.

Trabaja sobre columnas canónicas `harmonic_voltage_<n>` / `harmonic_current_<n>`
(en % de la fundamental / de IL, como las entregan los analizadores IEC
61000-4-30) y `thd_voltage` / `thd_current` / `tdd`. El cálculo espectral desde
forma de onda (COMTRADE) se agrega cuando una prueba lo exija con fs suficiente.
"""

from __future__ import annotations

import re

import pandas as pd

_HARMONIC_COL_RE = re.compile(r"^harmonic_(voltage|current)_(\d+)$")
_INTERHARMONIC_COL_RE = re.compile(r"^interharmonic_(voltage|current)_(\d+)$")


def _columns(df: pd.DataFrame, kind: str, pattern: re.Pattern) -> dict[int, str]:
    out: dict[int, str] = {}
    for col in df.columns:
        m = pattern.match(str(col))
        if m and m.group(1) == kind:
            out[int(m.group(2))] = col
    return dict(sorted(out.items()))


def harmonic_columns(df: pd.DataFrame, kind: str) -> dict[int, str]:
    """{orden: nombre_columna} de armónicos presentes ('voltage' | 'current')."""
    return _columns(df, kind, _HARMONIC_COL_RE)


def interharmonic_columns(df: pd.DataFrame, kind: str) -> dict[int, str]:
    """{grupo: nombre_columna} de interarmónicos (grupos IEC 61000-4-7)."""
    return _columns(df, kind, _INTERHARMONIC_COL_RE)


def _percentiles(df: pd.DataFrame, cols: dict[int, str], percentile: float) -> dict[int, float]:
    q = percentile / 100.0
    return {
        order: float(pd.to_numeric(df[col], errors="coerce").quantile(q))
        for order, col in cols.items()
        if pd.to_numeric(df[col], errors="coerce").notna().any()
    }


def percentile_by_harmonic(df: pd.DataFrame, kind: str, percentile: float = 95.0) -> dict[int, float]:
    """Percentil de cada armónico individual presente en el dataset."""
    return _percentiles(df, harmonic_columns(df, kind), percentile)


def percentile_by_interharmonic(df: pd.DataFrame, kind: str,
                                percentile: float = 95.0) -> dict[int, float]:
    """Percentil de cada grupo interarmónico presente en el dataset."""
    return _percentiles(df, interharmonic_columns(df, kind), percentile)


def series_percentile(series: pd.Series, percentile: float = 95.0) -> float | None:
    v = pd.to_numeric(series, errors="coerce").dropna()
    return float(v.quantile(percentile / 100.0)) if not v.empty else None
