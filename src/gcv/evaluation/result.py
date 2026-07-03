"""TestResult: resultado trazable de una prueba.

Cada resultado enlaza: valores medidos, límites citados con numeral,
comparaciones individuales, evidencia y la cadena de trazabilidad hasta el
archivo fuente (sha256) y la bitácora de limpieza.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from gcv.models import NormRef


class TestStatus(str, enum.Enum):
    CUMPLE = "CUMPLE"
    NO_CUMPLE = "NO_CUMPLE"
    NO_EVALUABLE = "NO_EVALUABLE"
    PENDIENTE_DOCUMENTAL = "PENDIENTE_DOCUMENTAL"


class MeasuredValue(BaseModel):
    nombre: str
    valor: float | None = None
    unidad: str | None = None
    detalle: str | None = None


class CriterionCheck(BaseModel):
    """Comparación individual medido-vs-límite; un resultado tiene una o varias."""

    nombre: str
    valor_medido: float | None = None
    limite: float | None = None
    unidad: str | None = None
    comparacion: str | None = None  # p. ej. "<=", ">=", "dentro de banda"
    cumple: bool | None = None  # None = no evaluable
    referencia: NormRef | None = None
    detalle: str | None = None


class Evidence(BaseModel):
    tipo: str  # "grafica" | "tabla" | "archivo"
    titulo: str
    path: str | None = None  # artefacto en disco
    data: dict | None = None  # tabla embebida (registros)


class TestResult(BaseModel):
    test_id: str
    test_name: str
    status: TestStatus
    ejecutado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    measured_values: list[MeasuredValue] = Field(default_factory=list)
    required_limits: dict[str, object] = Field(default_factory=dict)
    pass_fail_details: list[CriterionCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    normative_reference: list[NormRef] = Field(default_factory=list)
    plots: list[Evidence] = Field(default_factory=list)
    tables: list[Evidence] = Field(default_factory=list)
    conclusion: str = ""
    # Trazabilidad
    fuentes_sha256: list[str] = Field(default_factory=list)
    parametros_ejecucion: dict = Field(default_factory=dict)
    estado_normativo: str | None = None

    def add_warning(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)
