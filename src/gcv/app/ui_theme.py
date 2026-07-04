"""Tema visual de la app: CSS global, cabecera y componentes de estado.

Paleta única del sistema (la misma de reportes y gráficas):
    tinta #1e2430 · primario #2a78d6 · marino #2a3f54 · superficie #f4f5f7
    estados: ok #0ca30c / falla #d03b3b / advertencia #b97e00 / neutro #6b6b68
"""

from __future__ import annotations

import base64
from pathlib import Path

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
  --ink:#1e2430; --ink-2:#5b6472; --navy:#2a3f54; --accent:#2a78d6;
  --surface:#f4f5f7; --card:#ffffff; --line:#e3e6ea;
  --ok-bg:#e4f4e4; --ok-fg:#0a5c0a; --fail-bg:#fbe7e7; --fail-fg:#8f1f1f;
  --warn-bg:#fdf2d8; --warn-fg:#7a5a00; --pend-bg:#ececec; --pend-fg:#4a4a4a;
}

/* tipografía y lienzo */
html, body, [class*="css"]{
  font-family:"Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
}
.stApp{background:var(--surface);}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:3.6rem; max-width:1200px;}

/* cabecera de la app */
.gcv-header{
  display:flex; align-items:center; gap:18px;
  background:linear-gradient(100deg,var(--navy) 0%,#33506e 55%,#3c6a99 100%);
  border-radius:14px; padding:18px 26px; margin-bottom:6px;
  box-shadow:0 6px 18px rgba(42,63,84,.25);
}
.gcv-header img{height:52px; border-radius:8px; background:#fff; padding:4px;}
.gcv-header .t{color:#fff; font-size:1.45rem; font-weight:700; line-height:1.2; margin:0;}
.gcv-header .s{color:#c7d5e4; font-size:.85rem; margin-top:3px;}
.gcv-header .badge{
  margin-left:auto; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.35);
  color:#fff; border-radius:20px; padding:5px 14px; font-size:.78rem; white-space:nowrap;
}

/* pestañas */
.stTabs [data-baseweb="tab-list"]{gap:6px; border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{
  background:transparent; border-radius:10px 10px 0 0; padding:10px 20px;
  color:var(--ink-2); font-weight:600;
}
.stTabs [aria-selected="true"]{background:var(--card); color:var(--navy);
  border:1px solid var(--line); border-bottom:2px solid var(--accent);}

/* tarjetas y expanders */
div[data-testid="stExpander"]{
  background:var(--card); border:1px solid var(--line); border-radius:12px;
  box-shadow:0 1px 4px rgba(30,36,48,.06); overflow:hidden;
}
div[data-testid="stExpander"] summary{font-weight:600; color:var(--navy);}
div[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card); border-radius:12px;
}

/* métricas como tarjetas */
div[data-testid="stMetric"]{
  background:var(--card); border:1px solid var(--line); border-left:4px solid var(--accent);
  border-radius:10px; padding:10px 14px; box-shadow:0 1px 4px rgba(30,36,48,.05);
}
div[data-testid="stMetric"] label{color:var(--ink-2); font-size:.8rem;}

/* botones */
.stButton>button, .stDownloadButton>button{
  border-radius:10px; font-weight:600; border:1px solid var(--line);
}
.stButton>button[kind="primary"]{
  background:var(--accent); border:none;
  box-shadow:0 3px 10px rgba(42,120,214,.35);
}

/* barra lateral */
section[data-testid="stSidebar"]{
  background:var(--navy);
}
section[data-testid="stSidebar"] *{color:#e8eef5;}
section[data-testid="stSidebar"] .sb-logo{display:flex; justify-content:center; margin:6px 0 2px;}
section[data-testid="stSidebar"] .sb-logo img{height:64px; background:#fff; border-radius:10px; padding:6px;}
section[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.2);}
section[data-testid="stSidebar"] div[data-baseweb="select"] *,
section[data-testid="stSidebar"] input{color:var(--ink) !important;}
section[data-testid="stSidebar"] small{color:#aebdcd;}

/* chips de estado */
.chip{display:inline-block; padding:4px 14px; border-radius:14px;
  font-weight:700; font-size:.78rem; letter-spacing:.02em; vertical-align:middle;}
.chip.ok{background:var(--ok-bg); color:var(--ok-fg);}
.chip.fail{background:var(--fail-bg); color:var(--fail-fg);}
.chip.warn{background:var(--warn-bg); color:var(--warn-fg);}
.chip.pend{background:var(--pend-bg); color:var(--pend-fg);}

/* tarjetas de resumen de resultados */
.gcv-sum{display:flex; gap:14px; flex-wrap:wrap; margin:4px 0 14px;}
.gcv-sum .card{flex:1; min-width:150px; background:var(--card);
  border:1px solid var(--line); border-radius:12px; padding:14px 18px;
  box-shadow:0 1px 4px rgba(30,36,48,.06);}
.gcv-sum .n{font-size:1.9rem; font-weight:800; line-height:1;}
.gcv-sum .l{font-size:.78rem; color:var(--ink-2); margin-top:4px;
  text-transform:uppercase; letter-spacing:.05em;}
.gcv-sum .ok .n{color:var(--ok-fg);} .gcv-sum .fail .n{color:var(--fail-fg);}
.gcv-sum .warn .n{color:var(--warn-fg);} .gcv-sum .pend .n{color:var(--pend-fg);}

/* tablas */
div[data-testid="stDataFrame"]{border:1px solid var(--line); border-radius:10px; overflow:hidden;}

/* nota al pie */
.gcv-foot{color:var(--ink-2); font-size:.78rem; margin-top:8px;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _logo_b64() -> str | None:
    logo = Path(__file__).resolve().parents[3] / "LOGO.png"
    if not logo.exists():
        return None
    return base64.b64encode(logo.read_bytes()).decode()


def header(subtitle: str, badge: str) -> None:
    logo = _logo_b64()
    img = f'<img src="data:image/png;base64,{logo}" alt="logo">' if logo else ""
    st.markdown(
        f"""<div class="gcv-header">{img}
        <div><p class="t">Verificación de pruebas — Código de Red</p>
        <div class="s">{subtitle}</div></div>
        <div class="badge">{badge}</div></div>""",
        unsafe_allow_html=True)


def sidebar_logo() -> None:
    logo = _logo_b64()
    if logo:
        st.sidebar.markdown(
            f'<div class="sb-logo"><img src="data:image/png;base64,{logo}"></div>',
            unsafe_allow_html=True)


def chip(status: str) -> str:
    clase, texto = STATUS_META.get(status, ("pend", status))
    return f'<span class="chip {clase}">{texto}</span>'


def summary_cards(counts: dict[str, int]) -> None:
    cards = "".join(
        f'<div class="card {STATUS_META.get(s, ("pend", s))[0]}">'
        f'<div class="n">{n}</div><div class="l">{STATUS_META.get(s, ("pend", s))[1]}</div></div>'
        for s, n in counts.items())
    st.markdown(f'<div class="gcv-sum">{cards}</div>', unsafe_allow_html=True)
