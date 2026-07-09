"""Tema visual de la app — sistema de tokens único del proyecto.

Plan de diseño (identidad de laboratorio de ingeniería eléctrica):
  Color   tinta #1e2430 · marino #2a3f54 · azul señal #2a78d6 ·
          superficie con sesgo azul #f3f5f8 · línea #e2e7ee ·
          semánticos ok/falla/advertencia (nunca se usan como acento)
  Tipo    Escala: título 1.35rem/700 · sección .78rem versalitas espaciadas
          (eyebrow) · cuerpo 1rem · datos tabulares con tabular-nums
  Layout  Banda de identidad compacta arriba; pestañas tipo píldora;
          tarjetas de radio 12 con línea 1px; estado como chip, no como texto.
La misma paleta rige informes HTML y gráficas (plots.SERIES).
"""

from __future__ import annotations

import streamlit as st

STATUS_META = {
    "CUMPLE": ("ok", "Cumple"),
    "NO_CUMPLE": ("fail", "No cumple"),
    "NO_EVALUABLE": ("warn", "No evaluable"),
    "PENDIENTE_DOCUMENTAL": ("pend", "Pendiente documental"),
}

_CSS = """
<style>
:root{
  --ink:#1e2430; --ink-2:#5a6473; --navy:#2a3f54; --navy-2:#33506e;
  --accent:#2a78d6; --accent-soft:#e8f0fb;
  --surface:#f3f5f8; --card:#ffffff; --line:#e2e7ee;
  --ok-bg:#e4f4e4; --ok-fg:#0a5c0a; --fail-bg:#fbe7e7; --fail-fg:#8f1f1f;
  --warn-bg:#fdf2d8; --warn-fg:#7a5a00; --pend-bg:#ececec; --pend-fg:#4a4a4a;
  --radius:12px;
}

/* lienzo y tipografía */
html, body, [class*="css"]{
  font-family:"Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
  color:var(--ink);
}
.stApp{background:var(--surface);}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:3.4rem; padding-bottom:3rem; max-width:1180px;}

h1,h2,h3{color:var(--navy); text-wrap:balance;}
div[data-testid="stMarkdownContainer"] h3{
  font-size:1.15rem; font-weight:700; margin-bottom:.4rem;}

/* banda de identidad */
.gcv-header{
  display:flex; align-items:center; gap:16px;
  background:linear-gradient(100deg,var(--navy) 0%,var(--navy-2) 60%,#3c6a99 100%);
  border-radius:14px; padding:14px 22px; margin-bottom:4px;
  box-shadow:0 4px 14px rgba(42,63,84,.22);
}
.gcv-header .gcv-emblem{display:flex;} .gcv-header .gcv-emblem svg{display:block;}
.gcv-header .t{color:#fff; font-size:1.35rem; font-weight:700; line-height:1.2; margin:0;}
.gcv-header .s{color:#c7d5e4; font-size:.82rem; margin-top:2px;}
.gcv-header .badge{
  margin-left:auto; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.3);
  color:#fff; border-radius:999px; padding:6px 16px; font-size:.78rem;
  font-weight:600; white-space:nowrap;
}

/* etiqueta de sección (eyebrow) */
.gcv-eyebrow{
  text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:700;
  color:var(--ink-2); margin:6px 0 2px; display:flex; align-items:center; gap:10px;}
.gcv-eyebrow::after{content:""; flex:1; height:1px; background:var(--line);}

/* pestañas tipo píldora */
.stTabs [data-baseweb="tab-list"]{gap:8px; border-bottom:none; margin:.35rem 0 .4rem;}
.stTabs [data-baseweb="tab"]{
  background:var(--card); border:1px solid var(--line); border-radius:999px;
  padding:8px 20px; color:var(--ink-2); font-weight:600; font-size:.92rem;
}
.stTabs [aria-selected="true"]{
  background:var(--navy); color:#fff !important; border-color:var(--navy);
}
.stTabs [aria-selected="true"] p{color:#fff !important;}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none;}

/* tarjetas: expanders y contenedores con borde */
div[data-testid="stExpander"]{
  background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
  box-shadow:0 1px 3px rgba(30,36,48,.05); overflow:hidden;
}
div[data-testid="stExpander"] summary{font-weight:600; color:var(--navy);}
div[data-testid="stExpander"] summary:hover{color:var(--accent);}
div[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card); border-radius:var(--radius);
}

/* métricas como tarjetas de dato */
div[data-testid="stMetric"]{
  background:var(--card); border:1px solid var(--line); border-left:4px solid var(--accent);
  border-radius:10px; padding:10px 14px; box-shadow:0 1px 3px rgba(30,36,48,.04);
}
div[data-testid="stMetric"] label{color:var(--ink-2); font-size:.78rem;}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{
  font-variant-numeric:tabular-nums;}

/* botones */
.stButton>button, .stDownloadButton>button{
  border-radius:10px; font-weight:600; border:1px solid var(--line);
  background:var(--card); color:var(--navy);
}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:var(--accent); color:var(--accent);}
.stButton>button[kind="primary"]{
  background:var(--accent); border:none; color:#fff;
  box-shadow:0 3px 10px rgba(42,120,214,.3);
}
.stButton>button[kind="primary"]:hover{background:#2569bd; color:#fff;}

/* zona de carga de archivos */
section[data-testid="stFileUploaderDropzone"]{
  background:var(--accent-soft); border:1.5px dashed var(--accent);
  border-radius:var(--radius);
}

/* chips de estado */
.chip{display:inline-block; padding:4px 14px; border-radius:999px;
  font-weight:700; font-size:.78rem; letter-spacing:.02em; vertical-align:middle;}
.chip.ok{background:var(--ok-bg); color:var(--ok-fg);}
.chip.fail{background:var(--fail-bg); color:var(--fail-fg);}
.chip.warn{background:var(--warn-bg); color:var(--warn-fg);}
.chip.pend{background:var(--pend-bg); color:var(--pend-fg);}

/* tarjetas de resumen */
.gcv-sum{display:flex; gap:14px; flex-wrap:wrap; margin:4px 0 14px;}
.gcv-sum .card{flex:1; min-width:150px; background:var(--card);
  border:1px solid var(--line); border-radius:var(--radius); padding:14px 18px;
  box-shadow:0 1px 3px rgba(30,36,48,.05);}
.gcv-sum .n{font-size:2rem; font-weight:800; line-height:1;
  font-variant-numeric:tabular-nums;}
.gcv-sum .l{font-size:.74rem; color:var(--ink-2); margin-top:5px;
  text-transform:uppercase; letter-spacing:.08em; font-weight:600;}
.gcv-sum .ok .n{color:var(--ok-fg);} .gcv-sum .fail .n{color:var(--fail-fg);}
.gcv-sum .warn .n{color:var(--warn-fg);} .gcv-sum .pend .n{color:var(--pend-fg);}

/* tablas */
div[data-testid="stDataFrame"]{border:1px solid var(--line);
  border-radius:10px; overflow:hidden;}

.gcv-foot{color:var(--ink-2); font-size:.78rem; margin:2px 0 10px;}

/* ── ajustes de acabado ─────────────────────────────────────────────── */
/* vista limpia: se oculta el cromo de Streamlit (toolbar/Deploy/menú/pie) */
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer{
  visibility:hidden; height:0;}

/* multiselección: fichas sobrias del sistema (no el azul saturado por defecto)
   — 24 pruebas deben leerse como un grupo tranquilo, no como un mosaico) */
span[data-baseweb="tag"]{
  background:#dce8fa !important; color:var(--navy) !important;
  border:1px solid rgba(42,120,214,.35) !important; border-radius:8px !important;
  font-weight:600 !important; box-shadow:none !important;}
span[data-baseweb="tag"] span{color:var(--navy) !important;}
span[data-baseweb="tag"] svg{fill:var(--navy-2) !important; opacity:.75;}
span[data-baseweb="tag"]:hover svg{opacity:1;}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div{
  border-radius:10px !important; border-color:var(--line) !important;}
div[data-baseweb="select"]>div:focus-within{
  border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(42,120,214,.15) !important;}

/* cabecera: emblema con placa translúcida y micro-jerarquía */
.gcv-header{align-items:center;}
.gcv-header .gcv-emblem{background:rgba(255,255,255,.10);
  border:1px solid rgba(255,255,255,.18); border-radius:12px; padding:6px;}
.gcv-header .badge{backdrop-filter:blur(2px);}

/* pestañas: realce inferior sutil en la activa + transición */
.stTabs [data-baseweb="tab"]{transition:all .15s ease;}
.stTabs [data-baseweb="tab"]:hover{border-color:var(--accent); color:var(--navy);}
.stTabs [aria-selected="true"]{box-shadow:0 3px 10px rgba(42,63,84,.22);}

/* botones de descarga: acento a la izquierda para lectura de "documento" */
.stDownloadButton>button{border-left:3px solid var(--accent);}

/* separadores y foco general más suaves */
hr{border-color:var(--line);}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# Emblema neutro del sistema: onda de frecuencia, sin marca comercial.
def _emblem(size: int, bg: str, fg: str) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="emblema">'
        f'<rect width="48" height="48" rx="11" fill="{bg}"/>'
        f'<path d="M6 30 L14 30 L18 16 L24 34 L28 22 L32 30 L42 30" '
        f'fill="none" stroke="{fg}" stroke-width="2.6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="24" cy="34" r="2.4" fill="{fg}"/></svg>')


def header(subtitle: str, badge: str) -> None:
    emblem = _emblem(48, "#1f3350", "#5fa8ff")
    st.markdown(
        f"""<div class="gcv-header"><span class="gcv-emblem">{emblem}</span>
        <div><p class="t">Verificación de pruebas — Código de Red</p>
        <div class="s">{subtitle}</div></div>
        <div class="badge">{badge}</div></div>""",
        unsafe_allow_html=True)


def eyebrow(texto: str) -> None:
    """Etiqueta de sección en versalitas con regla — jerarquía sin gritar."""
    st.markdown(f'<div class="gcv-eyebrow">{texto}</div>', unsafe_allow_html=True)


def chip(status: str) -> str:
    clase, texto = STATUS_META.get(status, ("pend", status))
    return f'<span class="chip {clase}">{texto}</span>'


def summary_cards(counts: dict[str, int]) -> None:
    cards = "".join(
        f'<div class="card {STATUS_META.get(s, ("pend", s))[0]}">'
        f'<div class="n">{n}</div><div class="l">{STATUS_META.get(s, ("pend", s))[1]}</div></div>'
        for s, n in counts.items())
    st.markdown(f'<div class="gcv-sum">{cards}</div>', unsafe_allow_html=True)
