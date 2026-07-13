"""
core/export.py — Escritura de archivos Excel sin dependencia de openpyxl.

Consolida build_worksheet_xml, write_xlsx y write_multi_sheet_xlsx
que estaban duplicados en data/DATA2.PY, graph_utils.py y P3_DROP.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

DROOP = 0.08
FREQ_THRESHOLD_HIGH = 60.2
FREQ_HZ_DELTA = 1.0


def compute_expected_power_with_droop(
    freq: float,
    p_transition: float,
    p_simulated: float,
    droop: float = DROOP,
    freq_threshold: float = FREQ_THRESHOLD_HIGH,
    freq_delta: float = FREQ_HZ_DELTA,
) -> float:
    """Calcula potencia esperada usando la fórmula de estatismo.

    P = -(P_simulada / droop) × (f - 60.2) / 60 + P_transición
    """
    if freq < freq_threshold:
        return round(p_transition, 3)
    delta_f = freq - freq_threshold
    p_expected = -(p_simulated / droop) * (delta_f / freq_delta) + p_transition
    return round(max(0.0, p_expected), 3)


def classify_zone(
    freq: float,
    freq_threshold: float = FREQ_THRESHOLD_HIGH,
) -> str:
    """Clasifica la zona según el umbral de frecuencia.
    Cada escalón de frecuencia >= 60.2 Hz se considera una zona de estatismo separada."""
    if freq < freq_threshold - 0.01:
        return "Nominal"
    if freq < freq_threshold + 0.01:
        return "Transición"
    return "Estatismo"


# ─── Utilidades de celdas ─────────────────────────────────────────────────────
def _excel_col_name(index: int) -> str:
    name = ""
    current = index
    while current:
        current, rem = divmod(current - 1, 26)
        name = chr(65 + rem) + name
    return name


def _inline_string_cell(row: int, col: int, value: str) -> str:
    text = escape(value)
    preserve = ' xml:space="preserve"' if value != value.strip() else ""
    return (
        f'<c r="{_excel_col_name(col)}{row}" t="inlineStr">'
        f"<is><t{preserve}>{text}</t></is>"
        "</c>"
    )


def _numeric_cell(row: int, col: int, value: float) -> str:
    return f'<c r="{_excel_col_name(col)}{row}"><v>{value}</v></c>'


def build_worksheet_xml(df: pd.DataFrame) -> str:
    """Genera el XML de una hoja de cálculo a partir de un DataFrame."""
    rows_xml: list[str] = []
    # Cabecera
    header_cells = [_inline_string_cell(1, c, str(col)) for c, col in enumerate(df.columns, 1)]
    rows_xml.append(f'<row r="1">{"".join(header_cells)}</row>')
    # Filas de datos
    for row_num, (_, row) in enumerate(df.iterrows(), 2):
        cells = []
        for col_idx, val in enumerate(row, 1):
            if pd.isna(val):
                continue
            if pd.api.types.is_number(val):
                cells.append(_numeric_cell(row_num, col_idx, float(val)))
            else:
                cells.append(_inline_string_cell(row_num, col_idx, str(val)))
        rows_xml.append(f'<row r="{row_num}">{"".join(cells)}</row>')

    last_col = _excel_col_name(len(df.columns))
    last_row = len(df) + 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{last_col}{last_row}"/>'
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<sheetData>{''.join(rows_xml)}</sheetData>"
        "</worksheet>"
    )


def _base_xml_parts(now_utc: str) -> dict[str, str]:
    """Genera las partes XML comunes a cualquier workbook."""
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>Pruebas_Centrales_v3</dc:creator>"
        "<cp:lastModifiedBy>Pruebas_Centrales_v3</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now_utc}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now_utc}</dcterms:modified>'
        "</cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Application>Pruebas_Centrales_v3</Application>"
        "</Properties>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    return {"styles": styles, "core": core, "app": app, "root_rels": root_rels}


# ─── Escritura de archivos ─────────────────────────────────────────────────────
def write_xlsx(df: pd.DataFrame, output_path: Path, sheet_name: str = "Datos") -> Path:
    """Escribe un DataFrame en un archivo .xlsx con una sola hoja."""
    return write_multi_sheet_xlsx([(sheet_name, df)], output_path)


def write_multi_sheet_xlsx(sheets: list[tuple[str, pd.DataFrame]], output_path: Path) -> Path:
    """Escribe múltiples DataFrames en un archivo .xlsx, uno por hoja."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = _base_xml_parts(now_utc)

    sheet_xml_list: list[str] = []
    rel_xml_list: list[str] = []
    override_list: list[str] = []
    payloads: list[tuple[str, str]] = []

    for i, (name, df) in enumerate(sheets, 1):
        ename = escape(name)
        sheet_xml_list.append(f'<sheet name="{ename}" sheetId="{i}" r:id="rId{i}"/>')
        rel_xml_list.append(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
        )
        override_list.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        payloads.append((f"xl/worksheets/sheet{i}.xml", build_worksheet_xml(df)))

    styles_id = len(sheets) + 1
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(sheet_xml_list)}</sheets>"
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_xml_list)}"
        f'<Relationship Id="rId{styles_id}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{''.join(override_list)}"
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", base["root_rels"])
        zf.writestr("docProps/core.xml", base["core"])
        zf.writestr("docProps/app.xml", base["app"])
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", base["styles"])
        for ws_path, ws_xml in payloads:
            zf.writestr(ws_path, ws_xml)

    return output_path


# ─── Resumen de estados de frecuencia ─────────────────────────────────────────
def build_frequency_state_summary(
    df: pd.DataFrame,
    time_col: str,
    freq_col: str,
    power_col: str,
    power_unit: str,
    p_simulated: float | None = None,
    p_transition: float | None = None,
    trends: list[tuple[float, float]] | None = None,
    group_by_zone: bool = True,
) -> pd.DataFrame:
    """Agrupa el DataFrame por zonas de frecuencia y calcula medianas.

    Si group_by_zone=True, agrupa por zonas (Nominal/Transición/Estatismo).
    Si se proporcionan p_simulated y p_transition, calcula también:
    - Zona: clasificación nominal/estatismo según umbral (60.2 Hz)
    - Potencia esperada: calculada con fórmula de estatismo
    """
    df_copy = df.copy()

    if group_by_zone and (p_simulated is not None or trends):
        df_copy["zona"] = df_copy[freq_col].apply(classify_zone)
        rounded = df_copy[freq_col].round(3)
        df_copy["freq_step"] = rounded.ne(rounded.shift()).cumsum()
        groups = df_copy["zona"] + "_" + df_copy["freq_step"].astype(str)
    else:
        rounded = df_copy[freq_col].round(3)
        groups = rounded.ne(rounded.shift()).cumsum()

    summary = (
        df_copy.groupby(groups, sort=True)
        .agg(
            Inicio=(time_col, "first"),
            Termino=(time_col, "last"),
            Frecuencia=(freq_col, "median"),
            Potencia=(power_col, "median"),
        )
        .reset_index(drop=True)
    )

    result = pd.DataFrame({
        "Hora de inicio": summary["Inicio"].dt.strftime("%H:%M:%S.%f").str[:-3],
        "Hora de termino": summary["Termino"].dt.strftime("%H:%M:%S.%f").str[:-3],
        "Frecuencia [Hz]": summary["Frecuencia"].map(lambda v: round(float(v), 3)),
        f"Potencia [{power_unit}]": summary["Potencia"].map(lambda v: round(float(v), 3)),
    })

    if p_simulated is not None and p_transition is not None:
        result["Zona"] = summary["Frecuencia"].apply(
            lambda f: classify_zone(float(f))
        )
        result["Potencia esperada [MW]"] = summary["Frecuencia"].apply(
            lambda f: compute_expected_power_with_droop(
                float(f), p_transition, p_simulated
            )
        )
    elif trends:
        freq_to_power = {round(float(f), 3): float(p) for f, p in trends}
        result["Zona"] = summary["Frecuencia"].apply(
            lambda f: classify_zone(float(f))
        )
        result["Potencia esperada [MW]"] = summary["Frecuencia"].map(
            lambda v: freq_to_power.get(round(float(v), 3), float("nan"))
        )
    else:
        result["Zona"] = summary["Frecuencia"].apply(
            lambda f: classify_zone(float(f))
        )

    result = result.sort_values("Hora de inicio").reset_index(drop=True)

    return result
