"""Variaciones rápidas de tensión (RVC) sobre series RMS.

Método operativo: la tensión de estado estable se estima con mediana móvil
temporal; un evento RVC es una desviación de la muestra respecto al estado
estable previo mayor que el umbral (% de V nominal). Eventos consecutivos se
agrupan. La definición y el umbral exigidos deben confirmarse al validar el
numeral (CE-Q-03).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RvcEvent:
    inicio: pd.Timestamp
    fin: pd.Timestamp
    delta_v_pct_max: float  # máx |ΔV|/Vnom·100 durante el evento


def detect_rvc(
    times: pd.Series,
    voltage: pd.Series,
    v_nominal: float,
    threshold_pct: float,
    steady_window_s: float = 60.0,
) -> list[RvcEvent]:
    if v_nominal <= 0:
        raise ValueError("v_nominal debe ser positiva")
    t = pd.to_datetime(times)
    v = pd.to_numeric(voltage, errors="coerce")
    s = pd.Series(v.values, index=t.values).dropna()
    if len(s) < 3:
        return []

    steady = s.rolling(f"{int(steady_window_s)}s", min_periods=1).median().shift(1)
    dev_pct = (s - steady).abs() / v_nominal * 100.0
    mask = dev_pct > threshold_pct

    events: list[RvcEvent] = []
    groups = (mask != mask.shift()).cumsum()
    for _, idx in mask[mask].groupby(groups[mask]).groups.items():
        events.append(RvcEvent(
            inicio=pd.Timestamp(idx[0]),
            fin=pd.Timestamp(idx[-1]),
            delta_v_pct_max=float(dev_pct.loc[list(idx)].max()),
        ))
    return events
