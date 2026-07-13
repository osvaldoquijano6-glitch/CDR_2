"""Bitácora de limpieza y transformación (CleaningLog).

Cada transformación aplicada a los datos —coerción numérica, deduplicado,
reordenamiento, conversión de unidades, corrección manual— queda registrada
con parámetros y conteo de filas. Es la pieza que permite rastrear cualquier
número del informe hasta el dato crudo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class CleaningAction(BaseModel):
    timestamp: datetime
    modulo: str  # módulo que aplicó la acción, p. ej. "normalization.cleaning"
    accion: str  # verbo corto: "coercion_numerica", "dedup_timestamps", ...
    detalle: str  # descripción legible
    filas_antes: int | None = None
    filas_despues: int | None = None
    parametros: dict = Field(default_factory=dict)


class CleaningLog(BaseModel):
    """Bitácora ordenada de acciones sobre un dataset."""

    fuente: str | None = None  # ruta o identificador del DataSource
    acciones: list[CleaningAction] = Field(default_factory=list)

    def add(
        self,
        modulo: str,
        accion: str,
        detalle: str,
        filas_antes: int | None = None,
        filas_despues: int | None = None,
        **parametros,
    ) -> CleaningAction:
        entry = CleaningAction(
            timestamp=datetime.now(timezone.utc),
            modulo=modulo,
            accion=accion,
            detalle=detalle,
            filas_antes=filas_antes,
            filas_despues=filas_despues,
            parametros=parametros,
        )
        self.acciones.append(entry)
        return entry

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent, ensure_ascii=False)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path
