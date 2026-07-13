"""Interfaz del sistema — reestructuración v3.

Tres módulos de trabajo (el flujo real del proyecto):

    1. Protocolos    Datos del proyecto + selección de pruebas (universo 1–45
                     del checklist del usuario) → genera Protocolo por Central,
                     Protocolo por Unidad, Checklist y Anexo de Revisiones en
                     los formatos EXACTOS de las plantillas del usuario.
    2. Gráficas      Carga de mediciones, ejecución de pruebas y evidencia
                     gráfica con veredicto normativo; exporta informes.
    3. Repositorio   Histórico de gráficas por central, manuales HTML de
                     apoyo, figuras normativas y reapertura de proyectos.

Sin barra lateral: todo el ancho disponible para trabajar (el estado del
proyecto vive arriba, siempre visible).

Ejecución:  PYTHONPATH=src streamlit run src/gcv/app/streamlit_app.py
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from gcv.app import ui_theme
from gcv.config.settings import MATRIX_PATH, NORMATIVE_DIR
from gcv.evaluation.applicability import applicable_tests
from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.spec import load_matrix
from gcv.ingestion.base import read_file
from gcv.models import Installation, InstallationKind, SyncArea, Technology
from gcv.normalization.cleaning import ManualCorrections
from gcv.normalization.column_mapper import normalize
from gcv.protocolos import (ProyectoProtocolo, generar_checklist,
                            generar_protocolo, generar_revisiones,
                            universo_pruebas)
from gcv.reporting.context import ReportContext
from gcv.reporting.docx_report import export_docx
from gcv.reporting.excel import export_excel
from gcv.reporting.html_report import export_html
from gcv.reporting.pdf_report import export_pdf, pdf_disponible
from gcv.visualization.evidence import build_figures

st.set_page_config(page_title="Código de Red — Protocolos y Verificación",
                   layout="wide", initial_sidebar_state="collapsed")

_X = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_W = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_STATUS_TXT = {"CUMPLE": "CUMPLE", "NO_CUMPLE": "NO CUMPLE",
               "NO_EVALUABLE": "NO EVALUABLE", "PENDIENTE_DOCUMENTAL": "PENDIENTE"}

_PARAM_HINTS = {
    "CE-F-03": {"estatismo": 0.05, "p_ref_mw": 100.0},
    "CE-F-04": {"estatismo": 0.05, "p_ref_mw": 100.0},
    "CE-F-05": {"estatismo": 0.05, "p_ref_mw": 100.0},
    "CE-V-01": {"v_base_v": 230000.0},
    "CE-P-01": {"capacidad_declarada_mw": 100.0},
    "CE-Q-03": {"v_nominal_v": 230000.0},
}


def _state() -> dict:
    if "gcv" not in st.session_state:
        st.session_state.gcv = {"datasets": [], "results": {}, "figs": {}}
    return st.session_state.gcv


@st.cache_resource
def _matrix():
    return load_matrix(MATRIX_PATH)


@st.cache_data
def _universo() -> pd.DataFrame:
    filas = universo_pruebas()
    return pd.DataFrame(filas)


# ────────────────────────────── Módulo 1: Protocolos ──────────────────────────


def _form_proyecto() -> ProyectoProtocolo:
    ui_theme.eyebrow("Datos del proyecto")
    c1, c2, c3, c4 = st.columns([3, 1.2, 1, 1.4])
    nombre = c1.text_input("Nombre de la central",
                           st.session_state.get("p_nombre", "Central Eléctrica"),
                           key="p_nombre")
    codigo = c2.text_input("Código corto", st.session_state.get("p_codigo", "GCV"),
                           key="p_codigo", max_chars=8,
                           help="Sustituye la clave del proyecto en encabezados (p.ej. CNK)")
    tipo = c3.selectbox("Tipo", ["A", "B", "C", "D"], index=1, key="p_tipo")
    tecnologia = c4.selectbox("Tecnología", ["SINCRONA", "ASINCRONA"],
                              format_func={"SINCRONA": "Síncrona",
                                           "ASINCRONA": "Asíncrona"}.get,
                              key="p_tec")
    c5, c6, c7, c8 = st.columns([2, 2, 1.4, 1.4])
    proyecto_id = c5.text_input("Identificador de proyecto",
                                st.session_state.get("p_id", ""), key="p_id",
                                placeholder="GCE310_CNK_Caterpillar")
    ubicacion = c6.text_input("Ubicación", st.session_state.get("p_ubic", ""),
                              key="p_ubic", placeholder="Ciudad, Estado, México")
    fecha_pruebas = c7.text_input("Fecha de pruebas", key="p_fp",
                                  placeholder="Abril–Mayo 2026")
    fecha_envio = c8.text_input("Fecha de envío", key="p_fe",
                                placeholder="Julio 2026")
    return ProyectoProtocolo(
        nombre_central=nombre, codigo=codigo, proyecto=proyecto_id,
        tipo=tipo, tecnologia=tecnologia, ubicacion=ubicacion,
        fecha_pruebas=fecha_pruebas, fecha_envio=fecha_envio)


def _editor_pruebas() -> tuple[set[int], dict[int, str], dict[int, str]]:
    """Selección del universo 1–45 con todo el ancho de la pantalla."""
    ui_theme.eyebrow("Selección de pruebas — universo Anexo 5 (1–45)")
    st.caption("Los valores iniciales son los del Checklist REV 1.1. "
               "Edita APLICA y los comentarios; el criterio y el tipo son informativos.")
    df = _universo().copy()
    df["comentario"] = ""
    df = df[["numero", "nombre", "criterio", "tipo", "aplica", "ejecutar", "comentario"]]

    bloques = {
        "Pruebas por unidad (1–20)": df[df.numero <= 20],
        "Pruebas por central, preoperativas y de desempeño (21–45)": df[df.numero > 20],
    }
    editados = []
    for titulo, bloque in bloques.items():
        st.markdown(f"**{titulo}**")
        editados.append(st.data_editor(
            bloque,
            key=f"ed_{titulo[:18]}",
            width="stretch",
            height=min(60 + 42 * len(bloque), 700),
            hide_index=True,
            disabled=["numero", "nombre", "criterio", "tipo"],
            column_config={
                "numero": st.column_config.NumberColumn("No.", width="small"),
                "nombre": st.column_config.TextColumn("Prueba", width="medium"),
                "criterio": st.column_config.TextColumn("Criterio de aceptación",
                                                        width="large"),
                "tipo": st.column_config.TextColumn("Tipo", width="small"),
                "aplica": st.column_config.SelectboxColumn(
                    "Aplica", options=["SI", "No Aplica",
                                       "No se cuenta con la infraestructura"],
                    width="small"),
                "ejecutar": st.column_config.SelectboxColumn(
                    "¿Se puede ejecutar?", options=["SI", "NO", "Pendiente", "N/A"],
                    width="small"),
                "comentario": st.column_config.TextColumn("Comentarios REV₁",
                                                          width="medium"),
            }))
    total = pd.concat(editados, ignore_index=True)
    aplican = {int(r.numero) for r in total.itertuples() if str(r.aplica).upper() == "SI"}
    notas = {int(r.numero): str(r.aplica) for r in total.itertuples()
             if str(r.aplica) not in ("SI", "No Aplica")}
    estado = {"aplica": {int(r.numero): str(r.aplica) for r in total.itertuples()},
              "ejecutar": {int(r.numero): str(r.ejecutar) for r in total.itertuples()},
              "coment": {int(r.numero): str(r.comentario) for r in total.itertuples()
                         if str(r.comentario).strip()}}
    st.caption(f"{len(aplican)} de {len(total)} pruebas aplican.")
    return aplican, notas, estado


def _modulo_protocolos() -> None:
    proyecto = _form_proyecto()
    st.divider()
    aplican, notas, estado = _editor_pruebas()
    proyecto.pruebas_aplican = aplican
    proyecto.notas = notas

    st.divider()
    ui_theme.eyebrow("Generación de documentos — formato de las plantillas del usuario")
    outdir = Path(tempfile.mkdtemp(prefix="gcv_prot_"))
    c1, c2, c3, c4 = st.columns(4)

    if c1.button("Generar Protocolo por Central", type="primary", width="stretch"):
        with st.spinner("Generando desde la plantilla…"):
            ruta = generar_protocolo("central", proyecto, outdir)
        st.session_state["dl_central"] = (ruta.name, ruta.read_bytes())
    if c2.button("Generar Protocolo por Unidad", type="primary", width="stretch"):
        with st.spinner("Generando desde la plantilla…"):
            ruta = generar_protocolo("unidad", proyecto, outdir)
        st.session_state["dl_unidad"] = (ruta.name, ruta.read_bytes())
    if c3.button("Generar Checklist", width="stretch"):
        ruta = generar_checklist(
            outdir / f"Checklist_de_Pruebas_{proyecto.codigo}.xlsx",
            aplica=estado["aplica"], ejecutar=estado["ejecutar"],
            comentarios_rev1=estado["coment"])
        st.session_state["dl_checklist"] = (ruta.name, ruta.read_bytes())
    if c4.button("Generar Anexo de Revisiones", width="stretch"):
        ruta = generar_revisiones(
            outdir / f"Anexo_Revisiones_{proyecto.codigo}.xlsx",
            proyecto=f"{proyecto.nombre_central} — {proyecto.proyecto}".strip(" —"))
        st.session_state["dl_revisiones"] = (ruta.name, ruta.read_bytes())

    descargas = [("dl_central", "Protocolo por Central (.docx)", _W),
                 ("dl_unidad", "Protocolo por Unidad (.docx)", _W),
                 ("dl_checklist", "Checklist de Pruebas (.xlsx)", _X),
                 ("dl_revisiones", "Anexo de Revisiones (.xlsx)", _X)]
    listos = [(k, et, mime) for k, et, mime in descargas if k in st.session_state]
    if listos:
        cols = st.columns(len(listos))
        for col, (k, etiqueta, mime) in zip(cols, listos):
            nombre, datos = st.session_state[k]
            col.download_button(f"Descargar {etiqueta}", datos, nombre, mime,
                                width="stretch", key=f"btn_{k}")
    st.caption("El documento sale de la plantilla original: portada, estilos, "
               "encabezados y tablas idénticos; solo cambian los datos del proyecto, "
               "la columna APLICA y las secciones de pruebas seleccionadas.")

    with st.expander("Centro de Carga — Plan de Trabajo CRE"):
        _plan_trabajo_cc()


def _plan_trabajo_cc() -> None:
    from gcv.reporting.documentos_iniciales import generar_plan_trabajo

    c1, c2 = st.columns([3, 1.4])
    nombre = c1.text_input("Nombre del Centro de Carga", "Centro de Carga")
    tension = c2.number_input("Tensión en el POI (kV)", min_value=1.0, value=115.0)
    if st.button("Generar Plan de Trabajo CRE (.docx)"):
        inst = Installation(nombre=nombre, kind=InstallationKind.CENTRO_DE_CARGA,
                            tension_poi_kv=tension)
        outdir = Path(tempfile.mkdtemp(prefix="gcv_cc_"))
        ruta = generar_plan_trabajo(inst, outdir)
        st.download_button("Descargar Plan de Trabajo", ruta.read_bytes(),
                           ruta.name, _W)


# ────────────────────────────── Módulo 2: Gráficas ────────────────────────────


def _config_instalacion() -> Installation:
    """Clasificación de la central para la aplicabilidad de las pruebas."""
    from gcv.evaluation.applicability import clasificar_central

    ui_theme.eyebrow("Clasificación de la instalación")
    c1, c2, c3, c4 = st.columns([2.4, 1.4, 1.4, 1.4])
    nombre = c1.text_input("Central / proyecto",
                           st.session_state.get("p_nombre", "Central Eléctrica"),
                           key="g_nombre")
    tech = Technology(c2.selectbox(
        "Tecnología", [t.value for t in Technology],
        format_func={"SINCRONA": "Síncrona", "ASINCRONA": "Asíncrona",
                     "MIXTA": "Mixta"}.get, key="g_tec"))
    area = SyncArea(c3.selectbox("Área síncrona", [a.value for a in SyncArea],
                                 key="g_area"))
    cin = c4.number_input("Capacidad neta (MW)", min_value=0.0, value=30.0,
                          step=0.5, key="g_cin")
    categoria = clasificar_central(area.value, cin)
    st.caption(f"Clasificación automática: **Tipo {categoria.value}** "
               f"(Tabla 1.1 Manual INTE · {cin:g} MW · {area.value})")
    return Installation(nombre=nombre, kind=InstallationKind.CENTRAL_ELECTRICA,
                        tech=tech, area_sincrona=area,
                        capacidad_instalada_neta_mw=cin, category=categoria)


def _seccion_datos(state: dict) -> None:
    c1, c2, c3 = st.columns(3)
    dayfirst = c1.selectbox("Formato de fecha", ["auto", "día/mes", "mes/día"])
    tz = c2.text_input("Zona horaria (opcional)", "")
    c3.caption("Los archivos COMTRADE se cargan por su .cfg (con el .dat junto).")

    uploads = st.file_uploader(
        "Excel (.xlsx/.xlsm), CSV o COMTRADE (.cfg + .dat)",
        accept_multiple_files=True, type=["xlsx", "xlsm", "csv", "cfg", "dat"])
    if uploads and st.button("Procesar archivos", type="primary"):
        tmpdir = Path(tempfile.mkdtemp(prefix="gcv_"))
        for up in uploads:
            (tmpdir / up.name).write_bytes(up.getbuffer())
        state["datasets"] = []
        corrections = ManualCorrections(
            dayfirst={"auto": None, "día/mes": True, "mes/día": False}[dayfirst],
            tz=tz or None)
        for up in uploads:
            if up.name.lower().endswith(".dat"):
                continue
            try:
                ds = normalize(read_file(tmpdir / up.name), corrections=corrections)
                state["datasets"].append(ds)
            except Exception as exc:
                st.error(f"{up.name}: {exc}")
        state["results"], state["figs"] = {}, {}

    for ds in state["datasets"]:
        q = ds.quality
        titulo = f"{Path(ds.source_path).name} — {q.n_filas} filas"
        if q.fs_detectada_hz:
            titulo += f", fs {q.fs_detectada_hz:.4g} Hz"
        with st.expander(titulo):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Duplicados", q.timestamps_duplicados)
            c2.metric("Huecos", len(q.huecos))
            c3.metric("No monotónicos", q.saltos_no_monotonicos)
            c4.metric("Señales", len(ds.mappings))
            st.dataframe(pd.DataFrame(
                [{"columna original": m.columna_original, "señal": m.senal_canonica,
                  "unidad": m.unidad_original or "—", "factor": m.factor_conversion,
                  "método": m.metodo.value, "confianza": m.confianza}
                 for m in ds.mappings]), width="stretch")
            st.dataframe(ds.df.head(50), width="stretch")
            with st.expander("Bitácora de limpieza"):
                st.json(json.loads(ds.log.to_json()))


def _seccion_ejecucion(state: dict, inst: Installation) -> None:
    if not state["datasets"]:
        st.info("Primero carga y procesa archivos en la pestaña Datos.")
        return
    matrix = _matrix()
    impl = set(implemented_ids())
    decisiones = [d for d in applicable_tests(matrix, inst) if d.aplica]
    opciones = {}
    for d in decisiones:
        etiqueta = f"{d.spec.id} — {d.spec.nombre}"
        if d.spec.id not in impl:
            etiqueta += " (sin implementación)"
        elif d.dudosa:
            etiqueta += " (aplicabilidad por confirmar)"
        opciones[etiqueta] = d.spec.id
    elegidas = st.multiselect(
        "Pruebas a ejecutar", list(opciones),
        default=[e for e, tid in opciones.items() if tid in impl][:5])

    ds_labels = {f"{Path(d.source_path).name}": i for i, d in enumerate(state["datasets"])}
    params_por_prueba: dict[str, tuple[int, dict]] = {}
    for etiqueta in elegidas:
        tid = opciones[etiqueta]
        if tid not in impl:
            st.warning(f"{tid}: en la matriz pero sin implementación aún.")
            continue
        with st.container(border=True):
            st.markdown(f"**{etiqueta}**")
            c1, c2 = st.columns([1, 2])
            src = c1.selectbox("Archivo", list(ds_labels), key=f"src_{tid}")
            hint = json.dumps(_PARAM_HINTS.get(tid, {}))
            raw = c2.text_input("Parámetros del protocolo (JSON)", hint, key=f"par_{tid}")
            try:
                params = json.loads(raw) if raw.strip() else {}
                params_por_prueba[tid] = (ds_labels[src], params)
            except json.JSONDecodeError as exc:
                st.error(f"JSON inválido: {exc}")

    if params_por_prueba and st.button("Ejecutar análisis", type="primary"):
        state["results"], state["figs"] = {}, {}
        barra = st.progress(0.0)
        items = list(params_por_prueba.items())
        for n, (tid, (ds_idx, params)) in enumerate(items, start=1):
            ds = state["datasets"][ds_idx]
            try:
                result = get_test(tid, matrix).run(ds, params)
                state["results"][tid] = (result, ds_idx)
                figs = build_figures(result, ds)
                state["figs"][tid] = figs
                if figs:
                    from gcv.reporting.repositorio import guardar_figuras
                    guardar_figuras(inst.nombre, tid, figs, result.status.value)
            except Exception as exc:
                st.error(f"{tid}: {exc}")
            barra.progress(n / len(items))
        st.success(f"{len(state['results'])} pruebas ejecutadas. "
                   "Revisa la pestaña Resultados.")


def _seccion_resultados(state: dict) -> None:
    if not state["results"]:
        st.info("Ejecuta pruebas en la pestaña Ejecución.")
        return
    resumen = {}
    for tid, (r, _) in state["results"].items():
        resumen[r.status.value] = resumen.get(r.status.value, 0) + 1
    ui_theme.summary_cards(resumen)

    for tid, (r, _) in state["results"].items():
        with st.expander(f"{tid} — {r.test_name} · "
                         f"[{_STATUS_TXT.get(r.status.value, r.status.value)}]",
                         expanded=True):
            refs = "; ".join(f"{n.documento} {n.numeral or '(numeral pendiente)'}"
                             for n in r.normative_reference) or "—"
            st.markdown(ui_theme.chip(r.status.value), unsafe_allow_html=True)
            st.caption(f"Referencia: {refs} · Estado del criterio: {r.estado_normativo}")
            fmt = lambda v: "—" if v is None else f"{v:.6g}"  # noqa: E731
            if r.pass_fail_details:
                st.dataframe(pd.DataFrame([{
                    "criterio": c.nombre, "medido": fmt(c.valor_medido),
                    "límite": f"{c.comparacion or ''} {fmt(c.limite)}",
                    "unidad": c.unidad or "",
                    "cumple": {True: "SÍ", False: "NO"}.get(c.cumple, "NO EVALUABLE"),
                    "detalle": c.detalle or ""} for c in r.pass_fail_details]),
                    width="stretch")
            if r.measured_values:
                st.dataframe(pd.DataFrame([{
                    "variable": m.nombre, "valor": fmt(m.valor), "unidad": m.unidad or "",
                    "detalle": m.detalle or ""} for m in r.measured_values]),
                    width="stretch")
            for w in r.warnings:
                st.warning(w)
            for fig in state["figs"].get(tid, []):
                st.plotly_chart(fig, width="stretch")
            st.markdown(f"**Conclusión:** {r.conclusion}")


def _seccion_informes(state: dict, inst: Installation) -> None:
    if not state["results"]:
        st.info("Ejecuta pruebas antes de exportar.")
        return
    responsable = st.text_input("Responsable del informe", "")
    ctx = ReportContext(
        proyecto=inst.nombre, installation=inst,
        resultados=[r for r, _ in state["results"].values()],
        datasets=state["datasets"], figuras=state["figs"],
        responsable=responsable or None, fecha=datetime.now())

    outdir = Path(tempfile.mkdtemp(prefix="gcv_rep_"))
    p_pdf = None
    with st.spinner("Generando informes…"):
        try:
            p_xlsx = export_excel(ctx, outdir / "matriz_cumplimiento.xlsx")
            p_html = export_html(ctx, outdir / "informe_tecnico.html")
            p_docx = export_docx(ctx, outdir / "informe_tecnico.docx")
        except Exception as exc:
            st.error(f"Error al generar informes: {exc}")
            return
        if pdf_disponible():
            try:
                p_pdf = export_pdf(ctx, outdir / "informe_tecnico.pdf")
            except Exception:
                p_pdf = None
    bitacora = json.dumps([json.loads(d.log.to_json()) for d in state["datasets"]],
                          indent=2, ensure_ascii=False)
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("Excel — matriz de cumplimiento", p_xlsx.read_bytes(),
                       p_xlsx.name, _X, width="stretch")
    c2.download_button("Informe técnico HTML", p_html.read_bytes(), p_html.name,
                       "text/html", width="stretch")
    c3.download_button("Informe técnico Word", p_docx.read_bytes(), p_docx.name,
                       _W, width="stretch")
    c4.download_button("Bitácora JSON", bitacora, "bitacora.json",
                       "application/json", width="stretch")
    if p_pdf is not None:
        st.download_button("Informe técnico PDF", p_pdf.read_bytes(), p_pdf.name,
                           "application/pdf", width="stretch")
    else:
        st.caption("PDF no disponible en este entorno (sin Chromium/weasyprint); "
                   "el informe HTML es autocontenido.")

    st.divider()
    st.write("Guarda esta corrida (instalación, resultados y gráficas) para "
             "reabrirla después desde el Repositorio.")
    if st.button("Guardar proyecto", type="primary"):
        from gcv.persistence import guardar_proyecto

        carpeta = guardar_proyecto(
            inst, [r for r, _ in state["results"].values()], state["datasets"],
            figuras=state["figs"],
            result_ds_index={tid: idx for tid, (_, idx) in state["results"].items()},
            responsable=responsable or None)
        st.success(f"Proyecto guardado en {carpeta}")


def _modulo_graficas(state: dict) -> None:
    inst = _config_instalacion()
    st.divider()
    sub = st.tabs(["Datos", "Ejecución", "Resultados", "Informes"])
    with sub[0]:
        _seccion_datos(state)
    with sub[1]:
        _seccion_ejecucion(state, inst)
    with sub[2]:
        _seccion_resultados(state)
    with sub[3]:
        _seccion_informes(state, inst)


# ───────────────────────────── Módulo 3: Repositorio ──────────────────────────


def _seccion_historico() -> None:
    from gcv.reporting.repositorio import (cargar_figura, listar_centrales,
                                           listar_graficas)

    centrales = listar_centrales()
    if not centrales:
        st.info("Aún no hay gráficas guardadas. Cada ejecución guarda las suyas "
                "en projects/<central>/graficas/.")
        return
    c1, c2 = st.columns([1.4, 3])
    central = c1.selectbox("Central", centrales)
    entradas = listar_graficas(central)
    pruebas = sorted({e["prueba"] for e in entradas})
    filtro = c2.multiselect("Filtrar por prueba", pruebas, default=pruebas)
    entradas = [e for e in entradas if e["prueba"] in filtro]
    st.caption(f"{len(entradas)} gráficas · projects/{central}/graficas/ "
               "(los .html se abren directo con doble clic)")
    for e in entradas[:60]:
        fecha = (f"{e['fecha'][:4]}-{e['fecha'][4:6]}-{e['fecha'][6:8]} "
                 f"{e['fecha'][9:11]}:{e['fecha'][11:13]}")
        estado = _STATUS_TXT.get(e.get("resultado") or "", "")
        with st.expander(f"{fecha} · {e['prueba']} — {e['titulo']}"
                         + (f" [{estado}]" if estado else "")):
            if e.get("ruta_json") and Path(e["ruta_json"]).exists():
                st.plotly_chart(cargar_figura(e["ruta_json"]), width="stretch",
                                key=f"hist_{e['archivo']}")
            ruta = Path(e["ruta"])
            if ruta.exists():
                st.download_button("Descargar HTML autocontenible", ruta.read_bytes(),
                                   ruta.name, "text/html", key=f"dl_{e['archivo']}")


def _seccion_manuales() -> None:
    """HTML de apoyo: manuales de referencia con tablas y datos de pruebas."""
    carpeta = NORMATIVE_DIR / "fuentes" / "manuales"
    titulos = {
        "01_manual_puesta_en_servicio.html": "Manual 1 — Pruebas de puesta en servicio (Centrales)",
        "02_manual_operacion_desempeno.html": "Manual 2 — Pruebas de operación y desempeño",
        "03_manual_centro_de_carga.html": "Manual 3 — Centros de Carga",
    }
    archivos = sorted(carpeta.glob("*.html")) if carpeta.exists() else []
    if not archivos:
        st.info("No hay manuales HTML en normative/fuentes/manuales/.")
        return
    st.caption("Referencias de apoyo con tablas, límites y datos por prueba. "
               "Se pueden consultar aquí o descargar (autocontenidos).")
    nombres = {titulos.get(a.name, a.name): a for a in archivos}
    elegido = st.selectbox("Manual", list(nombres))
    ruta = nombres[elegido]
    c1, _ = st.columns([1.2, 3])
    c1.download_button("Descargar HTML", ruta.read_bytes(), ruta.name, "text/html",
                       width="stretch")
    st.iframe(ruta, height=760)


def _seccion_figuras_normativas() -> None:
    from gcv.reporting.figuras_normativas import TITULOS

    carpeta = NORMATIVE_DIR / "figuras"
    st.caption("Figuras oficiales del Código de Red 2.0 / Manual INTE que se "
               "insertan en protocolos e informes.")
    cols = st.columns(3)
    for i, (nombre, titulo) in enumerate(TITULOS.items()):
        ruta = carpeta / f"{nombre}.png"
        if ruta.exists():
            with cols[i % 3]:
                st.image(str(ruta), caption=titulo, width="stretch")


def _seccion_reabrir(state: dict) -> None:
    from gcv.config.settings import PROJECTS_DIR
    from gcv.persistence import cargar_proyecto, listar_proyectos

    proyectos = listar_proyectos()
    if not proyectos:
        st.info("No hay proyectos guardados todavía (Gráficas → Informes → "
                "Guardar proyecto).")
        return
    etiquetas = {p["slug"]: f"{p['nombre']} · {(p['guardado'] or '')[:16]}"
                 for p in proyectos}
    c1, c2 = st.columns([2.4, 1])
    slug = c1.selectbox("Corrida guardada", list(etiquetas),
                        format_func=etiquetas.get, key="reabrir_slug")
    if c2.button("Cargar corrida", type="primary", width="stretch"):
        pj = cargar_proyecto(PROJECTS_DIR / slug)
        state["datasets"] = pj.datasets
        state["results"] = {r.test_id: (r, pj.result_ds_index.get(r.test_id, 0))
                            for r in pj.resultados}
        state["figs"] = pj.figuras
        st.success(f"Cargado: {pj.installation.nombre} ({len(pj.resultados)} pruebas). "
                   "Revisa Gráficas → Resultados e Informes.")


def _modulo_repositorio(state: dict) -> None:
    sub = st.tabs(["Histórico de gráficas", "Manuales de apoyo (HTML)",
                   "Figuras normativas", "Reabrir proyecto"])
    with sub[0]:
        _seccion_historico()
    with sub[1]:
        _seccion_manuales()
    with sub[2]:
        _seccion_figuras_normativas()
    with sub[3]:
        _seccion_reabrir(state)


# ──────────────────────────────────── main ────────────────────────────────────


def main() -> None:
    ui_theme.inject_css()
    state = _state()
    ui_theme.header(
        subtitle="Protocolos · Gráficas de pruebas · Repositorio — "
                 "Código de Red 2.0, Manual INTE, POC/Anexo 5",
        badge=st.session_state.get("p_nombre", "Proyecto"))

    modulos = st.tabs(["1 · Protocolos", "2 · Gráficas de pruebas",
                       "3 · Repositorio"])
    with modulos[0]:
        _modulo_protocolos()
    with modulos[1]:
        _modulo_graficas(state)
    with modulos[2]:
        _modulo_repositorio(state)


if __name__ == "__main__":
    main()
