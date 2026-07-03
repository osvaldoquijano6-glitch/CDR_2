"""Homologación de unidades.

Unidades canónicas de almacenamiento interno (todas las señales normalizadas
se guardan en estas unidades; la matriz normativa declara sus límites en la
unidad que cite el numeral y la conversión se registra en la bitácora):

    frecuencia  Hz        tensión  V        corriente  A
    P           MW        Q        MVAr     S          MVA
    tiempo      s         FP/THD/Pst/…      adimensional o %

`pu` no se convierte automáticamente: requiere una base explícita
(pu_to_physical), y la base usada queda en la traza del canal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

# unidad → (cantidad, unidad_canónica, factor a canónica)
_UNIT_TABLE: dict[str, tuple[str, str, float]] = {
    # frecuencia
    "hz": ("frequency", "Hz", 1.0),
    "mhz": ("frequency", "Hz", 1e-3),  # milihertz en medidores de desviación
    # tensión
    "v": ("voltage", "V", 1.0),
    "kv": ("voltage", "V", 1e3),
    "mv": ("voltage", "V", 1e-3),
    # corriente
    "a": ("current", "A", 1.0),
    "ka": ("current", "A", 1e3),
    "ma": ("current", "A", 1e-3),
    # potencia activa
    "w": ("active_power", "MW", 1e-6),
    "kw": ("active_power", "MW", 1e-3),
    "mw": ("active_power", "MW", 1.0),
    # potencia reactiva
    "var": ("reactive_power", "MVAr", 1e-6),
    "kvar": ("reactive_power", "MVAr", 1e-3),
    "mvar": ("reactive_power", "MVAr", 1.0),
    # potencia aparente
    "va": ("apparent_power", "MVA", 1e-6),
    "kva": ("apparent_power", "MVA", 1e-3),
    "mva": ("apparent_power", "MVA", 1.0),
    # tiempo
    "s": ("time", "s", 1.0),
    "seg": ("time", "s", 1.0),
    "sec": ("time", "s", 1.0),
    "ms": ("time", "s", 1e-3),
    "min": ("time", "s", 60.0),
    "h": ("time", "s", 3600.0),
    # adimensionales
    "%": ("ratio", "%", 1.0),
    "pu": ("ratio", "pu", 1.0),
    "p.u.": ("ratio", "pu", 1.0),
}

_HEADER_UNIT_RE = re.compile(r"[\[\(]\s*([^\]\)]+?)\s*[\]\)]")


@dataclass(frozen=True)
class UnitInfo:
    original: str
    cantidad: str
    canonica: str
    factor: float  # valor_canónico = valor_original * factor


def normalize_unit_symbol(unit: str) -> str:
    return str(unit).strip().lower().replace("μ", "u")


def parse_unit(unit: str | None) -> UnitInfo | None:
    """Interpreta un símbolo de unidad. None si es desconocido o vacío."""
    if unit is None:
        return None
    sym = normalize_unit_symbol(unit)
    if sym in _UNIT_TABLE:
        cantidad, canonica, factor = _UNIT_TABLE[sym]
        return UnitInfo(original=str(unit).strip(), cantidad=cantidad, canonica=canonica, factor=factor)
    return None


def unit_from_header(header: object) -> str | None:
    """Extrae la unidad declarada entre corchetes/paréntesis: 'P [kW]' → 'kW'."""
    m = _HEADER_UNIT_RE.search(str(header))
    if not m:
        return None
    candidate = m.group(1)
    return candidate if parse_unit(candidate) else None


def convert_series(series: pd.Series, info: UnitInfo) -> pd.Series:
    return series * info.factor if info.factor != 1.0 else series


def pu_to_physical(series: pd.Series, base: float) -> pd.Series:
    """Convierte pu a magnitud física con base explícita (nunca implícita)."""
    if base <= 0:
        raise ValueError("La base para conversión pu debe ser positiva.")
    return series * base
