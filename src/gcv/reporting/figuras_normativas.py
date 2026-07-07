"""Figuras normativas del Manual INTE (CdR 2.0) — normative/figuras/.

Mapa prueba → tecnología → figuras. Se insertan en el Protocolo (.docx) y en
el informe HTML como referencia normativa de la sección correspondiente.
"""

from __future__ import annotations

import base64
from pathlib import Path

from gcv.config.settings import NORMATIVE_DIR

_DIR = NORMATIVE_DIR / "figuras"

TITULOS = {
    "figura_2_2_2_a": "Figura 2.2.2.A — Característica de regulación del CPF",
    "figura_2_2_2_b": "Figura 2.2.2.B — Respuesta del Control Primario de Frecuencia",
    "figura_3_3_2": "Figura 3.3.2 — Perfil V-Q/Pmáx (síncronas)",
    "figura_3_3_3": "Figura 3.3.3 — Perfil V-P-Q/Pmáx (síncronas)",
    "figura_3_5_1": "Figura 3.5.1 — Perfil P-Q/Pmáx (asíncronas)",
    "figura_3_5_2": "Figura 3.5.2 — Perfil V-P-Q/Pmáx (asíncronas)",
    "figura_4_1_1_a": "Figura 4.1.1.A — Zona A ante huecos de tensión (síncronas B/C)",
    "figura_4_2_1": "Figura 4.2.1 — Zona A ante huecos de tensión (síncronas D)",
    "figura_4_2_1_b": "Figura 4.2.1.B — Zona A ante huecos de tensión (asíncronas D)",
}

# prueba → {tecnología|AMBAS: [nombres]}
MAPA: dict[str, dict[str, list[str]]] = {
    "CE-F-03": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-F-04": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-F-05": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-V-02": {"SINCRONA": ["figura_3_3_2", "figura_3_3_3"],
                "ASINCRONA": ["figura_3_5_1", "figura_3_5_2"]},
    "CE-V-03": {"SINCRONA": ["figura_3_3_2", "figura_3_3_3"],
                "ASINCRONA": ["figura_3_5_1", "figura_3_5_2"]},
    "CE-V-07": {"SINCRONA": ["figura_4_1_1_a", "figura_4_2_1"],
                "ASINCRONA": ["figura_4_2_1_b"]},
}


def figuras_para(test_id: str, tecnologia: str | None) -> list[tuple[str, Path]]:
    """[(título, ruta)] de las figuras normativas aplicables a la prueba."""
    reglas = MAPA.get(test_id)
    if not reglas:
        return []
    tec = (tecnologia or "").upper()
    nombres = reglas.get("AMBAS", []) + reglas.get(tec, [])
    out = []
    for n in nombres:
        ruta = _DIR / f"{n}.png"
        if ruta.exists():
            out.append((TITULOS.get(n, n), ruta))
    return out


def figura_b64(ruta: Path) -> str:
    return base64.b64encode(Path(ruta).read_bytes()).decode()
