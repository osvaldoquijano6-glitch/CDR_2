"""Protocolo estilo v2 — rediseño regulatorio aprobado por el usuario.

A diferencia de `builder` (cirugía sobre la plantilla original), este módulo
GENERA el documento completo desde los datos del proyecto + catálogo YAML,
con el lenguaje visual aprobado:

  * banda de marca azul eléctrico al tope
  * eyebrow normativo (Código de Red 2.0 · RES/550/2021 · Manual INTE · POC A5)
  * ficha de datos del proyecto (Central / Tipo / Tecnología / Alcance / Fechas)
  * numeración de sección en placa azul
  * tabla maestra con cabecera sólida azul y estados como chips SI / NO APLICA
  * secciones de prueba renderizadas desde el catálogo YAML

Paleta (Variante A aprobada):
  eléctrico #0EA5D8 · eléctrico oscuro #0B7FA8 · marino #1B3A6B ·
  apagado (no aplica) #7FB8D9 · cuerpo #2C3A48

Regla dura: la columna APLICA solo lleva SI / NO / APLICA / NO APLICA. Las
notas libres provienen del usuario (visita en sitio, CENACE, dictamen); este
generador solo las estampa si vienen en `proyecto.notas`, nunca las redacta.

Tipografías del usuario: Montserrat (display) y Helvetica Neue (cuerpo). Los
estilos con nombre ("GCV ...") permiten reestilar todo el documento desde
Word con un par de clics.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from gcv.protocolos.builder import ProyectoProtocolo, _cargar_catalogo, _numero_de, _CFG
from gcv.protocolos.checklist import universo_pruebas

# ── paleta aprobada (Variante A) ────────────────────────────────────────────
ELECTRIC = "0EA5D8"
ELECTRIC_DARK = "0B7FA8"
NAVY = "1B3A6B"
MUTED = "7FB8D9"
BODY = "2C3A48"
LABEL = "7A7060"
CHIP_SI_BG = "E1F3FA"
CHIP_NO_BG = "EDEFF1"
CHIP_NO_FG = "7D8A94"
ROW_LINE = "E4EDF2"
RULE = "CFE4EF"

DISPLAY = "Montserrat"
CUERPO = "Helvetica Neue"


# ── helpers XML ─────────────────────────────────────────────────────────────
def _rgb(hexval: str) -> RGBColor:
    return RGBColor.from_string(hexval)


def _cell_bg(cell, hexval: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexval)
    tc_pr.append(shd)


def _run_spacing(run, val: int = 30) -> None:
    """Espaciado entre letras (eyebrow / etiquetas)."""
    r_pr = run._r.get_or_add_rPr()
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:val"), str(val))
    r_pr.append(sp)


def _run_bg(run, hexval: str) -> None:
    r_pr = run._r.get_or_add_rPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexval)
    r_pr.append(shd)


def _p_bottom_border(p, hexval: str = RULE, sz: int = 6) -> None:
    p_pr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), hexval)
    borders.append(bottom)
    p_pr.append(borders)


def _cell_borders(cell, bottom: str | None = ROW_LINE) -> None:
    """Solo línea inferior tenue (retícula recesiva de la propuesta)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for lado in ("top", "left", "right"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    el = OxmlElement("w:bottom")
    if bottom:
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), bottom)
    else:
        el.set(qn("w:val"), "nil")
    borders.append(el)
    tc_pr.append(borders)


def _row_header_repeat(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    tr_pr.append(el)


def _texto(p, texto: str, *, font: str = CUERPO, size: float = 10,
           bold: bool = False, color: str = BODY, spacing: int | None = None,
           bg: str | None = None):
    run = p.add_run(texto)
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    if spacing:
        _run_spacing(run, spacing)
    if bg:
        _run_bg(run, bg)
    return run


# ── bloques del documento ───────────────────────────────────────────────────
def _banda_marca(doc: Document) -> None:
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.rows[0].cells[0]
    _cell_bg(cell, ELECTRIC)
    _cell_borders(cell, bottom=None)
    p = cell.paragraphs[0]
    run = p.add_run(" ")
    run.font.size = Pt(2)
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    h = OxmlElement("w:trHeight")
    h.set(qn("w:val"), "140")
    h.set(qn("w:hRule"), "exact")
    tr_pr.append(h)


def _eyebrow(doc: Document, texto: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    _texto(p, texto.upper(), font=DISPLAY, size=8, bold=True,
           color=ELECTRIC_DARK, spacing=40)


def _titulo(doc: Document, proyecto: ProyectoProtocolo) -> None:
    tecnologia = ("SÍNCRONAS" if proyecto.tecnologia.upper().startswith("S")
                  else "ASÍNCRONAS")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(12)
    _texto(p, "PROTOCOLO DE PRUEBAS PARA PUESTA EN SERVICIO DE ",
           font=DISPLAY, size=15, bold=True, color=NAVY)
    _texto(p, f"CENTRALES ELÉCTRICAS {tecnologia}",
           font=DISPLAY, size=15, bold=True, color=ELECTRIC)


def _ficha_datos(doc: Document, proyecto: ProyectoProtocolo, alcance: str) -> None:
    campos = [("CENTRAL", proyecto.nombre_central),
              ("TIPO", proyecto.tipo),
              ("TECNOLOGÍA", proyecto.tecnologia.title()),
              ("ALCANCE", alcance)]
    extra = [("PROYECTO", proyecto.proyecto),
             ("UBICACIÓN", proyecto.ubicacion),
             ("FECHA DE PRUEBAS", proyecto.fecha_pruebas),
             ("FECHA DE ENVÍO", proyecto.fecha_envio)]
    extra = [(k, v) for k, v in extra if v]
    filas_campos = [campos] + ([extra] if extra else [])

    for grupo in filas_campos:
        t = doc.add_table(rows=2, cols=len(grupo))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, (etiqueta, valor) in enumerate(grupo):
            c_lbl, c_val = t.rows[0].cells[j], t.rows[1].cells[j]
            _cell_borders(c_lbl, bottom=None)
            _cell_borders(c_val, bottom=None)
            p = c_lbl.paragraphs[0]
            _texto(p, etiqueta, font=DISPLAY, size=7.5, bold=True,
                   color=LABEL, spacing=30)
            p = c_val.paragraphs[0]
            _texto(p, str(valor), font=CUERPO, size=11, bold=True, color=NAVY)
    # regla al pie de la ficha
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    _p_bottom_border(p, RULE, sz=8)


def _seccion(doc: Document, numero: str, titulo: str,
             muted: bool = False) -> None:
    """Encabezado de sección con placa numerada azul."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    _texto(p, f" {numero} ", font=DISPLAY, size=10.5, bold=True,
           color="FFFFFF", bg=(MUTED if muted else ELECTRIC))
    _texto(p, f"  {titulo}", font=DISPLAY, size=12, bold=True,
           color=(MUTED if muted else NAVY))
    _p_bottom_border(p, RULE, sz=6)


def _chip(cell, texto: str, aplica: bool) -> None:
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _texto(p, f" {texto} ", font=DISPLAY, size=8, bold=True,
           color=(ELECTRIC_DARK if aplica else CHIP_NO_FG),
           bg=(CHIP_SI_BG if aplica else CHIP_NO_BG))


def _tabla_maestra(doc: Document, proyecto: ProyectoProtocolo, clase: str) -> None:
    universo = universo_pruebas()
    if clase == "central":
        filas = [u for u in universo if u["numero"] >= 21]
    else:
        filas = [u for u in universo if u["numero"] <= 20]

    t = doc.add_table(rows=1, cols=4)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    anchos = (Cm(1.1), Cm(5.2), Cm(8.4), Cm(2.6))
    encabezados = ("No.", "Prueba", "Criterio de aceptación", "Aplica")
    hdr = t.rows[0]
    _row_header_repeat(hdr)
    for j, texto in enumerate(encabezados):
        c = hdr.cells[j]
        c.width = anchos[j]
        _cell_bg(c, ELECTRIC)
        _cell_borders(c, bottom=None)
        p = c.paragraphs[0]
        if j in (0, 3):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _texto(p, texto, font=DISPLAY, size=9, bold=True, color="FFFFFF")

    for u in filas:
        numero = u["numero"]
        nota = proyecto.notas.get(numero, "").strip()
        aplica = numero in proyecto.pruebas_aplican
        estado = nota if nota else ("SI" if aplica else "NO APLICA")
        color_txt = BODY if aplica else MUTED
        row = t.add_row()
        datos = (str(numero), u["nombre"], u["criterio"])
        for j, texto in enumerate(datos):
            c = row.cells[j]
            c.width = anchos[j]
            _cell_borders(c)
            p = c.paragraphs[0]
            if j == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _texto(p, texto, size=9.5, bold=True,
                       color=(ELECTRIC_DARK if aplica else MUTED))
            else:
                _texto(p, texto, size=9.5, color=color_txt)
        c = row.cells[3]
        c.width = anchos[3]
        _cell_borders(c)
        _chip(c, estado, aplica)


def _tabla_aplicabilidad(doc: Document, tipo: str) -> None:
    t = doc.add_table(rows=2, cols=8)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    etiquetas = ("A", "", "B", "", "C", "", "D", "")
    for j in range(8):
        c0, c1 = t.rows[0].cells[j], t.rows[1].cells[j]
        for c in (c0, c1):
            _cell_borders(c)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if etiquetas[j]:
            _cell_bg(c0, CHIP_SI_BG)
            _texto(c0.paragraphs[0], f"Tipo {etiquetas[j]}", font=DISPLAY,
                   size=8.5, bold=True, color=ELECTRIC_DARK)
            marca = "X" if etiquetas[j] == tipo.upper() else ""
            _texto(c1.paragraphs[0], marca, size=10, bold=True, color=NAVY)


def _tabla_datos(doc: Document, filas: list[list[str]]) -> None:
    ncols = max(len(f) for f in filas)
    t = doc.add_table(rows=0, cols=ncols)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, fila in enumerate(filas):
        row = t.add_row()
        if i == 0:
            _row_header_repeat(row)
        for j in range(ncols):
            c = row.cells[j]
            valor = fila[j] if j < len(fila) else ""
            if i == 0:
                _cell_bg(c, ELECTRIC)
                _cell_borders(c, bottom=None)
                _texto(c.paragraphs[0], valor or "", font=DISPLAY, size=8.5,
                       bold=True, color="FFFFFF")
            else:
                _cell_borders(c)
                _texto(c.paragraphs[0], valor or "", size=9, color=BODY)


def _placeholder(doc: Document, texto: str) -> None:
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    _cell_bg(c, "F4FAFD")
    tc_pr = c._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for lado in ("top", "left", "right", "bottom"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "dashed")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), MUTED)
        borders.append(el)
    tc_pr.append(borders)
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = _texto(p, texto, size=8.5, color=CHIP_NO_FG)
    run.font.italic = True


_SUBTITULOS = ("Objetivo", "Condiciones y desarrollo de la prueba",
               "Señales requeridas", "Criterio de aceptación", "Resultados")


def _seccion_prueba(doc: Document, entrada: dict, cfg: dict,
                    proyecto: ProyectoProtocolo) -> None:
    numero = _numero_de(entrada["seccion"], cfg["offset_numero"])
    aplica = numero in proyecto.pruebas_aplican
    titulo = entrada["titulo"].strip()
    num_seccion = f"{cfg['capitulo']}.{entrada['seccion']}"

    if not aplica:
        _seccion(doc, num_seccion, f"{titulo} — NO APLICA", muted=True)
        nota = proyecto.notas.get(numero, "").strip()
        if nota:  # solo texto entregado por el usuario, nunca redactado aquí
            p = doc.add_paragraph()
            _texto(p, nota, size=9.5, color=MUTED)
        return

    _seccion(doc, num_seccion, titulo)
    for item in entrada.get("flujo", []):
        if item.get("tabla") == "aplicabilidad":
            _tabla_aplicabilidad(doc, proyecto.tipo)
        elif "placeholder" in item:
            _placeholder(doc, item["placeholder"].replace("CNK", proyecto.codigo or "CNK"))
        elif "tabla_datos" in item:
            _tabla_datos(doc, item["tabla_datos"])
        elif "estilo" in item:
            texto = item.get("texto", "").replace("CNK", proyecto.codigo or "CNK")
            if not texto.strip():
                continue
            p = doc.add_paragraph()
            if texto.strip() in _SUBTITULOS or item["estilo"] in ("Heading 3", "Subtitle"):
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.keep_with_next = True
                _texto(p, texto, font=DISPLAY, size=10.5, bold=True,
                       color=ELECTRIC_DARK)
            else:
                p.paragraph_format.space_after = Pt(3)
                _texto(p, texto, size=10, color=BODY)


def _pie_pagina(doc: Document, proyecto: ProyectoProtocolo) -> None:
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    etiqueta = " · ".join(x for x in (
        proyecto.proyecto or proyecto.nombre_central,
        "Protocolo de Pruebas", "Código de Red 2.0") if x)
    _texto(p, f"{etiqueta} · pág. ", size=8, color=LABEL)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    p._p.append(fld)


# ── entrada principal ───────────────────────────────────────────────────────
def generar_protocolo_v2(clase: str, proyecto: ProyectoProtocolo,
                         destino: Path) -> Path:
    """Genera el protocolo con el rediseño v2 (documento completo, editable).

    `clase`: 'central' (pruebas 21–45) o 'unidad' (pruebas 1–20).
    `destino`: carpeta o ruta .docx.
    """
    if clase not in _CFG:
        raise ValueError(f"clase debe ser 'central' o 'unidad', no {clase!r}")
    cfg = _CFG[clase]
    catalogo = _cargar_catalogo(clase)

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.2)

    alcance = ("Pruebas por Central" if clase == "central" else
               "Pruebas por Unidad")
    _banda_marca(doc)
    _eyebrow(doc, "Código de Red 2.0 · RES/550/2021 · Manual INTE · POC Anexo 5")
    _titulo(doc, proyecto)
    _ficha_datos(doc, proyecto, alcance)

    _seccion(doc, cfg["capitulo"],
             f"Pruebas por {'Central Eléctrica' if clase == 'central' else 'Unidad'}"
             " — Tabla maestra")
    _tabla_maestra(doc, proyecto, clase)

    doc.add_page_break()
    for entrada in catalogo["pruebas"]:
        if "grupo" in entrada:
            _seccion(doc, cfg["capitulo"], entrada["grupo"])
        else:
            _seccion_prueba(doc, entrada, cfg, proyecto)

    _pie_pagina(doc, proyecto)

    destino = Path(destino)
    if destino.suffix.lower() != ".docx":
        destino.mkdir(parents=True, exist_ok=True)
        destino = destino / f"Protocolo_{clase.capitalize()}_v2_{proyecto.codigo or 'GCV'}.docx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(destino))
    return destino
