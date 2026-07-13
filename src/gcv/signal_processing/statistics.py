"""Estadísticos de series temporales: permanencia en banda, básicos, sostenidos.

Funciones puras sin criterio normativo (capa 4): los límites contra los que se
comparan estos números viven en la matriz normativa y los aplica `evaluation`.
"""

from __future__ import annotations

import pandas as pd


def sample_dt(times: pd.Series) -> pd.Series:
    """Δt (s) asignado a cada muestra: distancia a la siguiente; última = mediana."""
    t = pd.to_datetime(times)
    dt = t.diff().shift(-1).dt.total_seconds()
    if dt.notna().any():
        return dt.fillna(dt.median())
    return dt.fillna(0.0)


def time_in_bands(
    times: pd.Series,
    values: pd.Series,
    bands: list[tuple[float, float]],
) -> list[dict]:
    """Segundos acumulados y muestras dentro de cada banda [mín, máx] (inclusive)."""
    dt = sample_dt(times)
    v = pd.to_numeric(values, errors="coerce")
    out = []
    for vmin, vmax in bands:
        mask = (v >= vmin) & (v <= vmax)
        out.append({
            "min": vmin,
            "max": vmax,
            "permanencia_s": float(dt[mask].sum()),
            "muestras": int(mask.sum()),
        })
    return out


def basic_stats(values: pd.Series) -> dict[str, float]:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return {}
    return {
        "min": float(v.min()),
        "max": float(v.max()),
        "media": float(v.mean()),
        "p05": float(v.quantile(0.05)),
        "p95": float(v.quantile(0.95)),
        "p99": float(v.quantile(0.99)),
    }


def sustained_max(times: pd.Series, values: pd.Series, window_s: float) -> dict | None:
    """Máximo sostenido: mayor promedio móvil de `values` sobre ventana temporal.

    Base del cálculo de capacidad instalada neta (CE-P-01): la potencia máxima
    demostrada es la sostenida durante la ventana exigida, no un pico puntual.
    """
    v = pd.to_numeric(values, errors="coerce")
    t = pd.to_datetime(times)
    if v.dropna().empty or len(v) < 2:
        return None
    s = pd.Series(v.values, index=t.values)
    rolled = s.rolling(f"{int(window_s)}s", min_periods=2).mean()
    if rolled.dropna().empty:
        return None
    idx = rolled.idxmax()
    return {
        "valor": float(rolled.max()),
        "fin_ventana": pd.Timestamp(idx).to_pydatetime(),
        "ventana_s": window_s,
    }
