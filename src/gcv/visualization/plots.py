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


INK = "#1e2430"


def _plateaus(series: pd.Series, min_len: int = 3) -> list[tuple[int, int, float]]:
    """Mesetas de una señal escalonada: (idx_inicio, idx_fin, valor)."""
    s = pd.to_numeric(series, errors="coerce").round(6)
    grupos = (s != s.shift()).cumsum()
    out = []
    for _, idx in s.groupby(grupos).groups.items():
        if len(idx) >= min_len and pd.notna(s.loc[idx[0]]):
            out.append((idx[0], idx[-1], float(s.loc[idx[0]])))
    return out


def _seleccionar(plateaus: list, max_n: int) -> list:
    """Si hay más mesetas que presupuesto de etiquetas: primera, última y equiespaciadas."""
    if len(plateaus) <= max_n:
        return plateaus
    paso = (len(plateaus) - 1) / (max_n - 1)
    indices = sorted({round(i * paso) for i in range(max_n)})
    return [plateaus[i] for i in indices]


def annotate_steps(
    fig: go.Figure,
    x: pd.Series,
    exc: pd.Series,
    resp: pd.Series | None,
    exc_fmt: str = "{:.2f} Hz",
    resp_fmt: str = "{:.2f} MW",
    max_labels: int = 8,
    exc_yref: str = "y",
    resp_yref: str = "y2",
    row: int | None = None,
) -> int:
    """Etiqueta cada escalón: valor de la excitación al centro de la meseta
    (arriba/abajo alternado para no encimarse) y valor asentado de la
    respuesta al final de la meseta (offset contrario). Devuelve el número de
    mesetas etiquetadas."""
    mesetas = _seleccionar(_plateaus(exc), max_labels)
    kw = dict(row=row, col=1) if row is not None else {}
    for n, (i0, i1, valor) in enumerate(mesetas):
        centro = x.loc[i0:i1].iloc[len(x.loc[i0:i1]) // 2]
        arriba = n % 2 == 0
        fig.add_annotation(
            x=centro, y=valor, yref=exc_yref,
            text=f"<b>{exc_fmt.format(valor)}</b>",
            showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=SERIES["medida"],
            ax=0, ay=-30 if arriba else 30,
            font=dict(size=11, color=SERIES["medida"]),
            bgcolor="rgba(255,255,255,0.85)", bordercolor=SERIES["medida"],
            borderwidth=1, borderpad=3, **kw)
        if resp is not None:
            r = pd.to_numeric(resp.loc[i0:i1], errors="coerce").dropna()
            if not r.empty:
                asentada = float(r.tail(max(len(r) // 3, 1)).median())
                fig.add_annotation(
                    x=x.loc[i1], y=asentada, yref=resp_yref,
                    text=resp_fmt.format(asentada),
                    showarrow=True, arrowhead=0, arrowwidth=1,
                    arrowcolor=SERIES["secundaria"],
                    ax=0, ay=34 if arriba else -34,
                    font=dict(size=10, color="#0d7a55"),
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor=SERIES["secundaria"], borderwidth=1, borderpad=3, **kw)
    return len(mesetas)


def dual_axis_timeseries(
    df: pd.DataFrame,
    excitacion: tuple,  # (col|Series, nombre, unidad) — eje izquierdo, trazo escalonado
    respuestas: list[tuple],  # [(col|Series, nombre, rol)] — eje derecho
    title: str,
    y2_title: str = "Potencia Activa [MW]",
    bands: list[tuple] | None = None,
    time_col: str = "timestamp",
    etiquetas: bool = True,
    max_labels: int = 8,
) -> go.Figure:
    """Serie de tiempo a doble eje — convención de reportes del proyecto:
    eje izq. variable de excitación (f en Hz o V en pu, escalonada, color 1);
    eje der. potencia activa (color 2); bandas normativas sobre el eje izq."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    x = df[time_col]
    exc_data, exc_nombre, exc_unidad = excitacion
    y_exc = df[exc_data] if isinstance(exc_data, str) else exc_data
    fig.add_trace(go.Scatter(
        x=x, y=y_exc, name=exc_nombre, mode="lines",
        line=dict(color=SERIES["medida"], width=2, shape="hv")), secondary_y=False)
    for data, nombre, rol in respuestas:
        y = df[data] if isinstance(data, str) else data
        dash = "dash" if rol == "teorica" else None
        color = SERIES["teorica"] if rol == "teorica" else SERIES["secundaria"]
        fig.add_trace(go.Scatter(
            x=x, y=y, name=nombre, mode="lines",
            line=dict(color=color, width=2, dash=dash)), secondary_y=True)
    for y0, y1, etiqueta in bands or []:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=BAND_FILL, line_width=0, secondary_y=False)
        fig.add_hline(y=y1, line=dict(color=STATUS["neutro"], width=1, dash="dot"),
                      annotation_text=etiqueta, annotation_font_size=10, secondary_y=False)
    fig.update_yaxes(title_text=f"{exc_nombre} [{exc_unidad}]",
                     secondary_y=False, gridcolor=GRID)
    fig.update_yaxes(title_text=y2_title, secondary_y=True, showgrid=False)
    if etiquetas:
        resp0 = None
        if respuestas:
            data0 = respuestas[0][0]
            resp0 = df[data0] if isinstance(data0, str) else data0
        unidad_resp = "pu" if "pu" in y2_title.lower() else (
            "MVAr" if "MVAr" in y2_title else "MW")
        annotate_steps(fig, x, y_exc, resp0,
                       exc_fmt=f"{{:.2f}} {exc_unidad}",
                       resp_fmt=f"{{:.2f}} {unidad_resp}",
                       max_labels=max_labels)
        # margen extra para etiquetas en los extremos
        y_min, y_max = float(y_exc.min()), float(y_exc.max())
        pad = (y_max - y_min) * 0.25 or 0.1
        fig.update_yaxes(range=[y_min - pad, y_max + pad], secondary_y=False)
    fig.update_layout(height=460)
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
