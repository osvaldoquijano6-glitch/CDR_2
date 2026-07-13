"""
core/annotate.py — Anotaciones de valor en gráficas (frecuencia y potencia).

Consolida graph_utils.py y los helpers de anotación de todos los TEMPLATE_Pxx.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox


# ─── Estilos ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LabelStyle:
    x_offset: int
    y_offset: int
    horizontal_alignment: str
    vertical_alignment: str
    font_size: float = 7.2
    marker_size: int = 22
    box_pad: float = 0.22
    box_rounding: float = 0.18
    box_linewidth: float = 0.8
    box_alpha: float = 0.9


FREQ_STYLE = LabelStyle(
    x_offset=-10, y_offset=10,
    horizontal_alignment="right", vertical_alignment="bottom",
)
POWER_STYLE = LabelStyle(
    x_offset=10, y_offset=-10,
    horizontal_alignment="left", vertical_alignment="top",
)


# ─── Parámetros mínimos de gráficas ───────────────────────────────────────────
MIN_MULTI_POWER_LABELS = 5
MIN_FREQUENCY_STEP_HZ = 0.03


# ─── Selección de índices ─────────────────────────────────────────────────────
def select_extreme_indices(series: pd.Series, count: int = 6) -> list[int]:
    """Selecciona índices de máximos y mínimos con espaciado mínimo."""
    if series.empty:
        return []
    min_spacing = max(1, len(series) // 14)
    candidates: list[int] = []
    ranked = list(series.nsmallest(count * 3).index) + list(series.nlargest(count * 3).index)
    for idx in ranked:
        if all(abs(idx - c) >= min_spacing for c in candidates):
            candidates.append(idx)
        if len(candidates) >= count:
            break
    for boundary in (int(series.idxmin()), int(series.idxmax())):
        if boundary not in candidates:
            candidates.append(boundary)
    candidates = sorted(set(candidates))
    selected: list[int] = []
    for idx in candidates:
        if all(abs(idx - c) >= min_spacing for c in selected):
            selected.append(idx)
    if len(selected) < count:
        for step in range(count):
            raw = round(step * (len(series) - 1) / max(1, count - 1))
            if raw not in selected:
                selected.append(raw)
            if len(selected) >= count:
                break
    return sorted(selected[:count])


def select_time_spaced_indices(
    times: pd.Series,
    values: pd.Series,
    interval_s: float = 30.0,
    min_delta: float = 0.005,
) -> list[int]:
    """Selecciona índices separados temporalmente con delta mínimo en valor."""
    if len(times) <= 2:
        return list(range(len(times)))
    elapsed = (times - times.iloc[0]).dt.total_seconds()
    selected = [0]
    last = 0
    next_target = interval_s
    for i in range(1, len(times) - 1):
        curr = float(elapsed.iloc[i])
        if curr < next_target:
            continue
        changed = abs(float(values.iloc[i]) - float(values.iloc[last])) >= min_delta
        forced = (curr - float(elapsed.iloc[last])) >= interval_s * 2.0
        if changed or forced:
            selected.append(i)
            last = i
            next_target = curr + interval_s
    if selected[-1] != len(times) - 1:
        selected.append(len(times) - 1)
    return selected


def _cap_indices(indices: list[int], max_count: int) -> list[int]:
    if len(indices) <= max_count:
        return indices
    if max_count <= 1:
        return [indices[0]]
    picks = {
        round(step * (len(indices) - 1) / max(1, max_count - 1))
        for step in range(max_count)
    }
    return [indices[idx] for idx in sorted(picks)]


def _series_duration_seconds(times: pd.Series) -> float:
    if len(times) <= 1:
        return 0.0
    return float((times.iloc[-1] - times.iloc[0]).total_seconds())


def _median_step_seconds(times: pd.Series) -> float:
    if len(times) <= 1:
        return 1.0
    diffs = times.diff().dt.total_seconds().dropna()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return 1.0
    return float(diffs.median())


def _default_label_budget(duration_s: float, role: str) -> int:
    if duration_s <= 5 * 60:
        base = 7
    elif duration_s <= 30 * 60:
        base = 6
    elif duration_s <= 6 * 3600:
        base = 5
    elif duration_s <= 24 * 3600:
        base = 4
    else:
        base = 4

    if role == "power":
        base = max(3, base - 1)
    elif role == "long":
        base = max(3, min(base, 4))
    return base


def _score_candidate(
    idx: int,
    values: pd.Series,
    event_strength: pd.Series,
    center_value: float,
    value_span: float,
    total_count: int,
    role: str,
) -> float:
    extreme_strength = abs(float(values.iloc[idx]) - center_value) / value_span
    score = extreme_strength * (0.85 if role == "frequency" else 0.55)
    score += float(event_strength.iloc[idx]) * (1.15 if role == "power" else 0.95)
    if idx in {0, total_count - 1}:
        score += 0.35
    return score


def plan_adaptive_label_indices(
    times: pd.Series,
    values: pd.Series,
    role: Literal["frequency", "power", "generic", "long"] = "generic",
    target_count: int | None = None,
) -> list[int]:
    if len(times) <= 2:
        return list(range(len(times)))

    duration_s = _series_duration_seconds(times)
    median_step_s = _median_step_seconds(times)
    target = target_count or _default_label_budget(duration_s, role)
    target = max(3, min(target, 10, len(times)))

    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.dropna().empty:
        return [0, len(times) - 1] if len(times) > 1 else [0]

    value_span = max(float(numeric.max() - numeric.min()), 1e-6)
    center_value = float(numeric.median())
    elapsed = (times - times.iloc[0]).dt.total_seconds()
    min_gap_s = max(duration_s / max(target * 1.7, 1.0), median_step_s * 2.0)

    diffs = numeric.diff().abs().fillna(0.0)
    next_diffs = numeric.diff(-1).abs().fillna(0.0)
    event_strength = (pd.concat([diffs, next_diffs], axis=1).max(axis=1) / value_span).fillna(0.0)

    candidates: set[int] = {0, len(times) - 1}
    candidates.update(select_extreme_indices(numeric, min(6, target + 2)))

    event_threshold = float(event_strength.quantile(0.88 if role == "power" else 0.92))
    for idx, strength in enumerate(event_strength):
        if float(strength) >= event_threshold and strength > 0:
            candidates.add(idx)

    coverage_count = min(target + 2, max(4, target))
    for step in range(coverage_count):
        raw = round(step * (len(times) - 1) / max(1, coverage_count - 1))
        candidates.add(raw)

    ordered = sorted(
        candidates,
        key=lambda idx: _score_candidate(
            idx,
            numeric,
            event_strength,
            center_value,
            value_span,
            len(times),
            role,
        ),
        reverse=True,
    )

    bin_count = min(max(target + 1, 4), 10)
    used_bins: set[int] = set()
    selected: list[int] = []

    def _bin_of(index: int) -> int:
        return min(bin_count - 1, round(index * (bin_count - 1) / max(1, len(times) - 1)))

    for idx in ordered:
        current_time = float(elapsed.iloc[idx])
        if any(abs(current_time - float(elapsed.iloc[chosen])) < min_gap_s for chosen in selected):
            continue
        current_bin = _bin_of(idx)
        if current_bin in used_bins and len(selected) < max(2, target // 2):
            continue
        selected.append(idx)
        used_bins.add(current_bin)
        if len(selected) >= target:
            break

    if len(selected) < target:
        for idx in sorted(candidates):
            current_time = float(elapsed.iloc[idx])
            if any(abs(current_time - float(elapsed.iloc[chosen])) < (min_gap_s * 0.65) for chosen in selected):
                continue
            selected.append(idx)
            if len(selected) >= target:
                break

    return sorted(set(selected))


def _bbox_overlaps(box: Bbox, other_boxes: list[Bbox], pad_px: float = 6.0) -> bool:
    padded = Bbox.from_extents(
        box.x0 - pad_px,
        box.y0 - pad_px,
        box.x1 + pad_px,
        box.y1 + pad_px,
    )
    return any(padded.overlaps(other) for other in other_boxes)


# ─── Anotación principal ──────────────────────────────────────────────────────
def annotate_values(
    axis: plt.Axes,
    times: pd.Series,
    values: pd.Series,
    indices: list[int],
    label_template: str,
    text_color: str,
    box_facecolor: str,
    box_edgecolor: str,
    style: LabelStyle,
    force_all: bool = False,
) -> None:
    """Dibuja marcadores y etiquetas de valor en los índices indicados."""
    figure = axis.figure
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    placed_boxes: list[Bbox] = []
    axis_box = axis.get_window_extent(renderer)
    y_min, y_max = axis.get_ylim()
    y_span = max(y_max - y_min, 1e-6)

    for idx in indices:
        x = times.iloc[idx]
        y = float(values.iloc[idx])
        marker = axis.scatter([x], [y], color=text_color, s=style.marker_size, zorder=6)
        y_fraction = (y - y_min) / y_span
        x_fraction = idx / max(1, len(times) - 1)
        variants = _placement_variants(style, x_fraction, y_fraction)
        placed = False

        fallback_label = None
        fallback_bbox = None
        for variant in variants:
            label = axis.annotate(
                label_template.format(value=y),
                xy=(x, y),
                xytext=(variant.x_offset, variant.y_offset),
                textcoords="offset points",
                ha=variant.horizontal_alignment,
                va=variant.vertical_alignment,
                fontsize=variant.font_size,
                color=text_color,
                bbox={
                    "boxstyle": f"round,pad={variant.box_pad},rounding_size={variant.box_rounding}",
                    "facecolor": box_facecolor,
                    "edgecolor": box_edgecolor,
                    "linewidth": variant.box_linewidth,
                    "alpha": variant.box_alpha,
                },
            )
            figure.canvas.draw()
            bbox = label.get_window_extent(renderer)
            if fallback_label is None:
                fallback_label = label
                fallback_bbox = bbox
            if (
                _bbox_overlaps(bbox, placed_boxes)
                or bbox.x0 < axis_box.x0
                or bbox.x1 > axis_box.x1
                or bbox.y0 < axis_box.y0
                or bbox.y1 > axis_box.y1
            ):
                if label is not fallback_label:
                    label.remove()
                continue
            if fallback_label is not None and fallback_label is not label:
                fallback_label.remove()
            placed_boxes.append(bbox)
            placed = True
            break

        if not placed:
            if force_all and fallback_label is not None and fallback_bbox is not None:
                placed_boxes.append(fallback_bbox)
            else:
                if fallback_label is not None:
                    fallback_label.remove()
                marker.remove()


def _placement_variants(style: LabelStyle, x_fraction: float, y_fraction: float) -> list[LabelStyle]:
    prefer_above = y_fraction < 0.7
    prefer_right = x_fraction < 0.75

    def _variant(x_mul: int, y_mul: int, ha: str, va: str) -> LabelStyle:
        return LabelStyle(
            x_offset=abs(style.x_offset) * x_mul,
            y_offset=abs(style.y_offset) * y_mul,
            horizontal_alignment=ha,
            vertical_alignment=va,
            font_size=style.font_size,
            marker_size=style.marker_size,
            box_pad=style.box_pad,
            box_rounding=style.box_rounding,
            box_linewidth=style.box_linewidth,
            box_alpha=style.box_alpha,
        )

    vertical_order = [1, -1] if prefer_above else [-1, 1]
    horizontal_order = [1, -1] if prefer_right else [-1, 1]
    variants: list[LabelStyle] = []
    for y_mul in vertical_order:
        for x_mul in horizontal_order:
            variants.append(
                _variant(
                    x_mul,
                    y_mul,
                    "left" if x_mul > 0 else "right",
                    "bottom" if y_mul > 0 else "top",
                )
            )
    return variants


def annotate_frequency(
    axis: plt.Axes,
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    freq_color: str,
    count: int | None = None,
) -> None:
    role = "long" if _series_duration_seconds(df[time_col]) >= 6 * 3600 else "frequency"
    indices = plan_adaptive_label_indices(
        df[time_col],
        df[freq_col],
        role=role,
        target_count=count,
    )
    annotate_values(
        axis,
        df[time_col], df[freq_col],
        indices,
        "{value:.3f} Hz",
        freq_color, "#DCEAF7", freq_color,
        FREQ_STYLE,
    )


def annotate_power(
    axis: plt.Axes,
    df: pd.DataFrame,
    time_col: str,
    power_col: str,
    power_unit: str,
    power_color: str,
    count: int | None = None,
    interval_s: float | None = None,
    min_visible: int = 5,
    force_min_visible: bool = False,
) -> None:
    role = "long" if _series_duration_seconds(df[time_col]) >= 6 * 3600 else "power"
    indices = plan_adaptive_label_indices(
        df[time_col],
        df[power_col],
        role=role,
        target_count=count if count else 8,
    )
    if len(indices) < min_visible and len(df) >= min_visible:
        indices = [
            round(step * (len(df) - 1) / max(1, min_visible - 1))
            for step in range(min_visible)
        ]
    annotate_values(
        axis,
        df[time_col], df[power_col],
        indices,
        f"{{value:.3f}} {power_unit}",
        power_color, "#DFF2E3", power_color,
        POWER_STYLE,
        force_all=force_min_visible,
    )


def add_frequency_step_labels(
    ax_freq: plt.Axes,
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    freq_color: str,
    label_min_freq: float | None = 60.2,
    force_all: bool = False,
    min_step_hz: float = MIN_FREQUENCY_STEP_HZ,
) -> None:
    """Agrega etiquetas de frecuencia en cada escalón detectado."""
    freq = pd.to_numeric(df[freq_col], errors="coerce")
    step_changes = freq.diff().abs().fillna(0.0) >= min_step_hz
    steps = step_changes.cumsum()
    grouped = df.assign(_step_group=steps).groupby("_step_group", sort=True)

    ax_freq.figure.canvas.draw()
    renderer = ax_freq.figure.canvas.get_renderer()
    placed_boxes: list = []

    for _, group in grouped:
        if group.empty:
            continue
        freq_val = round(float(pd.to_numeric(group[freq_col], errors="coerce").median()), 2)
        if label_min_freq is not None and freq_val < label_min_freq - 0.01:
            continue
        t_mid = group[time_col].iloc[len(group) // 2]
        y_pos = float(group[freq_col].iloc[len(group) // 2])
        offset = 12 if len(placed_boxes) % 2 == 0 else -18
        text = ax_freq.annotate(
            f"{freq_val:.2f} Hz",
            xy=(t_mid, y_pos),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=8.0, fontweight="bold", color=freq_color,
            bbox={
                "boxstyle": "round,pad=0.18,rounding_size=0.12",
                "facecolor": "white",
                "edgecolor": freq_color,
                "linewidth": 0.9, "alpha": 0.95,
            },
            zorder=5,
        )
        ax_freq.figure.canvas.draw()
        bbox = text.get_window_extent(renderer)
        if not force_all and _bbox_overlaps(bbox, placed_boxes, pad_px=10.0):
            text.remove()
            continue
        placed_boxes.append(bbox)
