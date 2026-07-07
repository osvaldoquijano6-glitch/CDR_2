"""
tests/multi.py — Motor para pruebas de múltiples casos.

Maneja: P3, P8, P9
Flujo por caso: cargar FREC + GEN → empatar → generar gráfica
Al final: exportar Excel resumen de estados de frecuencia
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.naming import artifact_filename, unique_path
from core.merge import (
    load_frequency_df, load_power_df,
    merge_time_series, simplify_for_plot, infer_drawstyle,
)
from core.plot import (
    DEFAULT_FREQ_COLOR,
    DEFAULT_POWER_COLOR,
    plot_multi_case,
    plot_multi_compare_cases,
)
from core.export import build_frequency_state_summary, write_multi_sheet_xlsx
from tests.registry import TestConfig


@dataclass
class CaseResult:
    caso: str
    output_path: Path
    row_count: int
    error: str | None = None
    df: pd.DataFrame | None = None


@dataclass
class MultiResult:
    test_id: str
    cases: list[CaseResult] = field(default_factory=list)
    summary_xlsx: Path | None = None
    compare_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def successful(self) -> list[CaseResult]:
        return [c for c in self.cases if c.error is None]

    @property
    def failed(self) -> list[CaseResult]:
        return [c for c in self.cases if c.error is not None]


def _step_context_seconds(df: pd.DataFrame) -> float:
    if len(df) <= 1:
        return 0.0
    duration_s = float((df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds())
    diffs = df["time"].diff().dt.total_seconds().dropna()
    diffs = diffs[diffs > 0]
    median_step_s = float(diffs.median()) if not diffs.empty else 1.0
    return max(median_step_s * 5.0, min(45.0, duration_s * 0.08))


def _trim_step_window(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 8:
        return df

    work = df.sort_values("time").reset_index(drop=True)
    freq = pd.to_numeric(work["frequency"], errors="coerce")
    freq_delta = freq.diff().abs().fillna(0.0)
    threshold = max(float(freq_delta.quantile(0.95)), 0.01)
    step_indices = freq_delta[freq_delta >= threshold].index.to_list()
    if not step_indices:
        return work

    context_s = _step_context_seconds(work)
    start_time = work.loc[step_indices[0], "time"] - pd.Timedelta(seconds=context_s)
    end_time = work.loc[step_indices[-1], "time"] + pd.Timedelta(seconds=context_s)
    trimmed = work[(work["time"] >= start_time) & (work["time"] <= end_time)].reset_index(drop=True)
    return trimmed if len(trimmed) >= 8 else work


def _write_p28_series_cache(
    output_dir: Path,
    test_id: str,
    caso: str,
    df: pd.DataFrame,
) -> None:
    cache_dir = output_dir / ".p28_series"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_caso = caso.replace("%", "pct").replace("/", "_")
    cache_path = cache_dir / f"{test_id}_{safe_caso}.csv"
    export_df = df[["time", "frequency", "active_power"]].copy()
    export_df["caso"] = caso
    export_df["test_id"] = test_id
    export_df.to_csv(cache_path, index=False)


def run_multi(
    config: TestConfig,
    file_pairs: list[tuple[str, Path, Path]],   # [(caso, poi_path, gen_path), ...]
    output_dir: Path,
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
) -> MultiResult:
    """
    Ejecuta el análisis de una prueba multi-caso.

    Args:
        config: Configuración de la prueba (del registry).
        file_pairs: Lista de tuplas (etiqueta_caso, archivo_frec, archivo_gen).
                    Ejemplo: [("3%", path_frec_3, path_gen_3), ("5%", ...), ("8%", ...)]
        output_dir: Directorio donde guardar las gráficas y el Excel resumen.
        freq_color / power_color: Colores personalizables desde la UI.

    Returns:
        MultiResult con rutas de gráficas y summary Excel.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result = MultiResult(test_id=config.id)
    summary_sheets: list[tuple[str, pd.DataFrame]] = []

    for caso, frec_path, gen_path in file_pairs:
        try:
            # Cargar y empatar
            freq_df = load_frequency_df(frec_path)
            power_df = load_power_df(gen_path)
            df = merge_time_series(freq_df, power_df)
            if config.id == "P8":
                df = _trim_step_window(df)
            df = simplify_for_plot(df)
            drawstyle = infer_drawstyle(df["frequency"])

            # Gráfica
            safe_caso = caso.replace("%", "pct").replace("/", "_")
            output_path = unique_path(
                output_dir
                / artifact_filename(
                    output_dir,
                    descriptor=f"caso_{safe_caso}",
                    ext=".png",
                    test_id=config.id,
                    df=df,
                )
            )
            plot_multi_case(
                df=df,
                time_col="time",
                freq_col="frequency",
                power_col="active_power",
                output_path=output_path,
                title=config.titulo(caso),
                power_unit=config.power_unit,
                freq_color=freq_color,
                power_color=power_color,
                drawstyle=drawstyle,
                step_label_min_freq=None,
                force_step_labels=True,
            )

            # Resumen de estados
            sheet_name = caso[:31]   # Excel limita nombres de hoja a 31 caracteres
            summary = build_frequency_state_summary(
                df, "time", "frequency", "active_power", config.power_unit
            )
            summary_sheets.append((sheet_name, summary))

            result.cases.append(CaseResult(
                caso=caso,
                output_path=output_path,
                row_count=len(df),
                df=df.copy(),
            ))
            _write_p28_series_cache(output_dir, config.id, caso, df)

        except Exception as exc:
            result.cases.append(CaseResult(
                caso=caso,
                output_path=Path(""),
                row_count=0,
                error=str(exc),
            ))
            result.errors.append(f"[{caso}] {exc}")

    # Exportar Excel resumen
    if summary_sheets:
        xlsx_path = unique_path(
            output_dir
            / artifact_filename(
                output_dir,
                descriptor="resumen_estados",
                ext=".xlsx",
                test_id=config.id,
                df=pd.concat([sheet for _, sheet in summary_sheets], ignore_index=True) if summary_sheets else None,
            )
        )
        write_multi_sheet_xlsx(summary_sheets, xlsx_path)
        result.summary_xlsx = xlsx_path

    if len(result.successful) >= 2:
        first_df = result.successful[0].df
        compare_path = unique_path(
            output_dir
            / artifact_filename(
                output_dir,
                descriptor="comparativo_estatismos",
                ext=".png",
                test_id=config.id,
                df=first_df,
            )
        )
        plot_multi_compare_cases(
            result.successful,
            compare_path,
            f"{config.id} – Comparativo de estatismos",
            power_unit=config.power_unit,
        )
        result.compare_path = compare_path

    return result
