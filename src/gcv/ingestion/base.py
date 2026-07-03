"""Capa de lectura: contrato común y despachador por formato.

Los lectores NO interpretan señales ni encabezados desplazados: entregan una
rejilla cruda (`RawDataset.grid`, columnas posicionales 0..n) más metadatos.
La detección de encabezado y el mapeo de columnas ocurren en `normalization`.
Excepción: COMTRADE entrega canales ya resueltos (`header_resolved=True`)
porque el formato define nombre y unidad de cada canal.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


class FileFormat(str, enum.Enum):
    XLSX = "XLSX"
    XLSM = "XLSM"
    CSV = "CSV"
    COMTRADE = "COMTRADE"


@dataclass
class RawDataset:
    """Resultado de la lectura de un archivo, previo a normalización."""

    grid: pd.DataFrame  # datos crudos; columnas posicionales salvo header_resolved
    source_path: Path
    formato: FileFormat
    sha256: str
    hoja: str | None = None  # hoja Excel usada
    header_resolved: bool = False  # True si `grid` ya tiene encabezados reales
    units: dict[str, str] = field(default_factory=dict)  # unidad por columna (COMTRADE)
    metadata: dict = field(default_factory=dict)


def file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def read_file(path: Path, sheet: str | None = None) -> RawDataset:
    """Despacha al lector adecuado según la extensión.

    Para COMTRADE se acepta la ruta del .cfg (el .dat se resuelve junto a él).
    """
    from gcv.ingestion.comtrade_reader import read_comtrade
    from gcv.ingestion.csv_reader import read_csv
    from gcv.ingestion.excel_reader import read_excel

    path = Path(path)
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm"}:
        return read_excel(path, sheet=sheet)
    if ext == ".csv":
        return read_csv(path)
    if ext in {".cfg", ".dat"}:
        return read_comtrade(path)
    raise ValueError(f"Formato no soportado: '{ext}' ({path.name})")
