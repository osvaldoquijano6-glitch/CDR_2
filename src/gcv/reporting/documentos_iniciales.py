"""Generador de documentos iniciales del proyecto (formatos del usuario).

Con solo los datos de la instalación (tipo, tecnología, capacidad → clasificación
automática) y la selección de pruebas, genera el paquete de arranque:

  1. Checklist de Pruebas (.xlsx)         — formato Checklist_de_Pruebas_REV_3
  2. Revisión de pruebas Anexo 5 (.xlsx)  — formato ANEXO_5_POC_Revision_de_pruebas
  3. Protocolo de pruebas (.docx)         — formato 01CNK_Protocolo (estructura 1–7)
  4. Anexo de revisiones y comentarios (.xlsx) — formato Revisiones_Comentarios

El texto por prueba no cambia entre proyectos: solo se agregan o quitan pruebas
según la selección. Sin nombres de empresas: placeholders con el nombre de la
instalación.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml

from gcv.config.settings import MATRIX_PATH, NORMATIVE_DIR
from gcv.evaluation.spec import TestSpec, load_matrix
from gcv.models import Installation, Technology
from gcv.reporting import plantillas

_NAVY = "2A3F54"
_LINEA = "E3E6EA"


@lru_cache(maxsize=1)
def _checklist_rev3() -> list[dict]:
    data = yaml.safe_load((NORMATIVE_DIR / "limites" / "checklist_pruebas_rev3.yaml"
                           ).read_text(encoding="utf-8"))
    return data["filas"]


@lru_cache(maxsize=1)
def _anexo5_revision() -> dict:
    data = yaml.safe_load((NORMATIVE_DIR / "limites" / "anexo5_revision_pruebas.yaml"
                           ).read_text(encoding="utf-8"))
    return data["hojas"]


def _matriz() -> dict[str, TestSpec]:
    return load_matrix(MATRIX_PATH)


def _nombres_seleccionados(pruebas_ids: list[str]) -> set[str]:
    m = _matriz()
    return {m[t].nombre.lower() for t in pruebas_ids if t in m}


def _coincide(nombre_fila: str, seleccionados: set[str]) -> bool:
    n = (nombre_fila or "").lower()
    return any(s[:22] in n or n[:22] in s for s in seleccionados)


# ─── 1. Checklist de Pruebas (.xlsx) ─────────────────────────────────────────
def generar_checklist_xlsx(inst: Installation, pruebas_ids: list[str], path: Path) -> Path:
    import xlsxwriter

    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    ws = wb.add_worksheet("DATOS POR PRUEBA")
    hdr = wb.add_format({"bold": True, "bg_color": _NAVY, "font_color": "white",
                         "border": 1, "text_wrap": True, "valign": "vcenter"})
    celda = wb.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    si = wb.add_format({"border": 1, "bold": True, "font_color": "#0A5C0A",
                        "align": "center", "valign": "top"})
    no = wb.add_format({"border": 1, "font_color": "#8F1F1F",
                        "align": "center", "valign": "top"})
    cols = ["CATEGORÍA", "SISTEMA / SECCIÓN", "CONDICIÓN", "NO.", "PRUEBA",
            "CRITERIO DE ACEPTACIÓN", "TIPO", "SEÑALES REQUERIDAS",
            "APLICA (SI/NO)", "¿SE PUEDE EJECUTAR LA PRUEBA?",
            "COMENTARIOS REV₁", "COMENTARIOS REV₂"]
    for c, name in enumerate(cols):
        ws.write(0, c, name, hdr)
    for c, w in enumerate([16, 22, 12, 5, 26, 34, 10, 32, 12, 14, 18, 18]):
        ws.set_column(c, c, w)

    es_sincrona = inst.tech == Technology.SINCRONA
    seleccion = _nombres_seleccionados(pruebas_ids)
    r = 1
    for fila in _checklist_rev3():
        por_unidad = fila["categoria"] == "PRUEBAS POR UNIDAD"
        if por_unidad:
            aplica = "SI" if es_sincrona else "NO"
        else:
            aplica = "SI" if _coincide(fila["prueba"], seleccion) else "NO"
        valores = [fila["categoria"], fila["sistema"], fila["condicion"], fila["no"],
                   fila["prueba"], fila["criterio"], fila["tipo"], fila["senales"]]
        for c, v in enumerate(valores):
            ws.write(r, c, v if v is not None else "", celda)
        ws.write(r, 8, aplica, si if aplica == "SI" else no)
        ws.write(r, 9, "", celda); ws.write(r, 10, "", celda); ws.write(r, 11, "", celda)
        r += 1
    ws.freeze_panes(1, 0)
    wb.close()
    return path


# ─── 2. Revisión de pruebas Anexo 5 (.xlsx) ──────────────────────────────────
def _hojas_aplicables(inst: Installation) -> list[str]:
    if inst.kind.value == "CENTRO_DE_CARGA":
        return ["CC General", "CC Final"]
    if inst.tech == Technology.SINCRONA:
        return ["CE sincronas"]
    return ["CE ASincronas"]


def generar_revision_anexo5_xlsx(inst: Installation, pruebas_ids: list[str],
                                 path: Path) -> Path:
    import xlsxwriter

    m = _matriz()
    legacy_sel = {str(m[t].legacy_id).lstrip("P") for t in pruebas_ids
                  if t in m and m[t].legacy_id}
    seleccion = _nombres_seleccionados(pruebas_ids)
    hojas = _anexo5_revision()

    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    titulo_f = wb.add_format({"bold": True, "font_size": 13, "bg_color": _NAVY,
                              "font_color": "white", "border": 1})
    hdr = wb.add_format({"bold": True, "bg_color": "#EDF1F6", "border": 1,
                         "text_wrap": True})
    celda = wb.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    seccion_f = wb.add_format({"bold": True, "bg_color": "#DDE5EE", "border": 1})

    for nombre in _hojas_aplicables(inst):
        clave = next((k for k in hojas if k.strip() == nombre.strip()), None)
        if clave is None:
            continue
        ws = wb.add_worksheet(nombre.strip()[:31])
        titulo = ("PRUEBAS CENTROS DE CARGA" if nombre.startswith("CC")
                  else f"PRUEBAS CENTRALES ELÉCTRICAS "
                       f"{'SÍNCRONAS' if 'sincronas' in nombre.lower() and 'as' != nombre[3:5].lower() else 'ASÍNCRONAS'}"
                  if nombre.startswith("CE") else nombre)
        ws.merge_range(0, 0, 0, 2, titulo, titulo_f)
        ws.write(0, 3, "RESPONSABLE", titulo_f); ws.write(0, 4, "COMENTARIOS", titulo_f)
        for c, h in enumerate(["Numero", "Pruebas", "Criterio de aceptación",
                               "RESPONSABLE", "COMENTARIOS"]):
            ws.write(1, c, h, hdr)
        for c, w in enumerate([8, 34, 52, 14, 30]):
            ws.set_column(c, c, w)
        r = 2
        es_cc = nombre.startswith("CC")
        for fila in hojas[clave]:
            if "seccion" in fila:
                ws.merge_range(r, 0, r, 4, fila["seccion"], seccion_f); r += 1
                continue
            num = str(fila.get("numero", ""))
            incluir = (es_cc or not legacy_sel or num in legacy_sel
                       or _coincide(fila.get("prueba") or "", seleccion))
            if not incluir:
                continue
            ws.write(r, 0, fila.get("numero"), celda)
            ws.write(r, 1, fila.get("prueba") or "", celda)
            ws.write(r, 2, fila.get("criterio") or "", celda)
            ws.write(r, 3, fila.get("responsable") or "", celda)
            ws.write(r, 4, fila.get("comentarios") or "", celda)
            r += 1
        ws.freeze_panes(2, 0)
    wb.close()
    return path


# ─── 3. Protocolo de pruebas (.docx) ─────────────────────────────────────────
_DEFINICIONES = [
    ("CENACE", "Centro Nacional de Control de Energía"),
    ("CdR 2.0", "Código de Red 2.0 (RES/550/2021, DOF 31-dic-2021)"),
    ("Manual INTE", "Manual Regulatorio de Requerimientos Técnicos para la "
                    "Interconexión de Centrales Eléctricas al SEN"),
    ("POC", "Procedimiento de Operación para la Declaración de Entrada en "
            "Operación Comercial"),
    ("Anexo 5", "Listado de Pruebas por Tipo de Central Eléctrica (POC)"),
    ("PI / POI", "Punto de Interconexión"),
    ("CIN", "Capacidad Instalada Neta"),
    ("CPF / CSF", "Control Primario / Secundario de Frecuencia"),
    ("AVR", "Regulador Automático de Tensión"),
    ("SEN", "Sistema Eléctrico Nacional"),
]


def generar_protocolo_docx(inst: Installation, pruebas_ids: list[str],
                           path: Path, version: str = "1.0") -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    m = _matriz()
    seleccion = [m[t] for t in pruebas_ids if t in m]
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)

    # Portada
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("\nPROTOCOLO DE PRUEBAS\nCÓDIGO DE RED 2.0 — POC / ANEXO 5\n")
    run.bold = True; run.font.size = Pt(22); run.font.color.rgb = RGBColor(0x2A, 0x3F, 0x54)
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    clasif = (f"Central Eléctrica Tipo {inst.category.value if inst.category else '—'} · "
              f"{(inst.tech.value.title() if inst.tech else '—')} · "
              f"Área {(inst.area_sincrona.value if inst.area_sincrona else '—')}"
              if inst.kind.value == "CENTRAL_ELECTRICA" else "Centro de Carga")
    p2.add_run(f"{inst.nombre}\n{clasif}\n"
               f"CIN: {inst.capacidad_instalada_neta_mw or '—'} MW · "
               f"Versión {version} · {datetime.now():%d/%b/%Y}").font.size = Pt(13)
    doc.add_page_break()

    doc.add_heading("1. Definiciones y Abreviaciones", level=1)
    t = doc.add_table(rows=1, cols=2); t.style = "Light Grid Accent 1"
    t.rows[0].cells[0].text = "Término"; t.rows[0].cells[1].text = "Definición"
    for k, v in _DEFINICIONES:
        c = t.add_row().cells; c[0].text = k; c[1].text = v

    doc.add_heading("2. Introducción", level=1)
    doc.add_paragraph(
        f"El presente protocolo establece las pruebas aplicables a {inst.nombre} para la "
        "Declaración de Entrada en Operación Comercial, conforme al Anexo 5 del POC y a los "
        "requerimientos técnicos del Código de Red 2.0 (Manual INTE / Manual CONE, "
        "RES/550/2021). Las pruebas, criterios de aceptación y señales requeridas se toman "
        "de la matriz normativa del sistema de verificación; los criterios citan el numeral "
        "correspondiente y no se modifican entre proyectos: únicamente se agregan o retiran "
        "pruebas según la clasificación y el alcance acordado con CENACE.")

    doc.add_heading("3. Pruebas aplicables", level=1)
    t = doc.add_table(rows=1, cols=4); t.style = "Light Grid Accent 1"
    for i, h in enumerate(["No.", "Prueba", "Referencia normativa", "Aplica"]):
        t.rows[0].cells[i].text = h
    for spec in seleccion:
        c = t.add_row().cells
        c[0].text = spec.legacy_id or spec.id
        c[1].text = spec.nombre
        c[2].text = spec.numeral or ""
        c[3].text = "SÍ"

    from docx.shared import Inches

    from gcv.reporting.figuras_normativas import figuras_para

    def _tabla_resultados():
        t = doc.add_table(rows=1, cols=5); t.style = "Light Grid Accent 1"
        for i, h in enumerate(["PASO", "HORA INICIO", "HORA FIN",
                               "VARIABLE DE EXCITACIÓN", "POTENCIA / RESPUESTA"]):
            t.rows[0].cells[i].text = h
        for _ in range(4):
            t.add_row()

    tec = inst.tech.value if inst.tech else None
    doc.add_heading("4. Desarrollo de las pruebas", level=1)
    for n, spec in enumerate(seleccion, start=1):
        doc.add_heading(f"4.{n}. {spec.nombre}", level=2)
        doc.add_paragraph("Objetivo").runs[0].bold = True
        doc.add_paragraph(plantillas.objetivo(spec.id, inst.nombre) or
                          f"Verificar el cumplimiento de {spec.nombre} conforme a "
                          f"{spec.cita()}.")
        doc.add_paragraph("Criterio de aceptación").runs[0].bold = True
        doc.add_paragraph((spec.criterio_aceptacion or "").strip())
        for titulo_fig, ruta in figuras_para(spec.id, tec):
            doc.add_picture(str(ruta), width=Inches(5.6))
            cap = doc.add_paragraph(titulo_fig)
            cap.runs[0].italic = True; cap.runs[0].font.size = Pt(9)
        doc.add_paragraph("Metodología").runs[0].bold = True
        doc.add_paragraph((spec.formula_algoritmo or "").strip() or "Conforme al protocolo acordado con CENACE.")
        doc.add_paragraph("Señales requeridas").runs[0].bold = True
        for v in spec.variables_requeridas:
            doc.add_paragraph(v, style="List Bullet")
        doc.add_paragraph("Tabla de resultados").runs[0].bold = True
        _tabla_resultados()

    # Capítulo de Pruebas por Unidad (síncronas): universo del Checklist REV3
    cap = 5
    if inst.tech == Technology.SINCRONA:
        doc.add_heading("5. Pruebas por Unidad", level=1)
        doc.add_paragraph(
            "Pruebas por unidad de generación conforme al Anexo 5 (síncronas 1 a 20), "
            "con criterios del checklist de pruebas del proyecto. Se ejecutan por cada "
            "unidad antes de las pruebas por central.")
        unidad = [f for f in _checklist_rev3()
                  if f["categoria"] == "PRUEBAS POR UNIDAD"]
        sistema_actual = None
        for k, fila in enumerate(unidad, start=1):
            if fila["sistema"] and fila["sistema"] != sistema_actual:
                sistema_actual = fila["sistema"]
                doc.add_heading(f"{sistema_actual} — {fila['condicion'] or ''}".strip(" —"),
                                level=2)
            doc.add_heading(f"5.{k}. {fila['prueba']}", level=3)
            doc.add_paragraph("Criterio de aceptación").runs[0].bold = True
            doc.add_paragraph(fila["criterio"] or "Conforme al protocolo de la unidad.")
            if fila["senales"]:
                doc.add_paragraph("Señales requeridas").runs[0].bold = True
                for s in str(fila["senales"]).splitlines():
                    if s.strip():
                        doc.add_paragraph(s.strip(), style="List Bullet")
            _tabla_resultados()
        cap = 6

    doc.add_heading(f"{cap}. Datos de pruebas", level=1)
    doc.add_paragraph("Registros de medición con estampa de tiempo HH:MM:SS.mmm, muestreo "
                      "≥ 20 muestras/s en pruebas dinámicas, adjuntos al reporte de resultados.")
    doc.add_heading(f"{cap + 1}. Certificados de Calibración de Equipos de Medición", level=1)
    doc.add_paragraph("Anexar certificados vigentes del equipo de medición Clase A utilizado.")
    doc.add_heading(f"{cap + 2}. Referencias", level=1)
    for ref in ("Código de Red 2.0 — RES/550/2021 (DOF 31-dic-2021)",
                "Manual Regulatorio INTE / CONE",
                "POC — Anexo 5, CENACE",
                "Manual para la Interconexión de Centrales Eléctricas y Conexión de "
                "Centros de Carga (DOF 09-feb-2018)"):
        doc.add_paragraph(ref, style="List Bullet")

    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


# ─── 4. Anexo de revisiones y comentarios (.xlsx) ────────────────────────────
def generar_revisiones_xlsx(inst: Installation, path: Path,
                            documento_base: str = "MIC / Anexo IV — Información Técnica") -> Path:
    import xlsxwriter

    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    titulo = wb.add_format({"bold": True, "font_size": 14, "font_color": _NAVY})
    label = wb.add_format({"bold": True})
    hdr = wb.add_format({"bold": True, "bg_color": _NAVY, "font_color": "white",
                         "border": 1, "text_wrap": True})
    celda = wb.add_format({"border": 1, "text_wrap": True, "valign": "top"})

    ws = wb.add_worksheet("Portada")
    ws.write(1, 1, "ANEXO DE REVISIONES Y COMENTARIOS", titulo)
    ws.write(2, 1, f"Proyecto: {inst.nombre}")
    ws.write(3, 1, "Documento base:", label); ws.write(3, 2, documento_base)
    ws.write(4, 1, "Generado:", label); ws.write(4, 2, f"{datetime.now():%Y-%m-%d}")
    for c, h in enumerate(["REV", "FECHA", "MOTIVO / ALCANCE DE LA REVISIÓN",
                           "ELABORÓ", "ESTATUS"]):
        ws.write(6, 1 + c, h, hdr)
    ws.write(7, 1, "1.0", celda); ws.write(7, 2, f"{datetime.now():%d/%b/%Y}", celda)
    ws.write(7, 3, "Emisión inicial", celda); ws.write(7, 4, "", celda)
    ws.write(7, 5, "Abierta", celda)
    ws.set_column(1, 5, 22)

    ws2 = wb.add_worksheet("Comentarios CENACE")
    ws2.merge_range(0, 0, 0, 7, "REGISTRO CONTINUO DE OBSERVACIONES CENACE", titulo)
    cols = ["No.", "Sección\nMIC", "Título de sección",
            "Parámetro / Requerimiento", "Estatus", "Comentarios CENACE",
            "Comentarios internos", "Acción / respuesta"]
    for c, h in enumerate(cols):
        ws2.write(2, c, h, hdr)
    for c, w in enumerate([5, 10, 24, 40, 10, 32, 32, 32]):
        ws2.set_column(c, c, w)
    for r in range(3, 23):  # filas listas para captura
        for c in range(len(cols)):
            ws2.write(r, c, "", celda)
    ws2.freeze_panes(3, 0)
    wb.close()
    return path


# ─── Paquete completo ─────────────────────────────────────────────────────────
def generar_paquete(inst: Installation, pruebas_ids: list[str], outdir: Path) -> dict[str, Path]:
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch for ch in inst.nombre.upper() if ch.isalnum() or ch == " ").replace(" ", "_")[:30]
    return {
        "checklist": generar_checklist_xlsx(inst, pruebas_ids, outdir / f"{slug}_Checklist_de_Pruebas.xlsx"),
        "revision_anexo5": generar_revision_anexo5_xlsx(inst, pruebas_ids, outdir / f"{slug}_ANEXO5_Revision_de_pruebas.xlsx"),
        "protocolo": generar_protocolo_docx(inst, pruebas_ids, outdir / f"{slug}_Protocolo_de_Pruebas.docx"),
        "revisiones": generar_revisiones_xlsx(inst, outdir / f"{slug}_Revisiones_y_Comentarios.xlsx"),
    }
