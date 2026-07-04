"""Modelo droop primario por tramos y derivación de P_op.

Portado del proyecto legado (core/droop.py), validado en campo con pruebas
P3/P8/P9 del Anexo 5. Convención del protocolo CENACE heredado: pendiente
referida a P_ref,

    ΔP = -(P_ref / S) · (f - f_ref) / f_nom

activa solo fuera del umbral/banda muerta según la zona:
  * "alta":  f_ref = umbral de sobre-frecuencia; aplica si f > umbral (ΔP ≤ 0)
  * "baja":  f_ref = umbral de sub-frecuencia;  aplica si f < umbral (ΔP ≥ 0)
  * "ambas": f_ref = f_nom ± banda_muerta según el lado (CPF)

Los valores de umbral/estatismo/banda muerta NO viven aquí: vienen de la
matriz normativa (limites) o del protocolo (params).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DroopParams:
    p_ref_mw: float  # potencia de referencia del protocolo (típ. P nominal)
    estatismo: float  # S en pu (0.03, 0.05, 0.08)
    zona: str  # "alta" | "baja" | "ambas"
    f_nom_hz: float = 60.0
    umbral_hz: float | None = None  # requerido para zonas "alta"/"baja"
    banda_muerta_hz: float = 0.0  # usada en zona "ambas"
    p_min_mw: float = 0.0  # saturación inferior de la respuesta
    p_max_mw: float | None = None  # saturación superior (None = sin tope)

    def __post_init__(self):
        if self.zona not in ("alta", "baja", "ambas"):
            raise ValueError(f"Zona droop inválida: {self.zona}")
        if self.zona in ("alta", "baja") and self.umbral_hz is None:
            raise ValueError(f"Zona '{self.zona}' requiere umbral_hz")
        if self.estatismo <= 0:
            raise ValueError("El estatismo debe ser positivo")


def expected_power(freq: pd.Series, p_op: float, params: DroopParams) -> pd.Series:
    """Potencia esperada P_esp(f) según el modelo droop por tramos."""
    f = pd.to_numeric(freq, errors="coerce")
    slope = params.p_ref_mw / (params.estatismo * params.f_nom_hz)  # MW por Hz

    delta = pd.Series(0.0, index=f.index)
    if params.zona == "alta":
        active = f > params.umbral_hz
        delta[active] = -(f[active] - params.umbral_hz) * slope
    elif params.zona == "baja":
        active = f < params.umbral_hz
        delta[active] = -(f[active] - params.umbral_hz) * slope
    else:  # ambas
        hi = f > params.f_nom_hz + params.banda_muerta_hz
        lo = f < params.f_nom_hz - params.banda_muerta_hz
        delta[hi] = -(f[hi] - (params.f_nom_hz + params.banda_muerta_hz)) * slope
        delta[lo] = -(f[lo] - (params.f_nom_hz - params.banda_muerta_hz)) * slope

    expected = (p_op + delta).clip(lower=params.p_min_mw, upper=params.p_max_mw)
    return expected


def derive_p_op(
    times: pd.Series,
    freq: pd.Series,
    power: pd.Series,
    f_nom_hz: float = 60.0,
    stable_std_hz: float = 0.02,
    stable_window: int = 5,
) -> dict | None:
    """Estima P_op del estado estable previo al escalón (cascada del legado).

    1. Primer tramo estable (std de f < `stable_std_hz` en ventana móvil) dentro
       del primer 30 % del registro, con media a <0.15 Hz de f_nom.
    2. Puntos con f en f_nom ± 0.05 Hz en la primera mitad.
    3. Mediana de las primeras 100 muestras (marcado como método de respaldo).
    """
    f = pd.to_numeric(freq, errors="coerce")
    p = pd.to_numeric(power, errors="coerce")
    n = len(f)
    if n == 0 or p.dropna().empty:
        return None

    limit = max(50, int(n * 0.30))
    head_f = f.iloc[:limit]
    rolling_std = head_f.rolling(stable_window, min_periods=stable_window).std()
    stable = (rolling_std < stable_std_hz) & (head_f - f_nom_hz).abs().lt(0.15)
    if stable.any():
        idx = stable[stable].index
        p_seg = p.loc[idx].dropna()
        if len(p_seg) >= 3:
            return {"p_op_mw": float(p_seg.median()), "n_muestras": len(p_seg),
                    "metodo": "segmento_estable_pre_escalon"}

    half = n // 2
    near_nominal = (f.iloc[:half] - f_nom_hz).abs() <= 0.05
    if near_nominal.any():
        p_seg = p.iloc[:half][near_nominal].dropna()
        if len(p_seg) >= 3:
            return {"p_op_mw": float(p_seg.median()), "n_muestras": len(p_seg),
                    "metodo": "puntos_cercanos_f_nominal"}

    p_head = p.head(100).dropna()
    if p_head.empty:
        return None
    return {"p_op_mw": float(p_head.median()), "n_muestras": len(p_head),
            "metodo": "fallback_mediana_inicial"}


def response_error(
    power: pd.Series,
    expected: pd.Series,
    active_mask: pd.Series | None = None,
) -> dict:
    """Error P_medida − P_esperada; si se da `active_mask`, solo en zona activa."""
    p = pd.to_numeric(power, errors="coerce")
    err = (p - expected).dropna()
    if active_mask is not None:
        err = err[active_mask.reindex(err.index, fill_value=False)]
    if err.empty:
        return {"n": 0}
    return {
        "n": int(len(err)),
        "error_medio_mw": float(err.mean()),
        "error_abs_max_mw": float(err.abs().max()),
        "error_abs_p95_mw": float(err.abs().quantile(0.95)),
        "rmse_mw": float((err ** 2).mean() ** 0.5),
    }
