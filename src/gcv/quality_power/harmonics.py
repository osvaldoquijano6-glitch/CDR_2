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


def harmonic_columns(df: pd.DataFrame, kind: str) -> dict[int, str]:
    """{orden: nombre_columna} de armónicos presentes ('voltage' | 'current')."""
    out: dict[int, str] = {}
    for col in df.columns:
        m = _HARMONIC_COL_RE.match(str(col))
        if m and m.group(1) == kind:
            out[int(m.group(2))] = col
    return dict(sorted(out.items()))


def percentile_by_harmonic(df: pd.DataFrame, kind: str, percentile: float = 95.0) -> dict[int, float]:
    """Percentil de cada armónico individual presente en el dataset."""
    q = percentile / 100.0
    return {
        order: float(pd.to_numeric(df[col], errors="coerce").quantile(q))
        for order, col in harmonic_columns(df, kind).items()
        if pd.to_numeric(df[col], errors="coerce").notna().any()
    }


def series_percentile(series: pd.Series, percentile: float = 95.0) -> float | None:
    v = pd.to_numeric(series, errors="coerce").dropna()
    return float(v.quantile(percentile / 100.0)) if not v.empty else None
