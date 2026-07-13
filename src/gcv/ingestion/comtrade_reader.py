"""Lector COMTRADE (IEEE C37.111) sobre la librería `comtrade`.

A diferencia de Excel/CSV, el formato define nombre y unidad de cada canal en
el .cfg, por lo que el RawDataset sale con `header_resolved=True`: columnas
con nombre de canal, columna `timestamp` absoluta (si el .cfg trae fecha de
disparo) y unidades declaradas en `units`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from gcv.ingestion.base import FileFormat, RawDataset, file_sha256


def _resolve_pair(path: Path) -> tuple[Path, Path]:
    """Acepta la ruta del .cfg o del .dat y resuelve el par completo."""
    path = Path(path)
    stem = path.with_suffix("")
    candidates = {
        ".cfg": [stem.with_suffix(".cfg"), stem.with_suffix(".CFG")],
        ".dat": [stem.with_suffix(".dat"), stem.with_suffix(".DAT")],
    }
    resolved: dict[str, Path] = {}
    for ext, options in candidates.items():
        found = next((p for p in options if p.exists()), None)
        if found is None:
            raise FileNotFoundError(f"No se encontró el archivo {ext} para '{path.name}'.")
        resolved[ext] = found
    return resolved[".cfg"], resolved[".dat"]


def read_comtrade(path: Path) -> RawDataset:
    import comtrade

    cfg_path, dat_path = _resolve_pair(path)
    rec = comtrade.Comtrade()
    rec.load(str(cfg_path), str(dat_path))

    data: dict[str, object] = {}
    base: datetime | None = rec.start_timestamp
    seconds = pd.Series(rec.time, dtype="float64")
    data["t_rel_s"] = seconds  # tiempo relativo al inicio del registro
    if base is not None:
        data["timestamp"] = [base + timedelta(seconds=float(s)) for s in rec.time]

    units: dict[str, str] = {}
    for i, channel_id in enumerate(rec.analog_channel_ids):
        name = str(channel_id).strip() or f"analog_{i + 1}"
        data[name] = pd.Series(rec.analog[i], dtype="float64")
        units[name] = (rec.cfg.analog_channels[i].uu or "").strip()
    for i, channel_id in enumerate(rec.status_channel_ids):
        name = str(channel_id).strip() or f"status_{i + 1}"
        data[name] = pd.Series(rec.status[i], dtype="int64")

    grid = pd.DataFrame(data)
    return RawDataset(
        grid=grid,
        source_path=cfg_path,
        formato=FileFormat.COMTRADE,
        sha256=file_sha256(dat_path),
        header_resolved=True,
        units=units,
        metadata={
            "estacion": rec.station_name,
            "equipo": rec.rec_dev_id,
            "rev_year": rec.rev_year,
            "frecuencia_nominal_hz": rec.frequency,
            "muestras_totales": rec.total_samples,
            "inicio": str(rec.start_timestamp),
            "disparo": str(rec.trigger_timestamp),
            "cfg_sha256": file_sha256(cfg_path),
        },
    )
