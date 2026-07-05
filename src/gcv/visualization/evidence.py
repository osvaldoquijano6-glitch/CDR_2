"""Constructor de evidencia gráfica por prueba.

Consume TestResult + NormalizedDataset y produce figuras Plotly. No aplica
criterios: las vistas derivadas (curva droop teórica, serie ROCOF) se
reconstruyen con las mismas funciones puras de capa 4 usadas por el motor,
parametrizadas desde `result.parametros_ejecucion` y los valores medidos, de
modo que la gráfica es consistente con lo evaluado.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from gcv.evaluation.result import TestResult
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.derivatives import rocof_series
from gcv.signal_processing.droop import DroopParams, expected_power
from gcv.visualization import plots

_DROOP_ZONA = {"CE-F-03": "alta", "CE-F-04": "baja", "CE-F-05": "ambas"}


def _measured(result: TestResult, nombre: str) -> float | None:
    for m in result.measured_values:
        if m.nombre == nombre:
            return m.valor
    return None


def _freq_bands(result: TestResult) -> list[tuple]:
    bandas = (result.required_limits or {}).get("bandas") or []
    return [(b["f_min"], b["f_max"], f"{b['f_min']}–{b['f_max']} Hz")
            for b in bandas if "f_min" in b]


def build_figures(
    result: TestResult,
    ds: NormalizedDataset,
    estilo: str = "doble_eje",
) -> list[go.Figure]:
    """Figuras de evidencia para un resultado. Lista vacía si no hay vista definida.

    estilo: "doble_eje" (convención de reportes del proyecto: excitación
    escalonada eje izq. + P eje der.) o "apilado" (paneles con eje X común).
    """
    df = ds.df
    tid = result.test_id
    titulo = f"{tid} — {result.test_name}"
    dual = estilo == "doble_eje"

    if tid == "CE-F-01" and "frequency" in df.columns:
        bandas = _freq_bands(result)
        if dual and "active_power" in df.columns:
            return [plots.dual_axis_timeseries(
                df, ("frequency", "Frecuencia", "Hz"),
                [("active_power", "Potencia Activa", "medida")],
                titulo, bands=bandas)]
        panels = [{"series": [("frequency", "Frecuencia", "medida")],
                   "y_title": "Hz", "bands": bandas}]
        if "active_power" in df.columns:
            panels.append({"series": [("active_power", "Potencia activa", "medida")],
                           "y_title": "MW"})
        return [plots.stacked_timeseries(df, panels, titulo)]

    if tid == "CE-F-02" and "frequency" in df.columns:
        window_ms = (result.required_limits or {}).get(
            "ventana_rocof_ms", result.parametros_ejecucion.get("ventana_rocof_ms", 500))
        serie = rocof_series(df["timestamp"], df["frequency"], float(window_ms) / 1000.0)
        inmunidad = (result.required_limits or {}).get("rocof_inmunidad_hz_s")
        hlines = ([(inmunidad, f"inmunidad {inmunidad} Hz/s"),
                   (-inmunidad, "")] if inmunidad else [])
        panels = [
            {"series": [("frequency", "Frecuencia", "medida")], "y_title": "Hz"},
            {"series": [(serie, f"ROCOF (ventana {window_ms:g} ms)", "secundaria")],
             "y_title": "Hz/s", "hlines": hlines},
        ]
        if "active_power" in df.columns:
            panels.append({"series": [("active_power", "Potencia activa", "medida")],
                           "y_title": "MW"})
        return [plots.stacked_timeseries(df, panels, titulo)]

    if tid in _DROOP_ZONA and {"frequency", "active_power"} <= set(df.columns):
        figs: list[go.Figure] = []
        p_op = _measured(result, "p_op")
        params = result.parametros_ejecucion
        expected = None
        if p_op is not None and params.get("estatismo") and params.get("p_ref_mw"):
            lim = result.required_limits or {}
            dp = DroopParams(
                p_ref_mw=float(params["p_ref_mw"]), estatismo=float(params["estatismo"]),
                zona=_DROOP_ZONA[tid], f_nom_hz=float(params.get("f_nom_hz", 60.0)),
                umbral_hz=lim.get("umbral_hz", params.get("umbral_hz")),
                banda_muerta_hz=float(lim.get("banda_muerta_hz", 0.0) or 0.0),
            ) if (lim.get("umbral_hz") or params.get("umbral_hz")
                  or _DROOP_ZONA[tid] == "ambas") else None
            if dp is not None:
                expected = expected_power(df["frequency"], p_op, dp)
        if estilo == "doble_eje":
            respuestas = [("active_power", "P medida", "secundaria")]
            if expected is not None:
                respuestas.append((expected, "P esperada (droop)", "teorica"))
            figs.append(plots.dual_axis_timeseries(
                df, ("frequency", "Frecuencia", "Hz"), respuestas, titulo))
        else:
            p_series = [("active_power", "P medida", "medida")]
            if expected is not None:
                p_series.append((expected, "P esperada (droop)", "teorica"))
            figs.append(plots.stacked_timeseries(df, [
                {"series": [("frequency", "Frecuencia", "medida")], "y_title": "Hz"},
                {"series": p_series, "y_title": "MW"},
            ], titulo))
        if expected is not None:
            orden = df["frequency"].sort_values()
            figs.append(plots.scatter_xy(
                df["frequency"], df["active_power"],
                f"{tid} — Característica P(f) medida vs droop teórico",
                "Frecuencia [Hz]", "Potencia activa [MW]",
                curve=(orden, expected.loc[orden.index], "Droop teórico")))
        return figs

    if tid == "CE-V-01" and "voltage" in df.columns:
        v_base = result.parametros_ejecucion.get("v_base_v")
        serie = (pd.to_numeric(df["voltage"], errors="coerce") / float(v_base)
                 if v_base else df["voltage"])
        bandas = [(b["v_min_pu"], b["v_max_pu"], f"{b['v_min_pu']}–{b['v_max_pu']} pu")
                  for b in (result.required_limits or {}).get("bandas", [])]
        return [plots.stacked_timeseries(df, [
            {"series": [(serie, "Tensión POI", "medida")],
             "y_title": "pu" if v_base else "V", "bands": bandas}], titulo)]

    if tid == "CE-P-01" and "active_power" in df.columns:
        declarada = result.parametros_ejecucion.get("capacidad_declarada_mw")
        hlines = [(float(declarada), f"declarada {declarada} MW")] if declarada else []
        return [plots.stacked_timeseries(df, [
            {"series": [("active_power", "Potencia activa neta", "medida")],
             "y_title": "MW", "hlines": hlines}], titulo)]

    if tid == "CC-04":
        from gcv.evaluation.load_center.factor_potencia import _fp_series
        fp = _fp_series(df)
        if fp is None:
            return []
        fp_min = (result.required_limits or {}).get("fp_min")
        return [plots.stacked_timeseries(df, [
            {"series": [(fp, "Factor de potencia", "medida")], "y_title": "FP",
             "hlines": [(float(fp_min), f"FP mín {fp_min}")] if fp_min else []}], titulo)]

    if tid in ("CE-Q-04", "CE-Q-05"):
        for tabla in result.tables:
            pcts = (tabla.data or {}).get("percentiles_pct")
            if pcts:
                lim_tabla = {str(k): float(v) for k, v in
                             ((result.required_limits or {}).get("armonicos") or {}).items()}
                return [plots.limits_bar(
                    {f"h{k}": v for k, v in pcts.items()},
                    {f"h{k}": v for k, v in lim_tabla.items()},
                    titulo, "% de la fundamental")]
        señal = "thd_voltage" if tid == "CE-Q-04" else "tdd"
        if señal in df.columns:
            lim_key = "thd_max_pct" if tid == "CE-Q-04" else "tdd_max_pct"
            limite = (result.required_limits or {}).get(lim_key)
            return [plots.stacked_timeseries(df, [
                {"series": [(señal, señal.upper(), "medida")], "y_title": "%",
                 "hlines": [(float(limite), f"límite {limite}%")] if limite else []}], titulo)]
        return []

    if tid == "CE-Q-02":
        panels = []
        for señal in ("pst", "plt"):
            if señal in df.columns:
                limite = (result.required_limits or {}).get(f"{señal}_max")
                panels.append({"series": [(señal, señal.upper(), "medida")],
                               "y_title": señal.upper(),
                               "hlines": [(float(limite), f"límite {limite}")] if limite else []})
        return [plots.stacked_timeseries(df, panels, titulo)] if panels else []

    if tid in ("CE-Q-01", "CE-Q-03"):
        cols = [c for c in ("unbalance", "voltage_a", "voltage_b", "voltage_c", "voltage")
                if c in df.columns]
        if not cols:
            return []
        roles = ["medida", "secundaria", "teorica"]  # 3 slots categóricos para fases
        series = [(c, c, roles[min(i, 2)]) for i, c in enumerate(cols[:3])]
        return [plots.stacked_timeseries(df, [
            {"series": series, "y_title": "%" if cols[0] == "unbalance" else "V"}], titulo)]

    return []
