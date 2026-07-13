"""Resolutor de límites de distorsión de corriente (Tablas 2.8.A/B/C, CdR 2.0).

Selecciona la tabla por nivel de tensión y la fila por relación Icc/IL, y
entrega el límite por armónica: impares por rango de orden; pares = 25 % del
impar del mismo rango. Fuente de datos: normative/limites/tablas_cdr2.yaml.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from gcv.config.settings import NORMATIVE_DIR

# semántica de rangos IEEE 519 / Tabla 2.8: 2<h<11, 11≤h<17, 17≤h<23, 23≤h<35, 35≤h≤50
_RANGOS = [(2, 11), (11, 17), (17, 23), (23, 35), (35, 51)]


@lru_cache(maxsize=1)
def _tabla_tdd() -> dict:
    data = yaml.safe_load(
        (NORMATIVE_DIR / "limites" / "tablas_cdr2.yaml").read_text(encoding="utf-8"))
    return data["centros_carga"]["tdd"]


def _nivel(v_kv: float) -> str:
    if v_kv <= 69:
        return "v_hasta_69kv"
    if v_kv <= 161:
        return "v_69_a_161kv"
    return "v_mayor_161kv"


def resolver_fila(v_kv: float, icc_il: float) -> dict:
    """Fila aplicable: {'limites_h': [5 valores % IL], 'datd': %}."""
    if icc_il <= 0:
        raise ValueError("La relación Icc/IL debe ser positiva")
    filas = _tabla_tdd()[_nivel(v_kv)]
    for fila in filas:
        lo, hi = fila["icc_il"]
        if icc_il >= lo and (hi is None or icc_il < hi):
            return fila
    return filas[-1]


def limite_armonica(orden: int, fila: dict, pares_pct_de_impares: float = 25.0) -> float | None:
    """Límite (% de IL) para la armónica `orden` según la fila resuelta."""
    if orden < 2 or orden > 50:
        return None
    for (lo, hi), limite in zip(_RANGOS, fila["limites_h"]):
        en_rango = (lo < orden < hi) if lo == 2 else (lo <= orden < hi)
        if en_rango:
            if orden % 2 == 0:
                return round(limite * pares_pct_de_impares / 100.0, 4)
            return float(limite)
    return None
