"""
core/plot.py — Motor único de generación de gráficas.

Provee dos funciones principales:
  - plot_single_case(): Pruebas de 1 caso (P1, P2, P4, P6, P12, P13, P25, P26, P28)
  - plot_multi_case(): Pruebas de N casos (P3, P8, P9)
  - plot_p25_capacidad_instalada_neta(): Doble eje P_neta / P_generation para P25 asíncronas
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str((Path(__file__).resolve().parents[1] / ".mplconfig").resolve())
)

import matplotlib
import matplotlib.image as mpimg
import matplotlib.dates as mdates
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.annotate import (
    FREQ_STYLE,
    POWER_STYLE,
    annotate_frequency,
    annotate_power,
    annotate_values,
    plan_adaptive_label_indices,
    add_frequency_step_labels,
    MIN_MULTI_POWER_LABELS,
)


# ─── Colores por defecto (pueden sobreescribirse desde app.py) ────────────────
DEFAULT_FREQ_COLOR = "#0f766e"
DEFAULT_POWER_COLOR = "#2563eb"


# ─── Utilidades ──────────────────────────────────────────────────────────────
def _axis_limits(series: pd.Series, ratio: float = 0.12) -> tuple[float, float]:
    lo, hi = float(series.min()), float(series.max())
    if lo == hi:
        pad = abs(lo) * ratio if lo else 1.0
        return lo - pad, hi + pad
    span = hi - lo
    return lo - span * ratio, hi + span * ratio


def _apply_freq_axis(ax: plt.Axes, freq_color: str) -> None:
    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Frecuencia (Hz)", color=freq_color)
    ax.tick_params(axis="y", labelcolor=freq_color)
    ax.tick_params(axis="x", rotation=28, colors="#64748b")
    ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax.margins(x=0.015)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    for spine in ax.spines.values():
        spine.set_color("#cbd8e3")


def _apply_power_axis(ax: plt.Axes, power_color: str, power_unit: str) -> None:
    ax.set_ylabel(f"Potencia Activa ({power_unit})", color=power_color)
    ax.tick_params(axis="y", labelcolor=power_color)
    for spine in ax.spines.values():
        spine.set_color("#cbd8e3")


def _new_figure() -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(15, 7.8))
    fig.patch.set_facecolor("#f4f7fb")
    ax.set_facecolor("#ffffff")
    return fig, ax


def _save_and_close(fig: plt.Figure, output_path: Path, dpi: int = 180) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.07, right=0.93, bottom=0.10, top=0.84)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _normalize_voltage_pu(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return series.astype(float)
    median = float(clean.abs().median())
    if 0.2 <= median <= 2.0:
        return series.astype(float)
    if median <= 1e-9:
        return series.astype(float)
    return series.astype(float) / median


# ─── Motor 1: caso único ──────────────────────────────────────────────────────
def plot_single_case(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str | None = None,
    output_path: Path | None = None,
    title: str = "",
    power_unit: str = "MW",
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
    aux_col: str | None = None,
    aux_color: str = "#b45309",
    drawstyle: str = "steps-post",
    power_ylim: tuple[float, float] | None = None,
) -> Path | None:
    """Genera la gráfica de doble eje Frecuencia / Potencia Activa para una prueba simple."""
    if output_path is None:
        return None
    
    fig, ax_freq = _new_figure()
    freq_line = ax_freq.plot(
        df[time_col],
        df[freq_col],
        color=freq_color,
        linewidth=2.1,
        drawstyle=drawstyle,
        label="Frecuencia",
        zorder=3,
    )[0]
    ax_freq.set_ylim(*_axis_limits(df[freq_col], 0.12))
    _apply_freq_axis(ax_freq, freq_color)

    legend_handles = [freq_line]
    legend_labels = ["Frecuencia"]

    if power_col and power_col in df.columns:
        ax_power = ax_freq.twinx()
        power_line = ax_power.plot(
            df[time_col],
            df[power_col],
            color=power_color,
            linewidth=2.1,
            label="Potencia Activa",
            zorder=2,
        )[0]
        ax_power.set_ylim(*(power_ylim or _axis_limits(df[power_col], 0.14)))
        _apply_power_axis(ax_power, power_color, power_unit)
        legend_handles.append(power_line)
        legend_labels.append("Potencia Activa")

        if aux_col and aux_col in df.columns:
            aux_line = ax_power.plot(
                df[time_col],
                df[aux_col],
                color=aux_color,
                linewidth=1.8,
                linestyle="--",
                label="Setpoint / Referencia",
                zorder=2,
            )[0]
            legend_handles.append(aux_line)
            legend_labels.append("Setpoint / Referencia")

        annotate_power(ax_power, df, time_col, power_col, power_unit, power_color)

    annotate_frequency(ax_freq, df, time_col, freq_col, freq_color)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=len(legend_labels),
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


# ─── Motor 2: múltiples casos ─────────────────────────────────────────────────
def plot_multi_case(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    output_path: Path,
    title: str,
    power_unit: str = "MW",
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
    drawstyle: str = "steps-post",
    step_label_min_freq: float | None = 60.2,
    force_step_labels: bool = False,
) -> Path:
    """Genera la gráfica doble eje para pruebas multi-caso (P3, P8, P9)."""
    fig, ax_freq = _new_figure()
    freq_line = ax_freq.plot(
        df[time_col],
        df[freq_col],
        color=freq_color,
        linewidth=2.1,
        drawstyle=drawstyle,
        label="Frecuencia",
        zorder=3,
    )[0]
    ax_freq.set_ylim(*_axis_limits(df[freq_col], 0.14))
    _apply_freq_axis(ax_freq, freq_color)

    ax_power = ax_freq.twinx()

    power_vals = list(df[power_col])
    pw_min = min(power_vals)
    pw_max = max(power_vals)
    pw_lo, pw_hi = _axis_limits(pd.Series([pw_min, pw_max]), 0.16)

    power_line = ax_power.plot(
        df[time_col],
        df[power_col],
        color=power_color,
        linewidth=2.1,
        label="Potencia Activa",
        zorder=2,
    )[0]
    ax_power.set_ylim(pw_lo, pw_hi)
    _apply_power_axis(ax_power, power_color, power_unit)

    annotate_frequency(ax_freq, df, time_col, freq_col, freq_color, count=5)
    annotate_power(
        ax_power,
        df,
        time_col,
        power_col,
        power_unit,
        power_color,
        count=10,
        min_visible=MIN_MULTI_POWER_LABELS,
        force_min_visible=True,
    )
    add_frequency_step_labels(
        ax_freq,
        df,
        time_col,
        freq_col,
        freq_color,
        label_min_freq=step_label_min_freq,
        force_all=force_step_labels,
    )

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [freq_line, power_line],
        ["Frecuencia", "Potencia Activa"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_multi_compare_cases(
    cases: list,
    output_path: Path,
    title: str,
    power_unit: str = "MW",
) -> Path:
    fig, (ax_freq, ax_power) = plt.subplots(
        2,
        1,
        figsize=(15, 8.4),
        sharex=True,
        gridspec_kw={"hspace": 0.12},
    )
    fig.patch.set_facecolor("#f4f7fb")
    ax_freq.set_facecolor("#ffffff")
    ax_power.set_facecolor("#ffffff")
    palette = ["#0891b2", "#0f766e", "#b45309", "#4f46e5", "#dc2626"]

    for idx, case in enumerate(cases):
        df = getattr(case, "df", None)
        if df is None or df.empty:
            continue
        work = df.copy()
        work["time"] = pd.to_datetime(work["time"])
        elapsed = (work["time"] - work["time"].iloc[0]).dt.total_seconds() / 60.0
        color = palette[idx % len(palette)]
        ax_freq.plot(
            elapsed,
            work["frequency"],
            color=color,
            linewidth=2.0,
            label=f"{case.caso}",
        )
        ax_power.plot(
            elapsed,
            work["active_power"],
            color=color,
            linewidth=2.0,
            label=f"{case.caso}",
        )

    ax_freq.set_ylabel("Frecuencia (Hz)")
    ax_power.set_ylabel(f"Potencia activa ({power_unit})")
    ax_power.set_xlabel("Tiempo transcurrido (min)")
    for ax in (ax_freq, ax_power):
        ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
        ax.legend(title="Estatismo", frameon=False, ncol=3, fontsize=9)
        ax.margins(x=0.015)
        ax.tick_params(axis="both", colors="#64748b")
        for spine in ax.spines.values():
            spine.set_color("#cbd8e3")

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.07, right=0.95, bottom=0.10, top=0.90)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_multi_power_compare_cases(
    cases: list,
    output_path: Path,
    title: str = "Potencia activa por caso",
    power_unit: str = "MW",
) -> Path:
    fig, ax = plt.subplots(figsize=(15, 6.2))
    bg = "#f4f7fb"
    panel = "#ffffff"
    grid = "#d7e2ea"
    text = "#102033"
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(panel)
    palette = ["#0891b2", "#0f766e", "#b45309", "#4f46e5", "#dc2626"]

    for idx, case in enumerate(cases):
        df = getattr(case, "df", None)
        if df is None or df.empty:
            continue
        work = df.copy()
        work["time"] = pd.to_datetime(work["time"])
        elapsed = (work["time"] - work["time"].iloc[0]).dt.total_seconds() / 60.0
        ax.plot(
            elapsed,
            work["active_power"],
            color=palette[idx % len(palette)],
            linewidth=2.4,
            linestyle=":",
            label=f"Estatismo {case.caso}",
        )

    ax.set_title(title, fontsize=14, fontweight="bold", color=text, pad=16)
    ax.set_xlabel("Tiempo transcurrido (min)", fontsize=12, color=text, labelpad=12)
    ax.set_ylabel(f"Potencia activa ({power_unit})", fontsize=12, color=text, labelpad=12)
    ax.grid(True, axis="both", linestyle="-", color=grid, alpha=0.75)
    ax.tick_params(axis="both", colors="#64748b", labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#cbd8e3")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=9)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.22, top=0.88)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


def plot_voltage_case(
    df: pd.DataFrame,
    time_col: str,
    voltage_col: str,
    output_path: Path,
    title: str,
    lower_limit: float,
    upper_limit: float,
    voltage_color: str = "#4f46e5",
) -> Path:
    fig, ax = _new_figure()
    voltage_pu = _normalize_voltage_pu(df[voltage_col])
    ax.plot(
        df[time_col], voltage_pu, color=voltage_color, linewidth=2.0, label="Tension"
    )
    ax.axhline(
        lower_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.4,
        label="Limite inferior",
    )
    ax.axhline(
        upper_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.4,
        label="Limite superior",
    )
    ax.fill_between(df[time_col], lower_limit, upper_limit, color="#0f766e", alpha=0.10)
    ax.set_ylabel("Tension (pu)", color=voltage_color)
    ax.tick_params(axis="y", labelcolor=voltage_color)
    ax.tick_params(axis="x", rotation=28, colors="#64748b")
    ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax.margins(x=0.015)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.set_ylim(
        *_axis_limits(pd.Series([*voltage_pu.dropna(), lower_limit, upper_limit]), 0.12)
    )
    annotate_values(
        ax,
        df[time_col],
        voltage_pu,
        plan_adaptive_label_indices(df[time_col], voltage_pu, role="generic", target_count=4),
        "{value:.3f} pu",
        voltage_color,
        "#f3e8ff",
        voltage_color,
        FREQ_STYLE,
    )
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_reactive_pf_case(
    df: pd.DataFrame,
    time_col: str,
    reactive_col: str,
    power_factor_col: str,
    output_path: Path,
    title: str,
    reactive_color: str = "#b45309",
    pf_color: str = "#0891b2",
) -> Path:
    fig, ax_q = _new_figure()
    q_line = ax_q.plot(
        df[time_col],
        df[reactive_col],
        color=reactive_color,
        linewidth=2.0,
        label="Potencia reactiva",
    )[0]
    ax_q.set_ylabel("Potencia reactiva (MVAr)", color=reactive_color)
    ax_q.tick_params(axis="y", labelcolor=reactive_color)
    ax_q.tick_params(axis="x", rotation=28, colors="#64748b")
    ax_q.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax_q.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax_q.margins(x=0.015)
    ax_q.set_ylim(*_axis_limits(df[reactive_col], 0.14))

    ax_pf = ax_q.twinx()
    pf_line = ax_pf.plot(
        df[time_col],
        df[power_factor_col],
        color=pf_color,
        linewidth=2.0,
        label="Factor de potencia",
    )[0]
    ax_pf.axhline(
        0.95, color="#ef4444", linestyle="--", linewidth=1.4, label="FP minimo"
    )
    ax_pf.axhline(-0.95, color="#ef4444", linestyle="--", linewidth=1.4)
    ax_pf.set_ylabel("Factor de potencia", color=pf_color)
    ax_pf.tick_params(axis="y", labelcolor=pf_color)
    ax_pf.set_ylim(-1.05, 1.05)

    annotate_values(
        ax_q,
        df[time_col],
        df[reactive_col],
        plan_adaptive_label_indices(
            df[time_col],
            df[reactive_col],
            role="power",
            target_count=4,
        ),
        "{value:.3f} MVAr",
        reactive_color,
        "#ffedd5",
        reactive_color,
        POWER_STYLE,
    )
    annotate_values(
        ax_pf,
        df[time_col],
        df[power_factor_col],
        plan_adaptive_label_indices(
            df[time_col],
            df[power_factor_col],
            role="generic",
            target_count=4,
        ),
        "{value:.3f}",
        pf_color,
        "#ccfbf1",
        pf_color,
        FREQ_STYLE,
    )
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [q_line, pf_line],
        ["Potencia reactiva", "Factor de potencia"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_quality_case(
    df: pd.DataFrame,
    time_col: str,
    signal_columns: list[tuple[str, str]],
    output_path: Path,
    title: str,
) -> Path:
    if not signal_columns:
        raise ValueError(
            "No hay señales disponibles para graficar calidad de potencia."
        )

    fig, axes = plt.subplots(
        len(signal_columns), 1, figsize=(15, 3.4 * len(signal_columns)), sharex=True
    )
    if len(signal_columns) == 1:
        axes = [axes]

    fig.patch.set_facecolor("#f4f7fb")
    palette = ["#4f46e5", "#0891b2", "#b45309", "#2563eb"]
    for idx, ((column, label), ax) in enumerate(zip(signal_columns, axes)):
        ax.set_facecolor("#ffffff")
        color = palette[idx % len(palette)]
        ax.plot(df[time_col], df[column], color=color, linewidth=1.9)
        ax.set_ylabel(label, color=color)
        ax.tick_params(axis="y", labelcolor=color)
        ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
        ax.margins(x=0.015)
        for spine in ax.spines.values():
            spine.set_color("#cbd8e3")
        ax.set_ylim(*_axis_limits(df[column], 0.14))
        annotate_values(
            ax,
            df[time_col],
            df[column],
            plan_adaptive_label_indices(
                df[time_col],
                df[column],
                role="generic",
                target_count=3,
            ),
            "{value:.3f}",
            color,
            "#f8fbfd",
            color,
            POWER_STYLE,
        )

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    axes[-1].tick_params(axis="x", rotation=28, colors="#64748b")
    axes[-1].set_xlabel("Tiempo")
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.992)
    fig.subplots_adjust(left=0.08, right=0.94, bottom=0.10, top=0.90, hspace=0.18)
    return _save_and_close(fig, output_path)


def plot_p28_frequency_control_summary(
    evidence: dict[str, list[Path]],
    summary_tables: dict[str, dict[str, pd.DataFrame]],
    output_path: Path,
    title: str,
) -> Path:
    labels = {
        "P1": "Rango de frecuencia",
        "P2": "ROCOF",
        "P3": "Alta frecuencia",
        "P8": "Baja frecuencia",
        "P9": "Control primario",
    }
    fig = plt.figure(figsize=(15, 5.2))
    fig.patch.set_facecolor("#f4f7fb")
    grid = fig.add_gridspec(1, 3, wspace=0.25)
    colors = {"3%": "#2563eb", "5%": "#b45309", "8%": "#4f46e5"}

    for col, test_id in enumerate(("P3", "P8", "P9")):
        ax = fig.add_subplot(grid[0, col])
        ax.set_facecolor("#ffffff")
        tables = summary_tables.get(test_id, {})
        if not tables:
            ax.text(0.5, 0.5, "Sin resumen XLSX", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        for caso, frame in tables.items():
            work = frame.copy().sort_values("Frecuencia [Hz]")
            ax.plot(
                work["Frecuencia [Hz]"],
                work["Potencia [MW]"],
                marker="o",
                linewidth=2.0,
                label=caso,
                color=colors.get(caso, "#102033"),
            )
        ax.set_title(f"{test_id} · {labels[test_id]}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Frecuencia (Hz)")
        ax.set_ylabel("Potencia activa (MW)")
        ax.grid(True, linestyle="-", color="#d7e2ea", alpha=0.75)
        ax.tick_params(axis="both", colors="#64748b")
        for spine in ax.spines.values():
            spine.set_color("#cbd8e3")
        ax.legend(frameon=False, fontsize=8)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.14, top=0.84)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_p28_power_behavior_compare(
    tables: dict[str, pd.DataFrame],
    output_path: Path,
    title: str = "Potencia activa por caso",
) -> Path:
    fig, ax = plt.subplots(figsize=(15, 6.2))
    fig.patch.set_facecolor("#f4f7fb")
    ax.set_facecolor("#ffffff")
    colors = {"3%": "#0891b2", "5%": "#0f766e", "8%": "#b45309"}

    for caso, frame in tables.items():
        work = frame.copy()
        work["time"] = pd.to_datetime(work["time"], errors="coerce")
        work["active_power"] = pd.to_numeric(work["active_power"], errors="coerce")
        work = work.dropna(subset=["time", "active_power"]).sort_values("time")
        if work.empty:
            continue
        elapsed = (work["time"] - work["time"].iloc[0]).dt.total_seconds() / 60.0
        ax.plot(
            elapsed,
            work["active_power"],
            linewidth=2.6,
            linestyle=":",
            label=f"Estatismo {caso}",
            color=colors.get(caso, "#102033"),
        )

    ax.set_title(title, fontsize=14, fontweight="bold", color="#102033", pad=16)
    ax.set_xlabel("Tiempo transcurrido (min)", fontsize=12, color="#102033", labelpad=12)
    ax.set_ylabel("Potencia activa (MW)", fontsize=12, color="#102033", labelpad=12)
    ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax.tick_params(axis="both", colors="#64748b", labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#cbd8e3")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=9)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.22, top=0.88)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _apply_datetime_axis(ax: plt.Axes) -> None:
    ax.tick_params(axis="x", rotation=28, colors="#64748b")
    ax.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax.margins(x=0.015)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    for spine in ax.spines.values():
        spine.set_color("#cbd8e3")


def plot_p25_net_injection(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
) -> Path:
    fig, ax = _new_figure()
    gen_line = ax.plot(
        df["time"],
        df["generation_mw"],
        color="#0f766e",
        linewidth=2.0,
        label="Generacion",
    )[0]
    load_line = ax.plot(
        df["time"],
        df["load_mw"],
        color="#b45309",
        linewidth=2.0,
        label="Carga",
    )[0]
    net_line = ax.plot(
        df["time"],
        df["net_injection_mw"],
        color="#102033",
        linewidth=2.8,
        label="P_neta = P_generacion - P_carga",
    )[0]
    zero_line = ax.axhline(
        0,
        color="#6b7280",
        linestyle="--",
        linewidth=1.3,
        label="0 MW (sin inyeccion)",
    )
    ax.set_ylabel("Potencia (MW)")
    _apply_datetime_axis(ax)
    ax.set_ylim(
        *_axis_limits(
            pd.concat(
                [df["generation_mw"], df["load_mw"], df["net_injection_mw"]],
                ignore_index=True,
            ),
            0.12,
        )
    )
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [gen_line, load_line, net_line, zero_line],
        ["P_generacion", "P_carga", "P_neta = P_gen - P_carga", "0 MW"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=4,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_p25_no_injection_compliance(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
) -> Path:
    fig, ax = _new_figure()
    net = pd.to_numeric(df["net_injection_mw"], errors="coerce")
    net_line = ax.plot(
        df["time"],
        net,
        color="#102033",
        linewidth=2.4,
        label="P_neta = P_generacion - P_carga",
        zorder=4,
    )[0]
    zero_line = ax.axhline(
        0,
        color="#ef4444",
        linestyle="--",
        linewidth=1.6,
        label="Limite 0 MW",
        zorder=3,
    )

    clean = net.dropna()
    y_min, y_max = _axis_limits(clean, 0.18)
    y_min = min(y_min, 0.0)
    y_max = max(y_max, 0.05)
    ax.set_ylim(y_min, y_max)
    ax.axhspan(y_min, 0, color="#dcfce7", alpha=0.55, label="Cumple: sin inyeccion")
    ax.axhspan(0, y_max, color="#fee2e2", alpha=0.75, label="Inyeccion positiva")

    positive = df[net > 0]
    if not positive.empty:
        ax.scatter(
            positive["time"],
            positive["net_injection_mw"],
            s=14,
            color="#dc2626",
            alpha=0.85,
            label="Eventos > 0 MW",
            zorder=5,
        )

    ax.set_ylabel("Potencia neta (MW)")
    _apply_datetime_axis(ax)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [net_line, zero_line],
        ["P_neta = P_gen - P_carga", "0 MW"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)



def plot_p25_capacidad_instalada_neta(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
    smoothing_window: int = 5,
) -> Path:
    """Gráfica de P_neta y P_generacion en paneles separados para evitar confundir el límite 0 MW."""

    net_color = "#102033"
    gen_color = "#0f766e"

    def _smooth(series: pd.Series, w: int) -> pd.Series:
        if w <= 1 or len(series) < w:
            return series
        return series.rolling(window=w, center=True, min_periods=1).mean()

    net_smooth = _smooth(df["net_injection_mw"], smoothing_window)
    gen_smooth = _smooth(df["generation_mw"], smoothing_window)

    fig, (ax_net, ax_gen) = plt.subplots(
        2,
        1,
        figsize=(15, 8.4),
        sharex=True,
        gridspec_kw={"height_ratios": [1.35, 1.0], "hspace": 0.12},
    )
    fig.patch.set_facecolor("#f4f7fb")
    ax_net.set_facecolor("#ffffff")
    ax_gen.set_facecolor("#ffffff")

    net_line = ax_net.plot(
        df["time"],
        net_smooth,
        color=net_color,
        linewidth=2.2,
        label="P_neta = P_generacion - P_carga",
        zorder=3,
    )[0]
    zero_line = ax_net.axhline(
        0,
        color="#ef4444",
        linestyle="--",
        linewidth=1.5,
        zorder=2,
        label="0 MW (limite de inyeccion)",
    )
    ax_net.set_ylabel("Potencia neta (MW)", color=net_color)
    ax_net.tick_params(axis="y", labelcolor=net_color)
    ax_net.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    for spine in ax_net.spines.values():
        spine.set_color("#cbd8e3")
    net_lo, net_hi = _axis_limits(net_smooth, 0.18)
    net_lo = min(net_lo, 0.0)
    net_hi = max(net_hi, 0.05)
    ax_net.set_ylim(net_lo, net_hi)
    ax_net.axhspan(net_lo, 0, color="#dcfce7", alpha=0.45)
    ax_net.axhspan(0, net_hi, color="#fee2e2", alpha=0.60)

    gen_line = ax_gen.plot(
        df["time"],
        gen_smooth,
        color=gen_color,
        linewidth=2.2,
        label="P_generacion",
        zorder=2,
    )[0]
    ax_gen.set_ylabel("Potencia de generacion (MW)", color=gen_color)
    ax_gen.tick_params(axis="y", labelcolor=gen_color)
    ax_gen.set_ylim(*_axis_limits(gen_smooth, 0.14))
    ax_gen.grid(True, axis="both", linestyle="-", color="#d7e2ea", alpha=0.75)
    for spine in ax_gen.spines.values():
        spine.set_color("#cbd8e3")
    ax_gen.margins(x=0.015)
    ax_gen.xaxis.set_major_locator(mdates.DayLocator())
    ax_gen.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax_gen.tick_params(axis="x", rotation=45, colors="#64748b")
    ax_gen.set_xlabel("Tiempo")

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [net_line, zero_line, gen_line],
        ["P_neta = P_gen - P_carga", "0 MW", "P_generacion"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.07, right=0.93, bottom=0.12, top=0.84)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_p25_frequency(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
    lower_limit: float = 59.5,
    upper_limit: float = 60.5,
    deadband_lower: float = 59.97,
    deadband_upper: float = 60.03,
) -> Path:
    fig, ax = _new_figure()
    freq_line = ax.plot(
        df["time"],
        df["frequency"],
        color="#2563eb",
        linewidth=2.0,
        label="Frecuencia",
    )[0]
    ax.axhspan(lower_limit, upper_limit, color="#d1d5db", alpha=0.25)
    ax.axhspan(deadband_lower, deadband_upper, color="#cbd5e1", alpha=0.42)
    low_line = ax.axhline(
        lower_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.3,
        label="59.5 Hz",
    )
    high_line = ax.axhline(
        upper_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.3,
        label="60.5 Hz",
    )
    deadband_low_line = ax.axhline(
        deadband_lower,
        color="#b45309",
        linestyle=":",
        linewidth=1.4,
        label="59.97 Hz",
    )
    deadband_high_line = ax.axhline(
        deadband_upper,
        color="#b45309",
        linestyle=":",
        linewidth=1.4,
        label="60.03 Hz",
    )
    out_deadband = df[(df["frequency"] < deadband_lower) | (df["frequency"] > deadband_upper)]
    if not out_deadband.empty:
        ax.scatter(
            out_deadband["time"],
            out_deadband["frequency"],
            s=14,
            color="#ef4444",
            alpha=0.8,
            zorder=5,
            label="Fuera de banda muerta",
        )
    ax.set_ylabel("Frecuencia (Hz)")
    _apply_datetime_axis(ax)
    freq_values = pd.Series([*df["frequency"].dropna(), deadband_lower, deadband_upper])
    freq_min = float(freq_values.min())
    freq_max = float(freq_values.max())
    span = max(freq_max - freq_min, 0.01)
    pad = max(span * 0.20, 0.005)
    ax.set_ylim(freq_min - pad, freq_max + pad)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [freq_line, low_line, high_line, deadband_low_line, deadband_high_line],
        ["f_poi", "59.5 Hz", "60.5 Hz", "59.97 Hz", "60.03 Hz"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=5,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_p25_voltage(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
    lower_limit: float = 0.95,
    upper_limit: float = 1.05,
) -> Path:
    fig, ax = _new_figure()
    voltage_line = ax.plot(
        df["time"],
        df["voltage_pu"],
        color="#2563eb",
        linewidth=2.0,
        label="Voltaje",
    )[0]
    ax.axhspan(lower_limit, upper_limit, color="#d1d5db", alpha=0.25)
    low_line = ax.axhline(
        lower_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.3,
        label="0.95 p.u.",
    )
    high_line = ax.axhline(
        upper_limit,
        color="#ef4444",
        linestyle="--",
        linewidth=1.3,
        label="1.05 p.u.",
    )
    out_band = df[(df["voltage_pu"] < lower_limit) | (df["voltage_pu"] > upper_limit)]
    if not out_band.empty:
        ax.scatter(
            out_band["time"],
            out_band["voltage_pu"],
            s=14,
            color="#ef4444",
            alpha=0.8,
            zorder=5,
            label="Fuera de banda",
        )
    ax.set_ylabel("Voltaje (p.u.)")
    _apply_datetime_axis(ax)
    voltage_values = pd.Series([*df["voltage_pu"].dropna(), lower_limit, upper_limit])
    voltage_min = float(voltage_values.min())
    voltage_max = float(voltage_values.max())
    span = max(voltage_max - voltage_min, 0.01)
    pad = max(span * 0.15, 0.003)
    ax.set_ylim(voltage_min - pad, voltage_max + pad)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [voltage_line, low_line, high_line],
        ["V_pu", "0.95 p.u.", "1.05 p.u."],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


def plot_p25_daily_indicators(
    daily_df: pd.DataFrame,
    output_path: Path,
    title: str,
) -> Path:
    fig, ax_energy = plt.subplots(figsize=(15, 7.8))
    fig.patch.set_facecolor("#f4f7fb")
    ax_energy.set_facecolor("#ffffff")
    x = range(len(daily_df))
    width = 0.36
    bars_gen = ax_energy.bar(
        [idx - width / 2 for idx in x],
        daily_df["energia_generada_mwh"],
        width=width,
        color="#0f766e",
        label="Energia generada",
    )
    bars_load = ax_energy.bar(
        [idx + width / 2 for idx in x],
        daily_df["energia_carga_mwh"],
        width=width,
        color="#b45309",
        label="Energia carga",
    )
    ax_energy.set_ylabel("Energia (MWh/dia)")
    ax_energy.set_xticks(list(x))
    ax_energy.set_xticklabels(daily_df["day_label"], rotation=25, ha="right")
    ax_energy.grid(True, axis="y", linestyle="-", color="#d7e2ea", alpha=0.75)
    ax_energy.tick_params(axis="both", colors="#64748b")
    for spine in ax_energy.spines.values():
        spine.set_color("#cbd8e3")

    ax_hours = ax_energy.twinx()
    hours_line = ax_hours.plot(
        list(x),
        daily_df["horas_operacion_h"],
        color="#2563eb",
        linewidth=2.2,
        marker="o",
        label="Horas operacion",
    )[0]
    ax_hours.set_ylabel("Horas operacion (h/dia)")
    ax_hours.set_ylim(0, max(24.0, float(daily_df["horas_operacion_h"].max()) * 1.12 if not daily_df.empty else 24.0))

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        [bars_gen, bars_load, hours_line],
        ["Energia generada", "Energia carga", "Horas operacion"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    return _save_and_close(fig, output_path)


# ─── Motor 3: Pruebas con zonas esperadas (P3, P8, P9) ────────────────────────
def _plot_base_with_zones(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    curva_teorica: pd.Series,
    output_path: Path,
    title: str,
    power_unit: str,
    freq_color: str,
    power_color: str,
    drawstyle: str,
    estatismo: float,
    p_op: float,
    p_ref: float,
    zona_type: str,
) -> Path:
    """Funcion base para graficas con zonas esperadas.

    zona_type: "alta" (P3), "baja" (P8), "primario" (P9)
    """
    fig, ax_freq = _new_figure()

    # Eje frecuencia
    freq_line = ax_freq.plot(
        df[time_col],
        df[freq_col],
        color=freq_color,
        linewidth=2.1,
        drawstyle=drawstyle,
        label="Frecuencia",
        zorder=3,
    )[0]
    ax_freq.set_ylim(*_axis_limits(df[freq_col], 0.14))
    _apply_freq_axis(ax_freq, freq_color)

    # Eje potencia
    ax_power = ax_freq.twinx()
    power_line = ax_power.plot(
        df[time_col],
        df[power_col],
        color=power_color,
        linewidth=2.1,
        label="Potencia Activa",
        zorder=2,
    )[0]

    # Curva teorica
    teorica_line = ax_power.plot(
        df[time_col],
        curva_teorica,
        color="#ef4444",
        linewidth=2.0,
        linestyle="--",
        label=f"Curva teorica (S={estatismo*100:.0f}%)",
        zorder=1,
    )[0]

    ax_power.set_ylim(
        *_axis_limits(pd.concat([df[power_col], curva_teorica], ignore_index=True), 0.16)
    )
    _apply_power_axis(ax_power, power_color, power_unit)

    # Zonas sombreadas segun tipo
    legend_handles = [freq_line, power_line, teorica_line]
    legend_labels = ["Frecuencia", "Potencia Activa", f"Curva teorica (S={estatismo*100:.0f}%)"]

    f_nom = 60.0
    db = 0.030

    if zona_type == "alta":
        ax_power.axhspan(0, p_op, color="#dcfce7", alpha=0.25, label="Zona reduccion esperada")
        ax_power.axhline(p_op, color="#16a34a", linestyle=":", linewidth=1.2, label=f"P_op = {p_op:.2f} MW")
        ax_freq.axhline(60.20, color="#b45309", linestyle="--", linewidth=1.2, label="Inicio zona alta (60.20 Hz)")
        ax_freq.axhline(f_nom + db, color="#64748b", linestyle=":", linewidth=1.0, label="Banda muerta (+)")
        ax_freq.axhline(f_nom - db, color="#64748b", linestyle=":", linewidth=1.0, label="Banda muerta (-)")
        legend_labels.append("Zona reduccion esperada")
        legend_labels.append(f"P_op = {p_op:.2f} MW")
        legend_labels.append("Inicio zona alta (60.20 Hz)")

    elif zona_type == "baja":
        ax_power.axhspan(p_op, p_ref, color="#dcfce7", alpha=0.25, label="Zona incremento esperado")
        ax_power.axhline(p_op, color="#16a34a", linestyle=":", linewidth=1.2, label=f"P_op = {p_op:.2f} MW")
        ax_freq.axhline(59.80, color="#b45309", linestyle="--", linewidth=1.2, label="Inicio zona baja (59.80 Hz)")
        ax_freq.axhline(f_nom + db, color="#64748b", linestyle=":", linewidth=1.0, label="Banda muerta (+)")
        ax_freq.axhline(f_nom - db, color="#64748b", linestyle=":", linewidth=1.0, label="Banda muerta (-)")
        legend_labels.append("Zona incremento esperado")
        legend_labels.append(f"P_op = {p_op:.2f} MW")
        legend_labels.append("Inicio zona baja (59.80 Hz)")

    elif zona_type == "primario":
        ax_freq.axhspan(f_nom - db, f_nom + db, color="#dbeafe", alpha=0.30, label="Banda muerta")
        ax_power.axhspan(
            p_op - p_ref * 0.02, p_op + p_ref * 0.02,
            color="#dcfce7", alpha=0.25, label="Zona respuesta esperada"
        )
        ax_power.axhline(p_op, color="#16a34a", linestyle=":", linewidth=1.2, label=f"P_op = {p_op:.2f} MW")
        ax_freq.axhline(f_nom + db, color="#b45309", linestyle="--", linewidth=1.2, label="Banda muerta (+)")
        ax_freq.axhline(f_nom - db, color="#b45309", linestyle="--", linewidth=1.2, label="Banda muerta (-)")
        legend_labels.append("Banda muerta")
        legend_labels.append("Zona respuesta esperada")
        legend_labels.append(f"P_op = {p_op:.2f} MW")

    # Anotaciones
    annotate_frequency(ax_freq, df, time_col, freq_col, freq_color, count=5)
    annotate_power(
        ax_power,
        df,
        time_col,
        power_col,
        power_unit,
        power_color,
        count=10,
        min_visible=MIN_MULTI_POWER_LABELS,
        force_min_visible=True,
    )

    # Info box
    info_text = f"Estatismo: {estatismo*100:.0f}% | P_op: {p_op:.2f} MW | P_ref: {p_ref:.2f} MW"
    ax_power.text(
        0.02, 0.02, info_text,
        transform=ax_power.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85),
    )

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.952),
        ncol=min(len(legend_labels), 4),
        frameon=False,
        fontsize=9,
    )
    return _save_and_close(fig, output_path)


def plot_p3_with_zones(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    curva_teorica: pd.Series,
    output_path: Path,
    title: str,
    power_unit: str = "MW",
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
    drawstyle: str = "steps-post",
    estatismo: float = 0.03,
    p_op: float = 0.0,
    p_ref: float = 0.0,
) -> Path:
    """Grafica P3 (alta frecuencia) con zona esperada sombreada."""
    return _plot_base_with_zones(
        df, time_col, freq_col, power_col, curva_teorica,
        output_path, title, power_unit, freq_color, power_color,
        drawstyle, estatismo, p_op, p_ref, zona_type="alta",
    )


def plot_p8_with_zones(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    curva_teorica: pd.Series,
    output_path: Path,
    title: str,
    power_unit: str = "MW",
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
    drawstyle: str = "steps-post",
    estatismo: float = 0.03,
    p_op: float = 0.0,
    p_ref: float = 0.0,
) -> Path:
    """Grafica P8 (baja frecuencia) con zona esperada sombreada."""
    return _plot_base_with_zones(
        df, time_col, freq_col, power_col, curva_teorica,
        output_path, title, power_unit, freq_color, power_color,
        drawstyle, estatismo, p_op, p_ref, zona_type="baja",
    )


def plot_p9_with_zones(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    curva_teorica: pd.Series,
    output_path: Path,
    title: str,
    power_unit: str = "MW",
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
    drawstyle: str = "steps-post",
    estatismo: float = 0.03,
    p_op: float = 0.0,
    p_ref: float = 0.0,
) -> Path:
    """Grafica P9 (control primario) con zona esperada sombreada."""
    return _plot_base_with_zones(
        df, time_col, freq_col, power_col, curva_teorica,
        output_path, title, power_unit, freq_color, power_color,
        drawstyle, estatismo, p_op, p_ref, zona_type="primario",
    )
