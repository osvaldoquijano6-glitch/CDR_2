"""Lector de CSV exportados de analizadores, SCADA, registradores y PMU.

Detecta separador y codificación; entrega la rejilla cruda sin asumir fila de
encabezado (los exportes de analizadores y registradores suelen traer preámbulos).
Los valores se conservan como texto: la coerción numérica ocurre en
`normalization.cleaning` y queda registrada en la bitácora.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from gcv.ingestion.base import FileFormat, RawDataset, file_sha256

_ENCODINGS = ("utf-8-sig", "latin-1")
_DELIMITERS = ";,\t|"


def detect_encoding(path: Path) -> str:
    for enc in _ENCODINGS:
        try:
            with path.open("r", encoding=enc) as fh:
                fh.read(8192)
            return enc
        except UnicodeDecodeError:
            continue
    return _ENCODINGS[-1]


def detect_separator(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in _DELIMITERS}
        best = max(counts, key=counts.get)  # type: ignore[arg-type]
        return best if counts[best] > 0 else ","


def read_csv(path: Path) -> RawDataset:
    path = Path(path)
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as fh:
        sample = fh.read(8192)
    sep = detect_separator(sample)

    # csv.reader en lugar de pd.read_csv: los preámbulos de analizadores tienen
    # menos campos que la tabla y romperían el parser con ancho fijo.
    with path.open("r", encoding=encoding, newline="") as fh:
        rows = [row for row in csv.reader(fh, delimiter=sep)]
    if not rows:
        raise ValueError(f"Archivo CSV vacío: {path.name}")
    width = max(len(r) for r in rows)
    padded = [r + [None] * (width - len(r)) for r in rows]
    grid = pd.DataFrame(padded, dtype=object).replace({"": None})
    return RawDataset(
        grid=grid,
        source_path=path,
        formato=FileFormat.CSV,
        sha256=file_sha256(path),
        metadata={"separador": sep, "encoding": encoding},
    )
