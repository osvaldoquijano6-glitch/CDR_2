"""Anexo de Revisiones y Comentarios — formato exacto del usuario (v1.0).

Se parte de `Revisiones_Comentarios_SySCE_v1.0.xlsx` (hojas Portada y
Comentarios CENACE) y solo se estampan los datos del proyecto y, si se
entregan, filas de comentarios. El diseño no se reconstruye nunca.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from gcv.config.settings import NORMATIVE_DIR

PLANTILLA = NORMATIVE_DIR / "plantillas_usuario" / "Revisiones_Comentarios_SySCE_v1.0.xlsx"

# columnas de la hoja "Comentarios CENACE" (fila 4 = encabezados, datos desde 5)
_FILA_DATOS = 5
_COLUMNAS = ["No.", "Sección", "Título de sección", "Parámetro / Requerimiento",
             "Estatus", "Comentarios CENACE", "Comentarios SYSCE",
             "Acción / respuesta", "Fecha"]


def generar_revisiones(destino: Path, proyecto: str = "",
                       documento_base: str = "") -> Path:
    """Genera el anexo de revisiones con la portada actualizada al proyecto."""
    wb = openpyxl.load_workbook(PLANTILLA)
    portada = wb["Portada"]
    for fila in portada.iter_rows(min_row=1, max_row=10):
        for celda in fila:
            valor = celda.value
            if not isinstance(valor, str):
                continue
            if valor.startswith("Proyecto:") and proyecto:
                celda.value = f"Proyecto: {proyecto}"
            elif valor.startswith("MIC / Anexo") and documento_base:
                celda.value = documento_base

    destino = Path(destino)
    if destino.suffix.lower() != ".xlsx":
        destino.mkdir(parents=True, exist_ok=True)
        destino = destino / "Anexo_Revisiones_Comentarios.xlsx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(destino))
    return destino
