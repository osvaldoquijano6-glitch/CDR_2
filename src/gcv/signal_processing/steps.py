"""Detección de escalones y tiempos de respuesta t1/t2.

Definiciones operativas (los umbrales exigidos vienen de la matriz):
  * escalón: cambio del valor mediano entre las ventanas anterior y posterior
    a un instante, mayor que `min_delta`.
  * t1 (respuesta): tiempo desde el escalón hasta la primera entrada de la
    señal en la banda objetivo [target ± tol].
  * t2 (establecimiento): tiempo desde el escalón hasta el último instante en
    que la señal entra a la banda y ya no vuelve a salir.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Step:
    t: pd.Timestamp
    antes: float
    despues: float

    @property
    def delta(self) -> float:
        return self.despues - self.antes


def detect_steps(
    times: pd.Series,
    values: pd.Series,
    min_delta: float,
    window_s: float = 5.0,
    min_separation_s: float | None = None,
) -> list[Step]:
    """Escalones por diferencia de medianas antes/después de cada instante."""
    t = pd.to_datetime(times)
    v = pd.to_numeric(values, errors="coerce")
    s = pd.Series(v.values, index=t.values).dropna()
    if len(s) < 4:
        return []
    before = s.rolling(f"{window_s}s", min_periods=2).median()
    after = s[::-1].rolling(f"{window_s}s", min_periods=2).median()[::-1]
    jump = (after - before).abs()

    min_sep = pd.Timedelta(seconds=min_separation_s if min_separation_s is not None else window_s)
    steps: list[Step] = []
    candidates = jump[jump >= min_delta].sort_values(ascending=False)
    for ts in candidates.index:
        if any(abs(ts - st.t) < min_sep for st in steps):
            continue
        steps.append(Step(t=pd.Timestamp(ts), antes=float(before.loc[ts]), despues=float(after.loc[ts])))
    steps.sort(key=lambda st: st.t)
    return steps


def response_times(
    times: pd.Series,
    values: pd.Series,
    t_event: pd.Timestamp,
    target: float,
    tolerance: float,
) -> dict:
    """t1/t2 (s) de `values` hacia [target ± tolerance] a partir de t_event.

    t1/t2 = None si la señal nunca entra o no permanece en banda.
    """
    t = pd.to_datetime(times)
    v = pd.to_numeric(values, errors="coerce")
    s = pd.Series(v.values, index=t.values).dropna()
    post = s[s.index >= pd.Timestamp(t_event)]
    if post.empty:
        return {"t1_s": None, "t2_s": None, "en_banda_final": False}

    in_band = (post - target).abs() <= tolerance
    t1 = None
    if in_band.any():
        first = in_band.idxmax()  # primer True
        if in_band.loc[first]:
            t1 = float((pd.Timestamp(first) - pd.Timestamp(t_event)).total_seconds())

    t2 = None
    if in_band.iloc[-1]:
        # último instante fuera de banda; establecimiento en la muestra siguiente
        out = in_band[~in_band]
        if out.empty:
            t2 = t1
        else:
            after_last_out = in_band[in_band.index > out.index[-1]]
            if not after_last_out.empty:
                t2 = float((pd.Timestamp(after_last_out.index[0]) - pd.Timestamp(t_event)).total_seconds())
    return {"t1_s": t1, "t2_s": t2, "en_banda_final": bool(in_band.iloc[-1])}
