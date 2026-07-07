"""
core/depur.py — Recorte temporal de archivos de datos de día completo.

Migra data/DATA2.PY con API limpia sin rutas hardcodeadas,
lista para ser utilizada desde la interfaz Streamlit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd

from core.export import write_xlsx


XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SOURCE_SHEET = "High_resolution_50_ms"


@dataclass(frozen=True)
class CutJob:
    """Define un recorte: nombre de salida, timestamp de inicio y fin."""

    base_name: str
    start_text: str
    end_text: str


# ─── Parsing de timestamps ─────────────────────────────────────────────────────
_DATE_FORMATS = [
    "%m/%d/%Y %H:%M:%S:%f",
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M:%S",
]


def _parse_timestamp(value: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"No se pudo interpretar la fecha: {value}")


def _format_ts(ts: pd.Timestamp) -> str:
    ms = ts.microsecond // 1000
    return f"{ts.strftime('%m/%d/%Y %H:%M:%S')}:{ms:03d}"


def _normalize_ampm(value: str) -> str:
    text = str(value).strip()
    for old, new in [
        ("a. m.", "AM"),
        ("p. m.", "PM"),
        ("a.m.", "AM"),
        ("p.m.", "PM"),
        ("a m", "AM"),
        ("p m", "PM"),
    ]:
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    return text


def _parse_series(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).map(_normalize_ampm)
    parsed = pd.Series(pd.NaT, index=normalized.index, dtype="datetime64[ns]")
    for fmt in [
        "%d/%m/%Y %I:%M:%S.%f %p",
        "%m/%d/%Y %H:%M:%S:%f",
        "%m/%d/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S.%f",
    ]:
        mask = parsed.isna()
        if not mask.any():
            break
        parsed.loc[mask] = pd.to_datetime(
            normalized.loc[mask], errors="coerce", format=fmt
        )
    if parsed.isna().any():
        mask = parsed.isna()
        parsed.loc[mask] = pd.to_datetime(normalized.loc[mask], errors="coerce")
    if parsed.isna().all():
        raise ValueError("No se pudo interpretar la columna de tiempo.")
    return parsed


# ─── Carga del Excel fuente ───────────────────────────────────────────────────
def _col_index(cell_ref: str) -> int:
    letters = "".join(c for c in cell_ref if c.isalpha()).upper()
    idx = 0
    for letter in letters:
        idx = idx * 26 + (ord(letter) - ord("A") + 1)
    return idx - 1


def _read_cell(cell: ET.Element, shared: list[str]) -> object:
    t = cell.attrib.get("t")
    v = cell.find(f"{{{XML_NS}}}v")
    if t == "inlineStr":
        it = cell.find(f"{{{XML_NS}}}is/{{{XML_NS}}}t")
        return it.text if it is not None else None
    if v is None or v.text is None:
        return None
    if t == "s":
        return shared[int(v.text)]
    return v.text


def _read_shared(zf: ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(path))
    return [
        "".join(n.text or "" for n in item.iter(f"{{{XML_NS}}}t"))
        for item in root.findall(f"{{{XML_NS}}}si")
    ]


def _resolve_ws_path(zf: ZipFile, sheet_name: str) -> str:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        r.attrib["Id"]: r.attrib["Target"]
        for r in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    sheets = wb.find(f"{{{XML_NS}}}sheets")
    if sheets is None:
        raise ValueError("Sin hojas en el archivo.")
    for sheet in sheets.findall(f"{{{XML_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            rid = sheet.attrib.get(f"{{{REL_NS}}}id")
            if rid and rid in rel_map:
                return f"xl/{rel_map[rid].lstrip('/')}"
    raise ValueError(f"Hoja '{sheet_name}' no encontrada.")


def _load_source(path: Path) -> tuple[pd.DataFrame, str]:
    if path.suffix.lower() in {".csv", ".cvs"}:
        df = pd.read_csv(path, sep=None, engine="python", low_memory=False)
        if df.empty:
            raise ValueError(f"Sin datos en '{path.name}'.")
        df.columns = [str(c).strip() for c in df.columns]
        time_col = next(
            (c for c in df.columns if "date" in c.lower() and "time" in c.lower()),
            df.columns[0],
        )
        df["_parsed_time"] = _parse_series(df[time_col])
        df = (
            df.dropna(subset=["_parsed_time"])
            .sort_values("_parsed_time")
            .reset_index(drop=True)
        )
        return df, time_col

    with ZipFile(path) as zf:
        ws_path = _resolve_ws_path(zf, SOURCE_SHEET)
        shared = _read_shared(zf)
        ws = ET.fromstring(zf.read(ws_path))
        sheet_data = ws.find(f"{{{XML_NS}}}sheetData")
        if sheet_data is None:
            raise ValueError(f"Sin datos en '{path.name}'.")
        rows: list[dict[int, object]] = []
        max_col = -1
        for row in sheet_data.findall(f"{{{XML_NS}}}row"):
            rm: dict[int, object] = {}
            for cell in row.findall(f"{{{XML_NS}}}c"):
                c = _col_index(cell.attrib.get("r", ""))
                rm[c] = _read_cell(cell, shared)
                max_col = max(max_col, c)
            if rm:
                rows.append(rm)
    if not rows:
        raise ValueError(f"Sin filas en '{path.name}'.")
    headers = [
        str(rows[0].get(i, f"Column {i + 1}")).strip() for i in range(max_col + 1)
    ]
    records = [[row.get(i) for i in range(max_col + 1)] for row in rows[1:]]
    df = pd.DataFrame(records, columns=headers)
    df.columns = [str(c).strip() for c in df.columns]
    # Detectar columna de tiempo
    time_col = next(
        (c for c in df.columns if "date" in c.lower() and "time" in c.lower()),
        df.columns[0],
    )
    df["_parsed_time"] = _parse_series(df[time_col])
    df = (
        df.dropna(subset=["_parsed_time"])
        .sort_values("_parsed_time")
        .reset_index(drop=True)
    )
    return df, time_col


# ─── Selección de rango ───────────────────────────────────────────────────────
def _align_date(
    df: pd.DataFrame, start: datetime, end: datetime
) -> tuple[datetime, datetime, bool]:
    avail = df["_parsed_time"].dt.normalize().drop_duplicates().sort_values()
    if len(avail) != 1:
        return start, end, False
    avail_date = avail.iloc[0]
    if start.date() == avail_date.date():
        return start, end, False
    adj_start = start.replace(
        year=avail_date.year, month=avail_date.month, day=avail_date.day
    )
    adj_end = end.replace(
        year=avail_date.year, month=avail_date.month, day=avail_date.day
    )
    return adj_start, adj_end, True


def _select_range(
    df: pd.DataFrame,
    time_col: str,
    start: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    ts = df["_parsed_time"]
    start_matches = ts[ts <= start]
    end_matches = ts[ts <= end]
    if start_matches.empty:
        raise ValueError(f"Sin registro en o antes de: {start}")
    if end_matches.empty:
        raise ValueError(f"Sin registro en o antes de: {end}")
    s_idx = start_matches.index[-1]
    e_idx = end_matches.index[-1]
    if s_idx > e_idx:
        raise ValueError("Rango inválido: el inicio queda después del fin.")
    selected = df.loc[s_idx:e_idx].copy()
    applied_start = selected["_parsed_time"].iloc[0]
    applied_end = selected["_parsed_time"].iloc[-1]
    selected[time_col] = selected["_parsed_time"].map(_format_ts)
    selected = selected.drop(columns=["_parsed_time"])
    return selected.reset_index(drop=True), applied_start, applied_end


# ─── API pública ──────────────────────────────────────────────────────────────
def load_sources(poi_path: Path, gen_path: Path) -> dict[str, tuple[pd.DataFrame, str]]:
    """Carga los archivos fuente (POI y GEN) y los devuelve listos para recorte."""
    return {
        "POI": _load_source(poi_path),
        "GEN": _load_source(gen_path),
    }


def run_cut_job(
    job: CutJob,
    sources: dict[str, tuple[pd.DataFrame, str]],
    output_dir: Path,
) -> list[Path]:
    """Ejecuta un recorte temporal sobre todos los archivos fuente y guarda los resultados."""
    req_start = _parse_timestamp(job.start_text)
    req_end = _parse_timestamp(job.end_text)
    if req_start > req_end:
        raise ValueError(f"Rango inválido para '{job.base_name}': inicio > fin.")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for suffix, (df, time_col) in sources.items():
        eff_start, eff_end, adjusted = _align_date(df, req_start, req_end)
        selected, applied_start, applied_end = _select_range(
            df, time_col, eff_start, eff_end
        )
        sep = "" if job.base_name.endswith("_") else "_"
        out_path = output_dir / f"{job.base_name}{sep}{suffix}.xlsx"
        write_xlsx(selected, out_path, out_path.stem)
        outputs.append(out_path)

    return outputs
