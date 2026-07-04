"""Derivadas temporales: ROCOF (df/dt) con ventana configurable.

Método: derivada muestra a muestra (Δf/Δt) suavizada con promedio móvil
temporal de ancho `window_s`. La ventana es un parámetro del protocolo o del
numeral (la matriz debe fijarla al validar CE-F-02); el valor usado queda en
el resultado para trazabilidad.
"""

from __future__ import annotations

import pandas as pd


def rocof_series(times: pd.Series, freq: pd.Series, window_s: float = 0.5) -> pd.Series:
    """Serie de df/dt en Hz/s alineada al índice de entrada."""
    t = pd.to_datetime(times)
    f = pd.to_numeric(freq, errors="coerce")
    dt = t.diff().dt.total_seconds()
    dfdt = f.diff() / dt
    dfdt = dfdt.mask(dt <= 0)  # timestamps duplicados o retrocesos: sin derivada
    if window_s and window_s > 0:
        smoothed = pd.Series(dfdt.values, index=t.values).rolling(
            f"{window_s}s", min_periods=1).mean()
        return pd.Series(smoothed.values, index=freq.index)
    return pd.Series(dfdt.values, index=freq.index)


def max_abs_rocof(times: pd.Series, freq: pd.Series, window_s: float = 0.5) -> dict | None:
    """Máximo |df/dt| y el instante en que ocurre."""
    serie = rocof_series(times, freq, window_s)
    absolute = serie.abs()
    if absolute.dropna().empty:
        return None
    idx = absolute.idxmax()
    return {
        "rocof_max_abs_hz_s": float(absolute.max()),
        "rocof_en": pd.to_datetime(times).loc[idx].to_pydatetime(),
        "signo": float(1.0 if serie.loc[idx] >= 0 else -1.0),
        "ventana_s": window_s,
    }
