"""Detección de eventos operativos: desconexión/disparo y pérdida de señal."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Episode:
    inicio: pd.Timestamp
    fin: pd.Timestamp
    duracion_s: float
    muestras: int


def _group_episodes(t: pd.Series, mask: pd.Series, min_duration_s: float) -> list[Episode]:
    episodes: list[Episode] = []
    if not mask.any():
        return episodes
    groups = (mask != mask.shift()).cumsum()
    for _, idx in mask[mask].groupby(groups[mask]).groups.items():
        start, end = t.loc[idx[0]], t.loc[idx[-1]]
        dur = float((end - start).total_seconds())
        if dur >= min_duration_s or len(idx) >= 2:
            episodes.append(Episode(start, end, dur, len(idx)))
    return episodes


def detect_disconnection(
    times: pd.Series,
    power: pd.Series,
    threshold: float,
    min_duration_s: float = 0.0,
) -> list[Episode]:
    """Episodios con potencia bajo `threshold` (desconexión o disparo).

    El umbral debe venir del protocolo o de la matriz (p. ej. 5 % de Pn);
    esta función no asume ninguno.
    """
    t = pd.to_datetime(times)
    p = pd.to_numeric(power, errors="coerce")
    return _group_episodes(t, (p < threshold) & p.notna(), min_duration_s)


def detect_signal_loss(
    times: pd.Series,
    values: pd.Series,
    min_duration_s: float = 0.0,
) -> list[Episode]:
    """Episodios de NaN consecutivos (pérdida de medición/comunicación)."""
    t = pd.to_datetime(times)
    v = pd.to_numeric(values, errors="coerce")
    return _group_episodes(t, v.isna(), min_duration_s)
