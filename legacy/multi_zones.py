"""
tests/multi_zones.py — Motor para pruebas P3, P8, P9 con zonas esperadas.

Genera graficas con bandas sombreadas de zona de valores esperados
y curvas teoricas segun modelo droop piecewise.
Evalua en estatismos de 3%, 5% y 8%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.naming import artifact_filename, unique_path
from core.merge import (
    load_frequency_df,
    load_power_df,
    merge_time_series,
    simplify_for_plot,
    infer_drawstyle,
)
from core.droop import (
    derivar_p_op,
    generar_curva_teorica,
    construir_tabla_evaluacion,
    resumir_semaforo,
    PRUEBAS,
)
from core.plot import (
    DEFAULT_FREQ_COLOR,
    DEFAULT_POWER_COLOR,
    plot_p3_with_zones,
    plot_p8_with_zones,
    plot_p9_with_zones,
)


@dataclass
class ZoneCaseResult:
    caso: str
    estatismo_pct: float
    output_path: Path
    row_count: int
    p_op: float
    p_ref: float
    error_pct: float | None
    semaforo: str
    df: pd.DataFrame | None = None
    curva_teorica: pd.Series | None = None


@dataclass
class ZoneMultiResult:
    test_id: str
    cases: list[ZoneCaseResult] = field(default_factory=list)
    summary_xlsx: Path | None = None
    compare_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def successful(self) -> list[ZoneCaseResult]:
        return [c for c in self.cases if c.output_path.exists()]

    @property
    def failed(self) -> list[ZoneCaseResult]:
        return [c for c in self.cases if not c.output_path.exists()]


def _statismo_float(caso: str) -> float:
    """Convierte '3%' -> 0.03, '5%' -> 0.05, '8%' -> 0.08."""
    return float(caso.replace("%", "")) / 100.0


def _p_ref_from_data(df: pd.DataFrame, col_pot: str = "active_power") -> float:
    """Estima P_ref como el percentil 95 de potencia activa registrada."""
    return float(pd.to_numeric(df[col_pot], errors="coerce").quantile(0.95))


def _plot_function_for_test(test_id: str):
    """Devuelve la funcion de plot adecuada segun test_id."""
    if test_id == "P3Z":
        return plot_p3_with_zones
    if test_id == "P8Z":
        return plot_p8_with_zones
    if test_id == "P9Z":
        return plot_p9_with_zones
    raise ValueError(f"No hay funcion de plot con zonas para {test_id}")


def run_zones_multi(
    test_id: str,
    file_pairs: list[tuple[str, Path, Path]],
    output_dir: Path,
    freq_color: str = DEFAULT_FREQ_COLOR,
    power_color: str = DEFAULT_POWER_COLOR,
) -> ZoneMultiResult:
    """
    Ejecuta analisis de prueba multi-caso con zonas esperadas.

    Args:
        test_id: "P3Z", "P8Z" o "P9Z"
        file_pairs: [(caso, frec_path, gen_path), ...]
                    Ejemplo: [("3%", path_frec_3, path_gen_3), ...]
        output_dir: Directorio para graficas y Excel
        freq_color / power_color: Colores personalizables

    Returns:
        ZoneMultiResult con rutas, curvas teoricas y evaluacion.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result = ZoneMultiResult(test_id=test_id)
    summary_sheets: list[tuple[str, pd.DataFrame]] = []
    plot_fn = _plot_function_for_test(test_id)

    for caso, frec_path, gen_path in file_pairs:
        try:
            freq_df = load_frequency_df(frec_path)
            power_df = load_power_df(gen_path)
            df = merge_time_series(freq_df, power_df)
            df = simplify_for_plot(df)
            drawstyle = infer_drawstyle(df["frequency"])

            # Derivar P_op y P_ref
            info_p_op = derivar_p_op(df)
            if info_p_op is None:
                result.errors.append(f"[{caso}] No se pudo derivar P_op")
                continue

            p_op = info_p_op["p_op"]
            p_ref = _p_ref_from_data(df)
            S = _statismo_float(caso)

            # Generar curva teorica
            curva_teorica = generar_curva_teorica(df, S, p_op, p_ref)

            # Titulo
            safe_caso = caso.replace("%", "pct").replace("/", "_")
            titulo = _build_title(test_id, caso, S)

            # Grafica
            output_path = unique_path(
                output_dir
                / artifact_filename(
                    output_dir,
                    descriptor=f"caso_{safe_caso}_zona",
                    ext=".png",
                    test_id=test_id,
                    df=df,
                )
            )
            plot_fn(
                df=df,
                time_col="time",
                freq_col="frequency",
                power_col="active_power",
                curva_teorica=curva_teorica,
                output_path=output_path,
                title=titulo,
                power_unit="MW",
                freq_color=freq_color,
                power_color=power_color,
                drawstyle=drawstyle,
                estatismo=S,
                p_op=p_op,
                p_ref=p_ref,
            )

            # Tabla de evaluacion
            tabla = construir_tabla_evaluacion(df, S, p_op, p_ref)
            resumen = resumir_semaforo(tabla)
            tabla["caso"] = caso
            tabla["estatismo"] = f"{int(S*100)}%"

            sheet_name = f"{caso[:20]}_S{int(S*100)}"[:31]
            summary_sheets.append((sheet_name, tabla))

            # Error promedio
            clean_errors = tabla["error_pct"].dropna()
            error_prom = float(clean_errors.abs().mean()) if not clean_errors.empty else None

            # Semaforo dominante
            semaforo_dom = tabla["semaforo"].value_counts().index[0] if not tabla.empty else "indefinido"

            result.cases.append(ZoneCaseResult(
                caso=caso,
                estatismo_pct=S,
                output_path=output_path,
                row_count=len(df),
                p_op=round(p_op, 4),
                p_ref=round(p_ref, 4),
                error_pct=round(error_prom, 2) if error_prom else None,
                semaforo=semaforo_dom,
                df=df.copy(),
                curva_teorica=curva_teorica,
            ))

        except Exception as exc:
            result.errors.append(f"[{caso}] {exc}")

    # Exportar Excel resumen
    if summary_sheets:
        all_tabs = pd.concat(
            [sheet for _, sheet in summary_sheets], ignore_index=True
        )
        xlsx_path = unique_path(
            output_dir
            / artifact_filename(
                output_dir,
                descriptor="resumen_zonas",
                ext=".xlsx",
                test_id=test_id,
                df=all_tabs,
            )
        )
        _write_zones_xlsx(summary_sheets, xlsx_path)
        result.summary_xlsx = xlsx_path

    return result


def _build_title(test_id: str, caso: str, S: float) -> str:
    labels = {
        "P3Z": "Respuesta a Alta Frecuencia",
        "P8Z": "Respuesta a Baja Frecuencia",
        "P9Z": "Control Primario de Frecuencia",
    }
    return f"{test_id.replace('Z','')} - {labels.get(test_id, '')} - Estatismo {caso} (con zona esperada)"


def _write_zones_xlsx(sheets: list[tuple[str, pd.DataFrame]], path: Path) -> None:
    """Escribe multiple hojas en un Excel."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
