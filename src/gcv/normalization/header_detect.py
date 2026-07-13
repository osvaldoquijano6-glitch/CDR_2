"""Detección automática de la fila de encabezado en rejillas crudas.

Los exportes de analizadores traen preámbulos (equipo, campaña, ajustes) antes
de la tabla. Se puntúa cada fila candidata: una fila de encabezado es
mayormente texto no numérico, sin celdas repetidas, y las filas siguientes son
mayormente numéricas/fecha.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class HeaderDetection:
    row_index: int  # índice de la fila de encabezado dentro de la rejilla
    score: float  # 0..1; <0.5 debe pedirse confirmación al usuario
    headers: list[str]


def _is_numeric_like(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip().replace(",", ".")
    try:
        float(text)
        return True
    except ValueError:
        return pd.notna(pd.to_datetime(text, errors="coerce"))


def _row_score(grid: pd.DataFrame, idx: int, lookahead: int = 5) -> float:
    row = grid.iloc[idx]
    cells = [c for c in row if c is not None and str(c).strip() not in ("", "nan")]
    if len(cells) < 2:
        return 0.0
    filled = len(cells) / len(row)
    textual = sum(not _is_numeric_like(c) for c in cells) / len(cells)
    unique = len({str(c).strip().lower() for c in cells}) / len(cells)

    below = grid.iloc[idx + 1 : idx + 1 + lookahead]
    if below.empty:
        data_like = 0.0
    else:
        flat = [c for _, r in below.iterrows() for c in r if c is not None and str(c).strip() != ""]
        data_like = (sum(_is_numeric_like(c) for c in flat) / len(flat)) if flat else 0.0

    return 0.25 * filled + 0.30 * textual + 0.15 * unique + 0.30 * data_like


def detect_header(grid: pd.DataFrame, max_scan: int = 50) -> HeaderDetection:
    """Encuentra la fila de encabezado más plausible en las primeras `max_scan` filas."""
    if grid.empty:
        raise ValueError("Rejilla vacía: no hay encabezado que detectar.")
    n = min(max_scan, len(grid))
    scores = [(idx, _row_score(grid, idx)) for idx in range(n)]
    best_idx, best_score = max(scores, key=lambda item: item[1])
    headers = [
        str(v).strip() if v is not None and str(v).strip() not in ("", "nan") else f"col_{i}"
        for i, v in enumerate(grid.iloc[best_idx])
    ]
    return HeaderDetection(row_index=best_idx, score=round(best_score, 3), headers=headers)


def apply_header(grid: pd.DataFrame, detection: HeaderDetection) -> pd.DataFrame:
    """Devuelve la tabla de datos con los encabezados detectados aplicados."""
    df = grid.iloc[detection.row_index + 1 :].copy()
    df.columns = detection.headers
    return df.reset_index(drop=True)
