"""Extrae el catálogo de pruebas desde las plantillas .docx del usuario.

Lee `normative/plantillas_usuario/Protocolo_{Central,Unidad}_v1.2.1.docx` y
produce `normative/protocolos/catalogo_{central,unidad}.yaml` con el flujo
completo de cada prueba (párrafos con su estilo, tablas de datos, marcadores
de figura). El generador (`gcv.protocolos`) reconstruye el capítulo de pruebas
desde estos YAML dentro de la plantilla original, por lo que el formato del
documento final es el del usuario, no uno inventado.

Se vuelve a correr solo cuando el usuario entregue una nueva versión de sus
plantillas:  python tools/extraer_catalogo_protocolos.py
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLAS = RAIZ / "normative" / "plantillas_usuario"
SALIDA = RAIZ / "normative" / "protocolos"

# límites del capítulo de pruebas en cada plantilla
CONFIG = {
    "central": {
        "archivo": "Protocolo_Central_v1.2.1.docx",
        "inicio_h1": "3. Pruebas por Central Eléctrica",
        "fin_h1": "4. Datos de pruebas",
        "patron_seccion": re.compile(r"^3\.(\d+)\.\s*(.+)$"),
    },
    "unidad": {
        "archivo": "Protocolo_Unidad_v1.2.1.docx",
        "inicio_h1": "4. Pruebas Por Unidad",
        "fin_h1": "5. Datos de pruebas",
        "patron_seccion": re.compile(r"^4\.((?:\d+\.)*\d+)\.?\s*(.+)$"),
        # la tabla maestra vive en el capítulo previo
        "maestra_h1": "3. Pruebas aplicables por unidad",
    },
}


def _iter_cuerpo(doc):
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _tabla_es_aplicabilidad(t: Table) -> bool:
    return "LA PRUEBA APLICA" in t.rows[0].cells[0].text


def _tabla_a_filas(t: Table) -> list[list[str]]:
    filas = []
    for r in t.rows:
        vistos, fila = set(), []
        for c in r.cells:
            if id(c._tc) in vistos:  # celdas combinadas: una sola vez
                continue
            vistos.add(id(c._tc))
            fila.append(c.text.strip())
        filas.append(fila)
    return filas


def _parrafo_tiene_imagen(p: Paragraph) -> bool:
    return bool(p._p.findall(".//" + qn("w:drawing")))


def extraer(clave: str) -> dict:
    cfg = CONFIG[clave]
    doc = Document(str(PLANTILLAS / cfg["archivo"]))

    dentro = False
    en_maestra = False  # capítulo separado que solo aporta la tabla maestra
    tabla_maestra = None
    pruebas: list[dict] = []
    actual: dict | None = None
    preambulo: list[dict] = []  # flujo entre el H1 y la primera sección

    for el in _iter_cuerpo(doc):
        if isinstance(el, Paragraph):
            estilo, texto = el.style.name, el.text.strip()
            if estilo == "Heading 1":
                if texto == cfg["inicio_h1"]:
                    dentro, en_maestra = True, False
                    continue
                if dentro:
                    break  # fin del capítulo
                en_maestra = texto == cfg.get("maestra_h1")
                continue
            if not dentro:
                continue

            if estilo == "Heading 2":
                m = cfg["patron_seccion"].match(texto)
                if m:
                    actual = {
                        "seccion": m.group(1),
                        "titulo": m.group(2).strip(),
                        "no_aplica_en_plantilla": "no aplica" in texto.lower(),
                        "flujo": [],
                    }
                    pruebas.append(actual)
                else:
                    # encabezado de grupo (p.ej. "Sistema de Control de Tensión…")
                    actual = None
                    pruebas.append({"grupo": texto})
                continue

            destino = actual["flujo"] if actual is not None else preambulo
            if texto or _parrafo_tiene_imagen(el):
                item = {"estilo": estilo, "texto": texto}
                if _parrafo_tiene_imagen(el):
                    item["imagen_incrustada"] = True
                destino.append(item)
        else:  # Table
            if en_maestra and tabla_maestra is None and not dentro:
                tabla_maestra = _tabla_a_filas(el)
                continue
            if not dentro:
                continue
            if _tabla_es_aplicabilidad(el):
                if actual is not None:
                    actual["flujo"].append({"tabla": "aplicabilidad"})
                continue
            filas = _tabla_a_filas(el)
            if len(el.rows) == 1 and len(el.columns) == 1:
                item = {"placeholder": filas[0][0]}
            elif actual is None and tabla_maestra is None:
                tabla_maestra = filas
                continue
            else:
                item = {"tabla_datos": filas}
            (actual["flujo"] if actual is not None else preambulo).append(item)

    return {
        "origen": cfg["archivo"],
        "capitulo": cfg["inicio_h1"],
        "preambulo": preambulo,
        "tabla_maestra": tabla_maestra,
        "pruebas": pruebas,
    }


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for clave in CONFIG:
        datos = extraer(clave)
        ruta = SALIDA / f"catalogo_{clave}.yaml"
        with ruta.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(datos, fh, allow_unicode=True, sort_keys=False, width=100)
        n_pruebas = sum(1 for p in datos["pruebas"] if "seccion" in p)
        n_grupos = sum(1 for p in datos["pruebas"] if "grupo" in p)
        print(f"{ruta.name}: {n_pruebas} pruebas, {n_grupos} grupos, "
              f"maestra={len(datos['tabla_maestra'] or [])} filas")


if __name__ == "__main__":
    main()
