from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pandas as pd


_CONTAINER_DIRS = {"outputs", "graficas", "data", "DEPUR", "SALIDAS"}


def normalize_token(value: object, upper: bool = False) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")
    if not text:
        text = "archivo"
    return text.upper() if upper else text.lower()


def project_token(source: str | Path) -> str:
    path = Path(source)
    if path.suffix:
        path = path.parent
    while path.name in _CONTAINER_DIRS and path.parent != path:
        path = path.parent
    return normalize_token(path.name or "proyecto", upper=True)


def dataframe_date_label(df: pd.DataFrame | None, time_col: str = "time") -> str:
    if df is not None and time_col in df.columns:
        times = pd.to_datetime(df[time_col], errors="coerce").dropna()
        if not times.empty:
            start = times.min().strftime("%Y%m%d")
            end = times.max().strftime("%Y%m%d")
            return start if start == end else f"{start}_{end}"
    return dt.datetime.now().strftime("%Y%m%d")


def artifact_filename(
    source: str | Path,
    descriptor: str,
    ext: str,
    test_id: str | None = None,
    df: pd.DataFrame | None = None,
    time_col: str = "time",
    date_label: str | None = None,
) -> str:
    parts = [project_token(source)]
    if test_id:
        parts.append(normalize_token(test_id, upper=True))
    parts.append(normalize_token(descriptor))
    parts.append(date_label or dataframe_date_label(df, time_col=time_col))
    return f"{'_'.join(parts)}{ext}"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
