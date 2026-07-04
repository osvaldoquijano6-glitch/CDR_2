"""Exportación Excel: matriz de cumplimiento, criterios, mediciones y bitácora."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gcv.reporting.context import ReportContext

_STATUS_FMT = {
    "CUMPLE": {"bg_color": "#e6f4e6", "font_color": "#0a5c0a"},
    "NO_CUMPLE": {"bg_color": "#fbe9e9", "font_color": "#8f1f1f"},
    "NO_EVALUABLE": {"bg_color": "#fdf3dc", "font_color": "#7a5a00"},
    "PENDIENTE_DOCUMENTAL": {"bg_color": "#ececec", "font_color": "#444444"},
}


def _matriz_df(ctx: ReportContext) -> pd.DataFrame:
    rows = []
    for r in ctx.resultados:
        refs = "; ".join(f"{n.documento} {n.numeral or 's/numeral'}"
                         for n in r.normative_reference) or "—"
        rows.append({
            "ID": r.test_id, "Prueba": r.test_name, "Resultado": r.status.value,
            "Estado normativo": r.estado_normativo or "—",
            "Referencia": refs,
            "Criterios evaluados": sum(1 for c in r.pass_fail_details if c.cumple is not None),
            "Advertencias": len(r.warnings),
            "Conclusión": r.conclusion,
        })
    return pd.DataFrame(rows)


def _criterios_df(ctx: ReportContext) -> pd.DataFrame:
    rows = []
    for r in ctx.resultados:
        for c in r.pass_fail_details:
            rows.append({
                "ID": r.test_id, "Criterio": c.nombre,
                "Medido": c.valor_medido, "Límite": c.limite, "Unidad": c.unidad,
                "Comparación": c.comparacion,
                "Cumple": {True: "SÍ", False: "NO"}.get(c.cumple, "NO EVALUABLE"),
                "Numeral": (c.referencia.numeral if c.referencia else None),
                "Detalle": c.detalle,
            })
    return pd.DataFrame(rows)


def _mediciones_df(ctx: ReportContext) -> pd.DataFrame:
    rows = [{"ID": r.test_id, "Variable": m.nombre, "Valor": m.valor,
             "Unidad": m.unidad, "Detalle": m.detalle}
            for r in ctx.resultados for m in r.measured_values]
    return pd.DataFrame(rows)


def _bitacora_df(ctx: ReportContext) -> pd.DataFrame:
    rows = []
    for ds in ctx.datasets:
        for a in ds.log.acciones:
            rows.append({
                "Fuente": ds.source_path, "SHA256": (ds.source_sha256 or "")[:12],
                "Momento (UTC)": a.timestamp.replace(tzinfo=None), "Módulo": a.modulo,
                "Acción": a.accion, "Detalle": a.detalle,
                "Filas antes": a.filas_antes, "Filas después": a.filas_despues,
            })
    return pd.DataFrame(rows)


def export_excel(ctx: ReportContext, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = {
        "Matriz de cumplimiento": _matriz_df(ctx),
        "Criterios": _criterios_df(ctx),
        "Mediciones": _mediciones_df(ctx),
        "Bitacora": _bitacora_df(ctx),
    }
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        wb = writer.book
        header_fmt = wb.add_format({"bold": True, "bg_color": "#2a3f54",
                                    "font_color": "white", "border": 1})
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False, startrow=1, header=False)
            ws = writer.sheets[name]
            for col, col_name in enumerate(df.columns):
                ws.write(0, col, col_name, header_fmt)
                width = max(12, min(60, int(df[col_name].astype(str).str.len().max() or 12) + 2)) \
                    if not df.empty else 14
                ws.set_column(col, col, width)
            ws.freeze_panes(1, 0)
        # semáforo en la matriz
        matriz = sheets["Matriz de cumplimiento"]
        if not matriz.empty:
            ws = writer.sheets["Matriz de cumplimiento"]
            col = list(matriz.columns).index("Resultado")
            for status, style in _STATUS_FMT.items():
                fmt = wb.add_format({**style, "bold": True})
                for row, value in enumerate(matriz["Resultado"], start=1):
                    if value == status:
                        ws.write(row, col, value, fmt)
    return path
