"""
tests/simple.py — Motor para pruebas de caso único.

Maneja: P1, P2, P4, P6, P12, P13, P25, P26, P28
Flujo base: cargar archivos, empatar tiempos y generar evidencia gráfica.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.io import (
    detect_columns,
    detect_time_column,
    find_matching_header,
    load_table,
    prepare_dataframe,
    prepare_signal_dataframe,
)
from core.merge import (
    MERGE_TOLERANCE_SECONDS,
    POWER_SCALE_THRESHOLD,
    align_dates,
    infer_drawstyle,
    load_frequency_df,
    load_power_df,
    merge_time_series,
    simplify_for_plot,
)
from core.naming import artifact_filename, dataframe_date_label, unique_path
from core.plot import (
    DEFAULT_FREQ_COLOR,
    DEFAULT_POWER_COLOR,
    plot_quality_case,
    plot_p25_capacidad_instalada_neta,
    plot_p25_daily_indicators,
    plot_p25_frequency,
    plot_p25_net_injection,
    plot_p25_no_injection_compliance,
    plot_p25_voltage,
    plot_p28_frequency_control_summary,
    plot_p28_power_behavior_compare,
    plot_reactive_pf_case,
    plot_single_case,
    plot_voltage_case,
)
from tests.registry import TestConfig


@dataclass
class SimpleResult:
    output_path: Path
    row_count: int
    test_id: str
    caso: str | None = None
    df: pd.DataFrame | None = None
    output_paths: list[Path] | None = None
    frames: dict[str, pd.DataFrame] | None = None


SIGNAL_SPECS = {
    "frequency": [("frequency",), ("frecuencia",)],
    "voltage": [("voltage",), ("tension",), ("volt",)],
    "phase_v1n": [("v1n",), ("phase", "v1n")],
    "phase_v2n": [("v2n",), ("phase", "v2n")],
    "phase_v3n": [("v3n",), ("phase", "v3n")],
    "reactive_power": [("reactive", "power"), ("potencia", "reactiva"), ("mvar",)],
    "power_factor": [("power", "factor"), ("factor", "potencia"), ("fp",)],
    "active_power": [("active", "power"), ("potencia", "activa")],
    "thd_voltage": [("thd", "voltage"), ("thd", "tension"), ("thdv",)],
    "thd_current": [("thd", "current"), ("thd", "corriente"), ("thdi",)],
    "unbalance": [("unbalance",), ("desbalance",)],
    "current": [("current",), ("corriente",)],
}

P28_SOURCE_TESTS = {
    "P1": "Rango de frecuencia",
    "P2": "ROCOF",
    "P3": "Respuesta a alta frecuencia",
    "P8": "Respuesta a baja frecuencia",
    "P9": "Control primario de frecuencia",
}


def _output_path(
    config: TestConfig,
    output_dir: Path,
    df: pd.DataFrame,
    descriptor: str = "grafica",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = artifact_filename(
        output_dir,
        descriptor=descriptor,
        ext=".png",
        test_id=config.id,
        df=df,
    )
    return unique_path(output_dir / file_name)


def _collect_p28_evidence(output_dir: Path) -> dict[str, list[Path]]:
    evidence: dict[str, list[Path]] = {}
    for test_id in P28_SOURCE_TESTS:
        matches = [
            path
            for path in output_dir.rglob(f"*_{test_id}_*.png")
            if path.is_file() and "_P28_" not in path.name
        ]
        evidence[test_id] = sorted(
            matches,
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
    return evidence


def _latest_p28_summary_tables(output_dir: Path) -> dict[str, dict[str, pd.DataFrame]]:
    summaries: dict[str, dict[str, pd.DataFrame]] = {}
    for test_id in ("P3", "P8", "P9"):
        candidates = sorted(
            output_dir.rglob(f"*_{test_id}_resumen_estados_*.xlsx"),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        if not candidates:
            continue
        workbook = candidates[0]
        sheets = pd.read_excel(workbook, sheet_name=None)
        summaries[test_id] = {
            sheet_name: frame.assign(test_id=test_id, caso=sheet_name, fuente=workbook.name)
            for sheet_name, frame in sheets.items()
            if {"Frecuencia [Hz]", "Potencia [MW]"}.issubset(frame.columns)
        }
    return summaries


def _load_p28_series_tables(output_dir: Path) -> dict[str, dict[str, pd.DataFrame]]:
    cache_dir = output_dir / ".p28_series"
    series_tables: dict[str, dict[str, pd.DataFrame]] = {}
    if not cache_dir.exists():
        return series_tables

    for test_id in ("P3", "P8", "P9"):
        case_tables: dict[str, pd.DataFrame] = {}
        for path in sorted(cache_dir.glob(f"{test_id}_*.csv")):
            frame = pd.read_csv(path)
            if not {"time", "active_power", "caso"}.issubset(frame.columns):
                continue
            caso = str(frame["caso"].iloc[0]) if not frame.empty else path.stem.split("_", 1)[-1]
            case_tables[caso] = frame
        if case_tables:
            series_tables[test_id] = case_tables
    return series_tables


def run_p28_summary(config: TestConfig, output_dir: Path) -> SimpleResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = _collect_p28_evidence(output_dir)
    total = sum(len(paths) for paths in evidence.values())
    if total == 0:
        required = ", ".join(P28_SOURCE_TESTS)
        raise ValueError(
            f"No se encontraron evidencias PNG previas para P28. "
            f"Genera primero al menos una evidencia de: {required}."
        )
    summary_tables = _latest_p28_summary_tables(output_dir)
    series_tables = _load_p28_series_tables(output_dir)

    output_path = _output_path(config, output_dir, pd.DataFrame(), descriptor="resumen_control_frecuencia")
    plot_p28_frequency_control_summary(
        evidence=evidence,
        summary_tables=summary_tables,
        output_path=output_path,
        title="P28 – Control de frecuencia · Resumen de evidencias",
    )
    output_paths = [output_path]
    for source_test_id in ("P3", "P8", "P9"):
        tables = series_tables.get(source_test_id)
        if not tables:
            continue
        compare_path = _output_path(
            config,
            output_dir,
            pd.DataFrame(),
            descriptor=f"{source_test_id}_comparativo_potencia_estatismos",
        )
        plot_p28_power_behavior_compare(
            tables,
            compare_path,
            "Potencia activa por caso",
        )
        output_paths.append(compare_path)
    summary = pd.DataFrame(
        [
            {
                "test_id": test_id,
                "descripcion": P28_SOURCE_TESTS[test_id],
                "evidencias_png": len(paths),
                "evidencia_mas_reciente": paths[0].name if paths else "",
            }
            for test_id, paths in evidence.items()
        ]
    )
    return SimpleResult(
        output_path=output_path,
        row_count=total,
        test_id=config.id,
        df=summary,
        output_paths=output_paths,
        frames={"summary": summary},
    )


def _load_signal_subset(path: Path, aliases: list[str]) -> pd.DataFrame | None:
    raw = load_table(path)
    time_col = detect_time_column(raw.columns)
    signal_cols: dict[str, str] = {}
    for alias in aliases:
        match = find_matching_header(raw.columns, SIGNAL_SPECS[alias])
        if match is not None:
            signal_cols[alias] = match

    phase_voltage_cols: dict[str, str] = {}
    if "voltage" in aliases and "voltage" not in signal_cols:
        for alias in ("phase_v1n", "phase_v2n", "phase_v3n"):
            match = find_matching_header(raw.columns, SIGNAL_SPECS[alias])
            if match is not None:
                phase_voltage_cols[alias] = match
        signal_cols.update(phase_voltage_cols)

    if not signal_cols:
        return None

    df = prepare_signal_dataframe(raw, time_col, signal_cols)
    if phase_voltage_cols:
        df["voltage"] = df[list(phase_voltage_cols)].mean(axis=1)
        df = df.drop(columns=list(phase_voltage_cols))
    if (
        "active_power" in df.columns
        and df["active_power"].abs().quantile(0.95) > POWER_SCALE_THRESHOLD
    ):
        df["active_power"] = df["active_power"] / 1000.0
    return df


def _load_required_signals(path: Path, signal_map: dict[str, list[tuple[str, ...]]]) -> pd.DataFrame:
    raw = load_table(path)
    time_col = detect_time_column(raw.columns)
    resolved: dict[str, str] = {}
    for alias, token_groups in signal_map.items():
        match = find_matching_header(raw.columns, token_groups)
        if match is None:
            raise ValueError(
                f"No se encontró la señal '{alias}' en {path.name}. Columnas disponibles: {list(raw.columns)}"
            )
        resolved[alias] = match
    return prepare_signal_dataframe(raw, time_col, resolved)


def _p4_context_seconds(df: pd.DataFrame) -> float:
    if len(df) <= 1:
        return 0.0
    duration_s = float((df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds())
    diffs = df["time"].diff().dt.total_seconds().dropna()
    diffs = diffs[diffs > 0]
    median_step_s = float(diffs.median()) if not diffs.empty else 1.0
    return max(median_step_s * 5.0, min(30.0, duration_s * 0.08))


def _trim_p4_window(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 8:
        return df

    work = df.sort_values("time").reset_index(drop=True)
    freq = pd.to_numeric(work["frequency"], errors="coerce")
    freq_delta = freq.diff().abs().fillna(0.0)
    threshold = max(float(freq_delta.quantile(0.95)), 0.01)
    step_indices = freq_delta[freq_delta >= threshold].index.to_list()
    if not step_indices:
        return work

    context_s = _p4_context_seconds(work)
    start_time = work.loc[step_indices[0], "time"] - pd.Timedelta(seconds=context_s)
    end_time = work.loc[step_indices[-1], "time"] + pd.Timedelta(seconds=context_s)
    trimmed = work[(work["time"] >= start_time) & (work["time"] <= end_time)].reset_index(drop=True)
    return trimmed if len(trimmed) >= 8 else work


def _trim_p2_first_step(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 8:
        return df

    work = df.sort_values("time").reset_index(drop=True)
    freq = pd.to_numeric(work["frequency"], errors="coerce")
    clean = freq.dropna()
    if clean.empty:
        return work

    baseline = float(clean.iloc[0])
    away_threshold = max(abs(baseline) * 0.001, 0.05)
    return_threshold = max(abs(baseline) * 0.0005, 0.03)
    away = (freq - baseline).abs() >= away_threshold
    away_indices = away[away].index.to_list()
    if not away_indices:
        return work

    first_step = away_indices[0]
    return_candidates = [
        idx
        for idx in range(first_step + 1, len(work))
        if pd.notna(freq.iloc[idx]) and abs(float(freq.iloc[idx]) - baseline) <= return_threshold
    ]
    step_end = return_candidates[0] if return_candidates else len(work) - 1
    context_s = _p4_context_seconds(work)
    start_time = work.loc[first_step, "time"] - pd.Timedelta(seconds=context_s)
    end_time = work.loc[step_end, "time"] + pd.Timedelta(
        seconds=_p2_post_recovery_seconds(work, context_s)
    )
    trimmed = work[(work["time"] >= start_time) & (work["time"] <= end_time)].reset_index(drop=True)
    return trimmed if len(trimmed) >= 8 else work


def _p2_post_recovery_seconds(df: pd.DataFrame, pre_context_s: float) -> float:
    if len(df) <= 1:
        return 0.0
    diffs = df["time"].diff().dt.total_seconds().dropna()
    diffs = diffs[diffs > 0]
    median_step_s = float(diffs.median()) if not diffs.empty else 1.0
    return max(median_step_s * 6.0, min(12.0, pre_context_s * 0.40))


def _p2_recovery_index(df: pd.DataFrame, first_step: int, step_end: int) -> int:
    if "active_power" not in df.columns or first_step >= len(df) - 1:
        return min(len(df) - 1, first_step)

    power = pd.to_numeric(df["active_power"], errors="coerce")
    step_end = max(first_step, min(step_end, len(df) - 1))
    post = power.iloc[first_step : step_end + 1].dropna()
    if post.empty:
        return step_end

    target = float(post.quantile(0.95))
    tolerance = max(abs(target) * 0.015, 0.03)
    for idx in range(first_step, step_end + 1):
        value = power.iloc[idx]
        if pd.notna(value) and float(value) >= target - tolerance:
            return idx
    return step_end


def _p4_power_ylim(df: pd.DataFrame) -> tuple[float, float] | None:
    if "active_power" not in df.columns:
        return None
    power = pd.to_numeric(df["active_power"], errors="coerce").dropna()
    if power.empty:
        return None

    lower = float(power.quantile(0.05))
    upper = float(power.quantile(0.95))
    if lower == upper:
        center = float(power.median())
        pad = max(abs(center) * 0.02, 0.05)
        return center - pad, center + pad

    pad = max((upper - lower) * 0.35, abs(float(power.median())) * 0.01, 0.03)
    return lower - pad, upper + pad


def _load_p25_poi_signals(path: Path) -> pd.DataFrame:
    raw = load_table(path)
    time_col = detect_time_column(raw.columns)
    freq_col = find_matching_header(raw.columns, SIGNAL_SPECS["frequency"])
    if freq_col is None:
        raise ValueError(
            f"No se encontró la frecuencia en {path.name}. Columnas disponibles: {list(raw.columns)}"
        )

    poi_power_col = find_matching_header(raw.columns, SIGNAL_SPECS["active_power"])
    direct_voltage = find_matching_header(raw.columns, SIGNAL_SPECS["voltage"])
    if direct_voltage is not None:
        signal_cols = {"frequency": freq_col, "voltage": direct_voltage}
        if poi_power_col is not None:
            signal_cols["active_power"] = poi_power_col
        return prepare_signal_dataframe(
            raw,
            time_col,
            signal_cols,
        )

    phase_cols = []
    for alias in ("phase_v1n", "phase_v2n", "phase_v3n"):
        match = find_matching_header(raw.columns, SIGNAL_SPECS[alias])
        if match is not None:
            phase_cols.append((alias, match))
    if not phase_cols:
        raise ValueError(
            f"No se encontró voltaje directo ni fases V1N/V2N/V3N en {path.name}. Columnas disponibles: {list(raw.columns)}"
        )

    signal_cols = {"frequency": freq_col, **{alias: column for alias, column in phase_cols}}
    if poi_power_col is not None:
        signal_cols["active_power"] = poi_power_col
    prepared = prepare_signal_dataframe(
        raw,
        time_col,
        signal_cols,
    )
    voltage_cols = [alias for alias, _ in phase_cols]
    prepared["voltage"] = prepared[voltage_cols].mean(axis=1)
    keep = ["time", "frequency", "voltage"]
    if "active_power" in prepared.columns:
        keep.append("active_power")
    return prepared[keep]


def _merge_frames_with_tolerance(
    frames: list[pd.DataFrame],
    tolerance_s: float,
) -> pd.DataFrame:
    merged = frames[0].copy().sort_values("time").reset_index(drop=True)
    for frame in frames[1:]:
        aligned = align_dates(frame, merged)
        merged = pd.merge_asof(
            merged.sort_values("time"),
            aligned.sort_values("time"),
            on="time",
            direction="nearest",
            tolerance=pd.Timedelta(seconds=tolerance_s),
        )
    value_cols = [column for column in merged.columns if column != "time"]
    merged = merged.dropna(subset=value_cols).sort_values("time").reset_index(drop=True)
    if merged.empty:
        raise ValueError(
            "No fue posible alinear POI, generación y carga dentro de la tolerancia temporal. "
            "Verifica que los tres archivos correspondan al mismo periodo de 15 días."
        )
    return merged


def _normalize_voltage_pu(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return pd.to_numeric(series, errors="coerce")
    median = float(clean.abs().median())
    if 0.2 <= median <= 2.0 or median <= 1e-9:
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(series, errors="coerce") / median


def _build_p25_output_dir(output_dir: Path) -> Path:
    graph_dir = output_dir / "graficas"
    graph_dir.mkdir(parents=True, exist_ok=True)
    return graph_dir


def _build_p25_output_paths(output_dir: Path, df: pd.DataFrame) -> dict[str, Path]:
    graph_dir = _build_p25_output_dir(output_dir)
    date_label = dataframe_date_label(df)
    return {
        "inyeccion_neta": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="inyeccion_neta_poi",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
        "frecuencia": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="frecuencia_poi",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
        "cumplimiento_no_inyeccion": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="cumplimiento_no_inyeccion",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
        "voltaje": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="voltaje_poi",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
        "indicadores": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="energia_disponibilidad_diaria",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
        "capacidad_neta": unique_path(
            graph_dir
            / artifact_filename(
                graph_dir,
                descriptor="capacidad_instalada_neta",
                ext=".png",
                test_id="P25",
                date_label=date_label,
            )
        ),
    }


def _compute_daily_indicators(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy().sort_values("time").reset_index(drop=True)
    if work.empty:
        raise ValueError("No hay datos alineados para calcular indicadores diarios.")

    next_time = work["time"].shift(-1)
    delta_hours = (next_time - work["time"]).dt.total_seconds() / 3600.0
    valid_deltas = delta_hours[(delta_hours > 0) & (delta_hours <= 0.5)]
    default_hours = float(valid_deltas.median()) if not valid_deltas.empty else (5.0 / 60.0)
    delta_hours = delta_hours.fillna(default_hours).clip(lower=1.0 / 60.0, upper=0.5)
    work["interval_h"] = delta_hours
    work["day"] = work["time"].dt.floor("D")
    work["energia_generada_mwh"] = work["generation_mw"] * work["interval_h"]
    work["energia_carga_mwh"] = work["load_mw"] * work["interval_h"]
    work["horas_operacion_h"] = work["interval_h"].where(work["generation_mw"] > 0.01, 0.0)

    daily = (
        work.groupby("day", sort=True)
        .agg(
            energia_generada_mwh=("energia_generada_mwh", "sum"),
            energia_carga_mwh=("energia_carga_mwh", "sum"),
            horas_operacion_h=("horas_operacion_h", "sum"),
        )
        .reset_index()
    )
    daily["day_label"] = daily["day"].dt.strftime("%Y-%m-%d")
    return daily


def _load_p25_load_signals(path: Path) -> pd.DataFrame:
    """Carga archivo CARGA con frecuencia y potencia activa."""
    raw = load_table(path)
    time_col = detect_time_column(raw.columns)
    freq_col = find_matching_header(raw.columns, SIGNAL_SPECS["frequency"])
    if freq_col is None:
        raise ValueError(
            f"No se encontró la frecuencia en {path.name}. Columnas disponibles: {list(raw.columns)}"
        )
    signal_cols = {"frequency": freq_col}
    ap_col = find_matching_header(raw.columns, SIGNAL_SPECS["active_power"])
    if ap_col is None:
        raise ValueError(
            f"No se encontró la potencia activa de CARGA en {path.name}. "
            f"Columnas disponibles: {list(raw.columns)}"
        )
    signal_cols["active_power"] = ap_col
    return prepare_signal_dataframe(raw, time_col, signal_cols)


def run_p25(
    config: TestConfig,
    poi_path: Path,
    gen_path: Path,
    load_path: Path,
    output_dir: Path,
) -> SimpleResult:
    poi_df = _load_p25_poi_signals(poi_path)
    gen_df = _load_required_signals(gen_path, {"active_power": SIGNAL_SPECS["active_power"]})
    load_df = _load_p25_load_signals(load_path)

    poi_df = poi_df.rename(columns={"voltage": "voltage_raw"})
    if "active_power" in poi_df.columns:
        poi_df = poi_df.rename(columns={"active_power": "poi_active_power_mw"})
    gen_df = gen_df.rename(columns={"active_power": "generation_mw"})
    if "active_power" in load_df.columns:
        load_df = load_df.rename(columns={"active_power": "load_mw"})

    if "poi_active_power_mw" in poi_df.columns and poi_df["poi_active_power_mw"].abs().quantile(0.95) > POWER_SCALE_THRESHOLD:
        poi_df["poi_active_power_mw"] = poi_df["poi_active_power_mw"] / 1000.0
    if gen_df["generation_mw"].abs().quantile(0.95) > POWER_SCALE_THRESHOLD:
        gen_df["generation_mw"] = gen_df["generation_mw"] / 1000.0
    if "load_mw" in load_df.columns and load_df["load_mw"].abs().quantile(0.95) > POWER_SCALE_THRESHOLD:
        load_df["load_mw"] = load_df["load_mw"] / 1000.0

    # ── Lógica: CARGA aporta time + frequency como referencia temporal ──
    # La frecuencia de CARGA define los puntos de medición.
    # Potencia neta = P_generacion - P_carga.

    poi_aligned = align_dates(poi_df, load_df)
    gen_aligned = align_dates(gen_df, load_df)

    # Base: CARGA con su frecuencia
    merge_cols = ["time", "frequency"]
    if "load_mw" in load_df.columns:
        merge_cols.append("load_mw")
    
    merged = pd.merge_asof(
        load_df[merge_cols].sort_values("time"),
        poi_aligned[["time", "poi_active_power_mw", "voltage_raw"]].sort_values("time"),
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=15 * 60),
    )
    merged = pd.merge_asof(
        merged.sort_values("time"),
        gen_aligned[["time", "generation_mw"]].sort_values("time"),
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=15 * 60),
    )

    merged = merged.dropna(subset=["frequency"]).reset_index(drop=True)

    merged["net_injection_mw"] = merged["generation_mw"] - merged["load_mw"]

    merged["voltage_pu"] = _normalize_voltage_pu(merged["voltage_raw"])
    merged = merged.dropna(
        subset=["frequency", "voltage_pu", "generation_mw", "load_mw", "net_injection_mw"]
    ).reset_index(drop=True)
    if merged.empty:
        raise ValueError("No quedaron datos válidos tras alinear CARGA (frecuencia) con POI (potencia activa).")

    daily = _compute_daily_indicators(merged)
    output_paths = _build_p25_output_paths(output_dir, merged)

    plot_p25_net_injection(
        merged,
        output_paths["inyeccion_neta"],
        "Inyección neta en el POI – 15 días",
    )
    plot_p25_no_injection_compliance(
        merged,
        output_paths["cumplimiento_no_inyeccion"],
        "Cumplimiento de no inyección – P_neta ≤ 0 MW",
    )
    plot_p25_frequency(
        merged,
        output_paths["frecuencia"],
        "Frecuencia en el POI – 15 días (Código de Red 2.0)",
    )
    plot_p25_voltage(
        merged,
        output_paths["voltaje"],
        "Voltaje en el POI – 15 días (0.95–1.05 p.u.)",
    )
    plot_p25_daily_indicators(
        daily,
        output_paths["indicadores"],
        "Energía y disponibilidad diaria – 15 días",
    )
    plot_p25_capacidad_instalada_neta(
        merged,
        output_paths["capacidad_neta"],
        "Capacidad Instalada Neta – P25 (Centrales Asíncronas)",
    )

    ordered_paths = [
        output_paths["inyeccion_neta"],
        output_paths["cumplimiento_no_inyeccion"],
        output_paths["frecuencia"],
        output_paths["voltaje"],
        output_paths["indicadores"],
        output_paths["capacidad_neta"],
    ]
    return SimpleResult(
        output_path=ordered_paths[0],
        row_count=len(merged),
        test_id=config.id,
        df=merged.copy(),
        output_paths=ordered_paths,
        frames={"merged": merged.copy(), "daily": daily.copy()},
    )


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    merged = frames[0].copy().sort_values("time").reset_index(drop=True)
    for frame in frames[1:]:
        aligned = align_dates(frame, merged)
        merged = pd.merge_asof(
            merged.sort_values("time"),
            aligned.sort_values("time"),
            on="time",
            direction="nearest",
            tolerance=pd.Timedelta(seconds=MERGE_TOLERANCE_SECONDS),
        )
    merged = merged.sort_values("time").reset_index(drop=True)
    value_cols = [c for c in merged.columns if c != "time"]
    merged = merged.dropna(subset=value_cols, how="all")
    if merged.empty:
        raise ValueError(
            "No fue posible construir una serie útil con las señales requeridas."
        )
    return merged


def _load_combined_signals(
    poi_path: Path,
    gen_path: Path,
    aliases: list[str],
    require_all: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    remaining = list(aliases)

    for path in (poi_path, gen_path):
        if not remaining:
            break
        frame = _load_signal_subset(path, remaining)
        if frame is None:
            continue
        frames.append(frame)
        remaining = [alias for alias in remaining if alias not in frame.columns]

    if not frames:
        raise ValueError(
            "No se encontraron las señales requeridas en los archivos proporcionados."
        )

    merged = _merge_frames(frames)
    missing = [alias for alias in aliases if alias not in merged.columns]
    if require_all and missing:
        raise ValueError(f"Señales no encontradas: {', '.join(missing)}")
    return merged


def _run_voltage_case(
    config: TestConfig,
    criterion_id: int,
    poi_path: Path,
    gen_path: Path,
    output_dir: Path,
) -> SimpleResult:
    df = _load_combined_signals(poi_path, gen_path, ["voltage"])
    lower_limit, upper_limit = (0.90, 1.10) if criterion_id == 11 else (0.90, 1.10)
    output_path = _output_path(config, output_dir, df, descriptor="voltaje_poi")
    plot_voltage_case(
        df=df,
        time_col="time",
        voltage_col="voltage",
        output_path=output_path,
        title=config.titulo(),
        lower_limit=lower_limit,
        upper_limit=upper_limit,
    )
    return SimpleResult(
        output_path=output_path,
        row_count=len(df),
        test_id=config.id,
        df=df.copy(),
    )


def _run_reactive_case(
    config: TestConfig,
    poi_path: Path,
    gen_path: Path,
    output_dir: Path,
) -> SimpleResult:
    df = _load_combined_signals(
        poi_path,
        gen_path,
        ["reactive_power", "power_factor", "active_power"],
        require_all=False,
    )
    if "reactive_power" not in df.columns:
        raise ValueError("No se encontró la señal de potencia reactiva para P13.")
    if "power_factor" not in df.columns:
        if "active_power" not in df.columns:
            raise ValueError(
                "No se encontró factor de potencia ni potencia activa para estimarlo en P13."
            )
        apparent = (df["active_power"] ** 2 + df["reactive_power"] ** 2) ** 0.5
        df["power_factor"] = df["active_power"].abs() / apparent.replace(0, pd.NA)
        df["power_factor"] = df["power_factor"].fillna(0.0)
    output_path = _output_path(config, output_dir, df, descriptor="potencia_reactiva_fp")
    plot_reactive_pf_case(
        df=df,
        time_col="time",
        reactive_col="reactive_power",
        power_factor_col="power_factor",
        output_path=output_path,
        title=config.titulo(),
    )
    return SimpleResult(
        output_path=output_path,
        row_count=len(df),
        test_id=config.id,
        df=df.copy(),
    )


def _run_quality_case(
    config: TestConfig,
    poi_path: Path,
    gen_path: Path,
    output_dir: Path,
) -> SimpleResult:
    df = _load_combined_signals(
        poi_path,
        gen_path,
        ["thd_voltage", "thd_current", "unbalance", "power_factor", "current"],
        require_all=False,
    )
    quality_signals = [
        ("thd_voltage", "THD tension"),
        ("thd_current", "THD corriente"),
        ("unbalance", "Desbalance"),
        ("power_factor", "Factor de potencia"),
        ("current", "Corriente"),
    ]
    available = [(col, label) for col, label in quality_signals if col in df.columns]
    if not available:
        raise ValueError(
            "No se encontraron indicadores de calidad de potencia para graficar."
        )

    output_path = _output_path(config, output_dir, df, descriptor="calidad_energia")
    plot_quality_case(
        df=df,
        time_col="time",
        signal_columns=available[:4],
        output_path=output_path,
        title=config.titulo(),
    )
    return SimpleResult(
        output_path=output_path,
        row_count=len(df),
        test_id=config.id,
        df=df.copy(),
    )


def run_simple(
    config: TestConfig,
    poi_path: Path,
    gen_path: Path,
    output_dir: Path,
    criterion_id: int | None = None,
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
) -> SimpleResult:
    """
    Ejecuta el análisis de una prueba simple:
    1. Carga POI/FREC y GEN
    2. Empata tiempos con merge_asof
    3. Genera la gráfica doble eje
    """
    if config.id == "P12":
        return _run_voltage_case(
            config,
            criterion_id or 12,
            poi_path,
            gen_path,
            output_dir,
        )
    if config.id == "P13":
        return _run_reactive_case(config, poi_path, gen_path, output_dir)
    if config.id == "P26":
        return _run_quality_case(config, poi_path, gen_path, output_dir)

    # Cargar frecuencia (puede ser CSV o Excel)
    freq_df = load_frequency_df(poi_path)
    
    # Empatar tiempos (solo si hay potencia activa)
    try:
        power_df = load_power_df(gen_path)
        df = merge_time_series(freq_df, power_df)
    except:
        df = freq_df.copy()
        df["time"] = pd.to_datetime(df["time"])
    
    df = simplify_for_plot(df)
    drawstyle = infer_drawstyle(df["frequency"])

    # Construir nombre de salida
    output_path = _output_path(config, output_dir, df, descriptor="grafica")

    # Columna auxiliar (setpoint) si aplica
    aux_col = None
    if config.has_aux_col:
        raw = load_table(poi_path)
        cols = detect_columns(raw.columns)
        if cols.auxiliary_power:
            # Re-cargar con columna auxiliar incluida
            df_full = prepare_dataframe(raw, cols).copy()
            df_full = (
                df_full.sort_values(cols.time.strip())
                .drop_duplicates(subset=[cols.time.strip()])
                .reset_index(drop=True)
            )
            # Renombrar para consistencia
            df_full = df_full.rename(
                columns={
                    cols.time.strip(): "time",
                    cols.frequency.strip(): "frequency",
                    cols.active_power.strip(): "active_power",
                    cols.auxiliary_power.strip(): "aux",
                }
            )
            # Re-merge con gen
            from core.merge import align_dates

            freq_aux = df_full[["time", "frequency", "aux"]].copy()
            freq_aux = align_dates(freq_aux, power_df)
            df = (
                pd.merge_asof(
                    freq_aux.sort_values("time"),
                    power_df.sort_values("time"),
                    on="time",
                    direction="nearest",
                    tolerance=pd.Timedelta(seconds=1.0),
                )
                .dropna(subset=["frequency", "active_power"])
                .reset_index(drop=True)
            )
            aux_col = "aux"

    power_ylim = None
    if config.id == "P2":
        df = _trim_p2_first_step(df)
        df = simplify_for_plot(df)
        drawstyle = infer_drawstyle(df["frequency"])
    if config.id == "P4":
        df = _trim_p4_window(df)
        df = simplify_for_plot(df)
        drawstyle = infer_drawstyle(df["frequency"])
        power_ylim = _p4_power_ylim(df)

    plot_single_case(
        df=df,
        time_col="time",
        freq_col="frequency",
        power_col="active_power",
        output_path=output_path,
        title=config.titulo(),
        power_unit=config.power_unit,
        freq_color=freq_color,
        power_color=power_color,
        aux_col=aux_col,
        drawstyle=drawstyle,
        power_ylim=power_ylim,
    )

    return SimpleResult(
        output_path=output_path,
        row_count=len(df),
        test_id=config.id,
        df=df.copy(),
    )
