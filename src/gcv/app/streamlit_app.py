"""Borrador de interfaz Streamlit (FASE 4).

Flujo: proyecto → carga y normalización de archivos → selección de pruebas
aplicables → parámetros de protocolo → ejecución → resultados con evidencia →
exportación (Excel / HTML / Word / bitácora).

Ejecución:  PYTHONPATH=src streamlit run src/gcv/app/streamlit_app.py
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from gcv.config.settings import MATRIX_PATH
from gcv.evaluation.applicability import applicable_tests
from gcv.evaluation.registry import get_test, implemented_ids
from gcv.evaluation.spec import load_matrix
from gcv.ingestion.base import read_file
from gcv.models import Category, Installation, InstallationKind, SyncArea, Technology
from gcv.normalization.cleaning import ManualCorrections
from gcv.normalization.column_mapper import normalize
from gcv.reporting.context import ReportContext
from gcv.reporting.docx_report import export_docx
from gcv.reporting.excel import export_excel
from gcv.reporting.html_report import export_html
from gcv.visualization.evidence import build_figures
from gcv.app import ui_theme

st.set_page_config(page_title="Verificación Código de Red", layout="wide", page_icon="⚡")

_STATUS_ICON = {"CUMPLE": "✅", "NO_CUMPLE": "❌",
                "NO_EVALUABLE": "⚠️", "PENDIENTE_DOCUMENTAL": "📄"}

# Parámetros de protocolo sugeridos por prueba (el usuario los edita como JSON)
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


def _sidebar() -> Installation:
    ui_theme.sidebar_logo()
    st.sidebar.title("Proyecto")
    nombre = st.sidebar.text_input("Nombre del proyecto", "Proyecto de verificación")
    etiquetas = {"CENTRAL_ELECTRICA": "Central Eléctrica", "CENTRO_DE_CARGA": "Centro de Carga",
                 "SINCRONA": "Síncrona", "ASINCRONA": "Asíncrona", "MIXTA": "Mixta"}
    kind = st.sidebar.radio("Tipo de instalación", [k.value for k in InstallationKind],
                            format_func=etiquetas.get, horizontal=False)
    kwargs = {}
    if kind == InstallationKind.CENTRAL_ELECTRICA.value:
        kwargs["tech"] = Technology(st.sidebar.selectbox(
            "Tecnología", [t.value for t in Technology], format_func=etiquetas.get))
        kwargs["category"] = Category(st.sidebar.selectbox(
            "Categoría (A/B/C/D)", [c.value for c in Category], index=2))
        kwargs["area_sincrona"] = SyncArea(st.sidebar.selectbox(
            "Área síncrona", [a.value for a in SyncArea]))
    st.sidebar.caption(
        "La clasificación A–D debe corresponder al numeral del Manual INTER "
        "(pendiente de validación normativa).")
    return Installation(nombre=nombre, kind=InstallationKind(kind), **kwargs)


def _tab_datos(state: dict) -> None:
    st.subheader("Carga y normalización de archivos")
    col1, col2, col3 = st.columns(3)
    dayfirst = col1.selectbox("Formato de fecha", ["auto", "día/mes", "mes/día"])
    tz = col2.text_input("Zona horaria (opcional)", "")
    col3.caption("Los archivos COMTRADE se cargan por su .cfg (con el .dat junto).")

    uploads = st.file_uploader(
        "Excel (.xlsx/.xlsm), CSV o COMTRADE (.cfg + .dat)",
        accept_multiple_files=True, type=["xlsx", "xlsm", "csv", "cfg", "dat"])
    if uploads and st.button("Procesar archivos", type="primary"):
        tmpdir = Path(tempfile.mkdtemp(prefix="gcv_"))
        for up in uploads:  # guardar todo primero (COMTRADE necesita el par)
            (tmpdir / up.name).write_bytes(up.getbuffer())
        state["datasets"] = []
        corrections = ManualCorrections(
            dayfirst={"auto": None, "día/mes": True, "mes/día": False}[dayfirst],
            tz=tz or None)
        for up in uploads:
            if up.name.lower().endswith(".dat"):
                continue  # se procesa vía su .cfg
            try:
                ds = normalize(read_file(tmpdir / up.name), corrections=corrections)
                state["datasets"].append(ds)
            except Exception as exc:
                st.error(f"{up.name}: {exc}")
        state["results"], state["figs"] = {}, {}

    for i, ds in enumerate(state["datasets"]):
        q = ds.quality
        with st.expander(f"📄 {Path(ds.source_path).name} — {q.n_filas} filas, "
                         f"fs {q.fs_detectada_hz:.4g} Hz" if q.fs_detectada_hz
                         else f"📄 {Path(ds.source_path).name} — {q.n_filas} filas"):
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


def _tab_pruebas(state: dict, inst: Installation) -> None:
    st.subheader("Pruebas aplicables")
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
            st.warning(f"{tid}: en la matriz pero sin implementación aún (fase posterior).")
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

    if params_por_prueba and st.button("▶ Ejecutar análisis", type="primary"):
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
                if figs:  # repositorio histórico por central
                    from gcv.reporting.repositorio import guardar_figuras
                    guardar_figuras(inst.nombre, tid, figs, result.status.value)
            except Exception as exc:
                st.error(f"{tid}: {exc}")
            barra.progress(n / len(items))
        st.success(f"{len(state['results'])} pruebas ejecutadas. Ver pestaña Resultados.")


def _tab_resultados(state: dict) -> None:
    st.subheader("Resultados")
    if not state["results"]:
        st.info("Ejecuta pruebas en la pestaña Pruebas.")
        return
    resumen = {}
    for tid, (r, _) in state["results"].items():
        resumen[r.status.value] = resumen.get(r.status.value, 0) + 1
    ui_theme.summary_cards(resumen)

    for tid, (r, _) in state["results"].items():
        with st.expander(f"{_STATUS_ICON.get(r.status.value,'')} {tid} — {r.test_name} · "
                         f"{r.status.value.replace('_',' ')}", expanded=True):
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


def _tab_reportes(state: dict, inst: Installation) -> None:
    st.subheader("Exportar informes")
    if not state["results"]:
        st.info("Ejecuta pruebas antes de exportar.")
        return
    responsable = st.text_input("Responsable del informe", "")
    ctx = ReportContext(
        proyecto=inst.nombre, installation=inst,
        resultados=[r for r, _ in state["results"].values()],
        datasets=state["datasets"],
        figuras=state["figs"],
        responsable=responsable or None, fecha=datetime.now())

    # Descarga en un solo clic: los artefactos se generan al entrar a la pestaña
    # (el patrón botón→botón perdía el estado entre reruns y mostraba errores).
    outdir = Path(tempfile.mkdtemp(prefix="gcv_rep_"))
    with st.spinner("Generando informes..."):
        try:
            p_xlsx = export_excel(ctx, outdir / "matriz_cumplimiento.xlsx")
            p_html = export_html(ctx, outdir / "informe_tecnico.html")
            p_docx = export_docx(ctx, outdir / "informe_tecnico.docx")
        except Exception as exc:
            st.error(f"Error al generar informes: {exc}")
            return
    bitacora = json.dumps([json.loads(d.log.to_json()) for d in state["datasets"]],
                          indent=2, ensure_ascii=False)
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("📊 Excel (matriz)", p_xlsx.read_bytes(), p_xlsx.name,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
    c2.download_button("🌐 Informe HTML", p_html.read_bytes(), p_html.name,
                       "text/html", width="stretch")
    c3.download_button("📝 Informe Word", p_docx.read_bytes(), p_docx.name,
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       width="stretch")
    c4.download_button("🧾 Bitácora JSON", bitacora, "bitacora.json",
                       "application/json", width="stretch")
    st.caption("El informe HTML se abre en el navegador (doble clic). Las gráficas de "
               "cada corrida quedan además en el Histórico por central.")


def _tab_historico() -> None:
    from gcv.reporting.repositorio import cargar_figura, listar_centrales, listar_graficas

    st.subheader("Histórico de gráficas por central")
    centrales = listar_centrales()
    if not centrales:
        st.info("Aún no hay gráficas guardadas. Cada ejecución de pruebas guarda sus "
                "gráficas automáticamente en projects/<central>/graficas/.")
        return
    central = st.selectbox("Central", centrales)
    entradas = listar_graficas(central)
    pruebas = sorted({e["prueba"] for e in entradas})
    filtro = st.multiselect("Filtrar por prueba", pruebas, default=pruebas)
    entradas = [e for e in entradas if e["prueba"] in filtro]
    st.caption(f"{len(entradas)} gráficas · carpeta: projects/{central}/graficas/ "
               "(los .html se abren directo con doble clic)")
    for e in entradas[:60]:
        fecha = f"{e['fecha'][:4]}-{e['fecha'][4:6]}-{e['fecha'][6:8]} {e['fecha'][9:11]}:{e['fecha'][11:13]}"
        icono = {"CUMPLE": "✅", "NO_CUMPLE": "❌"}.get(e.get("resultado") or "", "⚠️")
        with st.expander(f"{icono} {fecha} · {e['prueba']} — {e['titulo']}"):
            if e.get("ruta_json") and Path(e["ruta_json"]).exists():
                st.plotly_chart(cargar_figura(e["ruta_json"]), width="stretch",
                                key=f"hist_{e['archivo']}")
            ruta = Path(e["ruta"])
            if ruta.exists():
                st.download_button("Descargar HTML autocontenible", ruta.read_bytes(),
                                   ruta.name, "text/html", key=f"dl_{e['archivo']}")


def main() -> None:
    ui_theme.inject_css()
    inst = _sidebar()
    state = _state()
    clasificacion = (f"Cat. {inst.category.value} · {inst.tech.value.title()}"
                     if inst.category and inst.tech else inst.kind.value.replace("_", " ").title())
    ui_theme.header(
        subtitle="Manual INTER · Manual CONE · POC/Anexo 5 — evaluación determinística y trazable",
        badge=f"{inst.nombre} — {clasificacion}")
    st.markdown('<p class="gcv-foot">Los criterios no validados documentalmente producen '
                'NO EVALUABLE: el sistema nunca inventa límites.</p>', unsafe_allow_html=True)
    tabs = st.tabs(["📥 Datos", "🧪 Pruebas", "📈 Resultados", "📤 Reportes", "📚 Histórico"])
    with tabs[0]:
        _tab_datos(state)
    with tabs[1]:
        _tab_pruebas(state, inst)
    with tabs[2]:
        _tab_resultados(state)
    with tabs[3]:
        _tab_reportes(state, inst)
    with tabs[4]:
        _tab_historico()


if __name__ == "__main__":
    main()
