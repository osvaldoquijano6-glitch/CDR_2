"""Gráficas Plotly base del sistema.

Convenciones (guía de visualización):
  * Nunca doble eje Y: señales de distinta magnitud (f y P) van en subgráficas
    apiladas con eje X compartido.
  * Colores por entidad, orden fijo: medición=azul, referencia/teórica=ámbar,
    señal secundaria=aqua. Límites normativos en rojo crítico discontinuo;
    bandas permitidas en gris neutro translúcido.
  * Marcas delgadas (líneas 2 px), retícula recesiva, tooltip unificado.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Paleta categórica validada (referencia dataviz, modo claro)
SERIES = {
    "medida": "#2a78d6",  # slot 1 azul
    "teorica": "#eda100",  # slot 3 ámbar
    "secundaria": "#1baf7a",  # slot 2 aqua
}
STATUS = {"cumple": "#0ca30c", "no_cumple": "#d03b3b", "neutro": "#6b6b68"}
BAND_FILL = "rgba(107,107,104,0.12)"  # banda permitida, gris translúcido
GRID = "#e8e7e4"


def _layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=60, r=30, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        font=dict(size=12),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def _line(x, y, name: str, color: str, dash: str | None = None) -> go.Scatter:
    return go.Scatter(
        x=x, y=y, name=name, mode="lines",
        line=dict(color=color, width=2, dash=dash),
    )


def stacked_timeseries(
    df: pd.DataFrame,
    panels: list[dict],
    title: str,
    time_col: str = "timestamp",
) -> go.Figure:
    """Subgráficas apiladas con eje X compartido (sustituye al doble eje).

    Cada panel: {"series": [(col|Series, nombre, rol)], "y_title": str,
                 "hlines": [(valor, etiqueta)], "bands": [(y0, y1, etiqueta)]}
    rol ∈ SERIES ("medida" | "teorica" | "secundaria").
    """
    rows = len(panels)
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    x = df[time_col]
    for i, panel in enumerate(panels, start=1):
        for data, nombre, rol in panel["series"]:
            y = df[data] if isinstance(data, str) else data
            dash = "dash" if rol == "teorica" else None
            fig.add_trace(_line(x, y, nombre, SERIES[rol], dash), row=i, col=1)
        for y0, y1, etiqueta in panel.get("bands", []):
            fig.add_hrect(y0=y0, y1=y1, fillcolor=BAND_FILL, line_width=0, row=i, col=1)
            fig.add_hline(y=y0, line=dict(color=STATUS["neutro"], width=1, dash="dot"),
                          row=i, col=1)
            fig.add_hline(y=y1, line=dict(color=STATUS["neutro"], width=1, dash="dot"),
                          annotation_text=etiqueta, annotation_font_size=10, row=i, col=1)
        for valor, etiqueta in panel.get("hlines", []):
            fig.add_hline(y=valor, line=dict(color=STATUS["no_cumple"], width=1.5, dash="dash"),
                          annotation_text=etiqueta, annotation_font_size=10, row=i, col=1)
        fig.update_yaxes(title_text=panel["y_title"], row=i, col=1)
    fig.update_layout(height=280 * rows + 80)
    return _layout(fig, title)


def limits_bar(
    measured: dict[str, float],
    limits: dict[str, float],
    title: str,
    y_title: str,
    measured_name: str = "Medido",
    limit_name: str = "Límite",
) -> go.Figure:
    """Barras medido-vs-límite (armónicos, flicker): barras finas + marcador de límite."""
    keys = list(measured.keys())
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=keys, y=[measured[k] for k in keys], name=measured_name,
        marker=dict(color=SERIES["medida"]), width=0.55,
    ))
    lim_x = [k for k in keys if k in limits]
    if lim_x:
        fig.add_trace(go.Scatter(
            x=lim_x, y=[limits[k] for k in lim_x], name=limit_name, mode="markers",
            marker=dict(symbol="line-ew", size=26,
                        line=dict(color=STATUS["no_cumple"], width=2.5)),
        ))
    fig.update_yaxes(title_text=y_title)
    fig.update_layout(height=380, bargap=0.35)
    return _layout(fig, title)


def scatter_xy(
    x: pd.Series, y: pd.Series, title: str, x_title: str, y_title: str,
    name: str = "Medido",
    curve: tuple[pd.Series, pd.Series, str] | None = None,
) -> go.Figure:
    """Dispersión (p. ej. P vs f, P-Q) con curva teórica opcional."""
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=x, y=y, name=name, mode="markers",
        marker=dict(color=SERIES["medida"], size=5, opacity=0.55)))
    if curve is not None:
        cx, cy, cname = curve
        fig.add_trace(_line(cx, cy, cname, SERIES["teorica"], dash="dash"))
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text=y_title)
    fig.update_layout(height=420)
    return _layout(fig, title)
