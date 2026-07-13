"""Diccionario de alias de señales y emparejamiento determinístico.

Identifica columnas equivalentes con nombres distintos (f/freq/Frequency/Hz…).
El emparejamiento es determinístico y auditable: cada match reporta método y
confianza. La sugerencia por similitud ML (capa `ml`) puede proponer mapeos,
pero siempre con confirmación del usuario (MappingMethod.AUTO_ML_SUGERIDO).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ─── Señales canónicas ────────────────────────────────────────────────────────
# Alias exactos (tras normalizar: minúsculas, sin acentos, sin unidad entre [] o ()).
ALIASES: dict[str, list[str]] = {
    "timestamp": ["timestamp", "datetime", "fecha hora", "fechahora", "date time", "date/time"],
    "date": ["fecha", "date", "dia"],
    "time_of_day": ["hora", "time", "hora local", "local time"],
    "frequency": ["f", "freq", "frequency", "frecuencia", "hz", "frec"],
    "voltage": ["v", "vrms", "voltage", "tension", "voltaje", "u", "urms"],
    "voltage_a": ["va", "v1", "van", "v1n", "ua", "l1"],
    "voltage_b": ["vb", "v2", "vbn", "v2n", "ub", "l2"],
    "voltage_c": ["vc", "v3", "vcn", "v3n", "uc", "l3"],
    "voltage_ab": ["vab", "v12", "uab"],
    "voltage_bc": ["vbc", "v23", "ubc"],
    "voltage_ca": ["vca", "v31", "uca"],
    "current": ["i", "irms", "current", "corriente", "amp", "amps"],
    "current_a": ["ia", "i1"],
    "current_b": ["ib", "i2"],
    "current_c": ["ic", "i3"],
    "active_power": ["p", "mw", "kw", "active power", "potencia activa", "p total", "ptot", "watts"],
    "reactive_power": ["q", "mvar", "kvar", "reactive power", "potencia reactiva", "q total", "qtot", "vars"],
    "apparent_power": ["s", "mva", "kva", "apparent power", "potencia aparente"],
    "power_factor": ["fp", "pf", "power factor", "factor de potencia", "cos phi", "cosphi", "cos fi"],
    "thd_voltage": ["thd v", "thdv", "thd voltage", "thd tension", "thd u", "vthd"],
    "thd_current": ["thd i", "thdi", "thd current", "thd corriente", "ithd"],
    "tdd": ["tdd"],
    "pst": ["pst"],
    "plt": ["plt"],
    "pinst": ["pinst", "ifl"],
    "unbalance": ["unbalance", "desbalance", "desequilibrio", "u2/u1", "v2/v1"],
    "rocof": ["rocof", "df/dt", "dfdt"],
    "corriente_dc": ["idc", "i dc", "dc current", "corriente directa", "componente dc"],
    "setpoint_p": ["setpoint", "set point", "consigna", "p setpoint", "order", "potencia teorica",
                   "potencia referencia", "theoretical power", "reference power", "p ref"],
    "setpoint_v": ["v setpoint", "consigna v", "consigna tension", "voltage setpoint",
                   "v ref", "vref"],
    "setpoint_q": ["q setpoint", "consigna q", "consigna reactiva", "reactive setpoint",
                   "q ref", "qref"],
    "setpoint_fp": ["fp setpoint", "consigna fp", "pf setpoint", "consigna factor",
                    "fp ref", "pfref"],
}

# Grupos de tokens: match si TODOS los tokens aparecen en el encabezado normalizado.
# Complementan los alias exactos para encabezados largos de equipos
# (hereda tests/simple.py::SIGNAL_SPECS del proyecto legado).
TOKEN_GROUPS: dict[str, list[tuple[str, ...]]] = {
    "timestamp": [("date", "time"), ("fecha", "hora")],
    "frequency": [("frequency",), ("frecuencia",)],
    "voltage": [("voltage",), ("tension",), ("volt",)],
    "current": [("current",), ("corriente",)],
    "active_power": [("active", "power"), ("potencia", "activa")],
    "reactive_power": [("reactive", "power"), ("potencia", "reactiva")],
    "power_factor": [("power", "factor"), ("factor", "potencia")],
    "thd_voltage": [("thd", "voltage"), ("thd", "tension")],
    "thd_current": [("thd", "current"), ("thd", "corriente")],
    "unbalance": [("unbalance",), ("desbalance",)],
    "setpoint_p": [("setpoint",), ("consigna",), ("theoretical", "power"), ("reference", "power"),
                   ("potencia", "teor"), ("potencia", "refer")],
    "rocof": [("rocof",), ("df", "dt")],
    "pst": [("pst",)],
    "plt": [("plt",)],
}

_HARMONIC_RE = re.compile(r"^(h|arm(?:onico)?|harmonic)\s*_?(\d{1,2})\b", re.IGNORECASE)
_INTERHARMONIC_RE = re.compile(
    r"^(ih|inter\s*_?arm(?:onico)?s?|inter\s*_?harmonic)\s*_?(\d{1,2})\b", re.IGNORECASE)
_UNIT_SUFFIX_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")


@dataclass(frozen=True)
class SignalMatch:
    señal: str
    score: float  # 1.0 alias exacto · 0.8 grupo de tokens · 0.6 armónico numerado
    metodo: str  # "alias_exacto" | "grupo_tokens" | "armonico"


def normalize_header(header: object) -> str:
    """minúsculas, sin acentos, sin unidades entre corchetes/paréntesis, espacios colapsados."""
    text = str(header)
    text = _UNIT_SUFFIX_RE.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9/.%]+", " ", text.lower())
    return " ".join(text.split())


def match_signal(header: object) -> SignalMatch | None:
    """Empareja un encabezado con una señal canónica. None si no hay match."""
    norm = normalize_header(header)
    if not norm:
        return None

    for signal, aliases in ALIASES.items():
        if norm in aliases:
            return SignalMatch(signal, 1.0, "alias_exacto")

    m = _INTERHARMONIC_RE.match(norm)
    if m:
        order = int(m.group(2))
        kind = "voltage" if any(k in norm for k in ("v", "tension", "volt")) else "current"
        return SignalMatch(f"interharmonic_{kind}_{order}", 0.6, "armonico")

    m = _HARMONIC_RE.match(norm)
    if m:
        order = int(m.group(2))
        kind = "voltage" if any(k in norm for k in ("v", "tension", "volt")) else "current"
        return SignalMatch(f"harmonic_{kind}_{order}", 0.6, "armonico")

    # Grupos de tokens: gana el grupo más específico (más tokens exigidos),
    # p. ej. ("thd","voltage") sobre ("voltage",) para "THD Voltage L1".
    tokens = set(norm.split())
    best: tuple[int, str] | None = None
    for signal, groups in TOKEN_GROUPS.items():
        for group in groups:
            if all(any(t == g or t.startswith(g) for t in tokens) for g in group):
                if best is None or len(group) > best[0]:
                    best = (len(group), signal)
    if best is not None:
        return SignalMatch(best[1], 0.8, "grupo_tokens")

    return None
