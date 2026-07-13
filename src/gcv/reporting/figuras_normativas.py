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
    # extraída del Código de Red 2.0 oficial (DOF 31-dic-2021, pág. 1066)
    "figura_4_1_1_b": "Figura 4.1.1.B — Zona A ante huecos de tensión (asíncronas B/C)",
    "figura_4_2_1": "Figura 4.2.1 — Zona A ante huecos de tensión (síncronas D)",
    "figura_4_2_1_b": "Figura 4.2.1.B — Zona A ante huecos de tensión (asíncronas D)",
}

# prueba → {tecnología|AMBAS: [nombres] | {BC/D: [nombres]}}
MAPA: dict[str, dict[str, list[str] | dict[str, list[str]]]] = {
    "CE-F-03": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-F-04": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-F-05": {"AMBAS": ["figura_2_2_2_a", "figura_2_2_2_b"]},
    "CE-V-02": {"SINCRONA": ["figura_3_3_2", "figura_3_3_3"],
                "ASINCRONA": ["figura_3_5_1", "figura_3_5_2"]},
    "CE-V-03": {"SINCRONA": ["figura_3_3_2", "figura_3_3_3"],
                "ASINCRONA": ["figura_3_5_1", "figura_3_5_2"]},
    "CE-V-07": {"SINCRONA": {"BC": ["figura_4_1_1_a"], "D": ["figura_4_2_1"]},
                "ASINCRONA": {"BC": ["figura_4_1_1_b"], "D": ["figura_4_2_1_b"]}},
}


def figuras_para(test_id: str, tecnologia: str | None,
                 tipo_ce: str | None = None) -> list[tuple[str, Path]]:
    """[(título, ruta)] de las figuras normativas aplicables a la prueba.

    La curva de huecos (CE-V-07) depende del tipo de central (Tabla 4.1.1 para
    B/C, Tabla 4.2.1 para D); sin tipo conocido se incluyen ambas variantes.
    """
    reglas = MAPA.get(test_id)
    if not reglas:
        return []
    tec = (tecnologia or "").upper()
    nombres = list(reglas.get("AMBAS", []))
    por_tec = reglas.get(tec, [])
    if isinstance(por_tec, dict):
        tipo = (tipo_ce or "").upper()
        clave = "D" if tipo == "D" else ("BC" if tipo in ("B", "C") else None)
        if clave:
            nombres += por_tec.get(clave, [])
        else:
            for variante in por_tec.values():
                nombres += variante
    else:
        nombres += por_tec
    out = []
    for n in nombres:
        ruta = _DIR / f"{n}.png"
        if ruta.exists():
            out.append((TITULOS.get(n, n), ruta))
    return out


def figura_b64(ruta: Path) -> str:
    return base64.b64encode(Path(ruta).read_bytes()).decode()
