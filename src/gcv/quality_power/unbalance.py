"""Desbalance de tensión: métodos NEMA e IEC (aproximación por magnitudes).

El método exigido debe fijarse al validar el numeral (CE-Q-01):
  * nema:    100 · máx|Vx − V̄| / V̄ sobre las tres magnitudes.
  * iec_ll:  aproximación de V2/V1 desde magnitudes línea-línea
             (CIGRÉ/IEC 61000-4-30 anexo):
             β = (Vab⁴+Vbc⁴+Vca⁴)/(Vab²+Vbc²+Vca²)² ;
             u2 = 100·sqrt((1−sqrt(3−6β))/(1+sqrt(3−6β))).
El método exacto por componentes simétricas requiere fasores (COMTRADE/PMU).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def unbalance_nema(va: pd.Series, vb: pd.Series, vc: pd.Series) -> pd.Series:
    """% de desbalance NEMA por muestra."""
    df = pd.DataFrame({
        "a": pd.to_numeric(va, errors="coerce"),
        "b": pd.to_numeric(vb, errors="coerce"),
        "c": pd.to_numeric(vc, errors="coerce"),
    })
    mean = df.mean(axis=1)
    max_dev = (df.sub(mean, axis=0)).abs().max(axis=1)
    return 100.0 * max_dev / mean


def unbalance_iec_ll(vab: pd.Series, vbc: pd.Series, vca: pd.Series) -> pd.Series:
    """% u2 aproximado desde magnitudes línea-línea."""
    ab = pd.to_numeric(vab, errors="coerce")
    bc = pd.to_numeric(vbc, errors="coerce")
    ca = pd.to_numeric(vca, errors="coerce")
    sq = ab**2 + bc**2 + ca**2
    beta = (ab**4 + bc**4 + ca**4) / sq**2
    inner = np.sqrt(np.clip(3.0 - 6.0 * beta, 0.0, None))
    ratio = (1.0 - inner) / (1.0 + inner)
    return 100.0 * np.sqrt(np.clip(ratio, 0.0, None))
