"""TestSpec: representación tipada de una fila de la matriz normativa.

La matriz (normative/matriz_pruebas.yaml) es la única fuente de criterios.
El código nunca declara límites propios: si el estado normativo no es
VALIDADO, el motor no emite CUMPLE/NO_CUMPLE.
"""

from __future__ import annotations

import enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from gcv.models import InstallationKind


class EstadoNormativo(str, enum.Enum):
    VALIDADO = "VALIDADO"
    HEREDADO_PROTOCOLO_SIN_CITA = "HEREDADO_PROTOCOLO_SIN_CITA"
    PENDIENTE_VALIDACION_NORMATIVA = "PENDIENTE_VALIDACION_NORMATIVA"


class TestSpec(BaseModel):
    """Fila de la matriz normativa maestra."""

    model_config = ConfigDict(extra="allow")  # campos futuros de la matriz no rompen carga

    id: str
    nombre: str
    aplica_a: InstallationKind
    legacy_id: str | None = None
    categorias: list[str] = Field(default_factory=list)  # vacío = aplicabilidad pendiente
    tecnologia: str | None = None  # SINCRONA | ASINCRONA | AMBAS
    manual_referencia: str | None = None
    numeral: str | None = None
    fuente_documental: str | None = None
    variables_requeridas: list[str] = Field(default_factory=list)
    unidad_esperada: dict[str, str] = Field(default_factory=dict)
    fs_minima_sugerida_hz: float | None = None
    duracion_minima: str | None = None
    criterio_aceptacion: str | None = None
    formula_algoritmo: str | None = None
    parametros_heredados: dict = Field(default_factory=dict)
    evidencia_requerida: list[str] = Field(default_factory=list)
    tipo_salida: list[str] = Field(default_factory=list)
    estado_normativo: EstadoNormativo = EstadoNormativo.PENDIENTE_VALIDACION_NORMATIVA
    dato_requerido: str | None = None
    observaciones: str | None = None
    # Límites cuantitativos validados (se llenan al capturar el numeral;
    # estructura libre por prueba, p. ej. bandas de frecuencia, envolvente P-Q).
    limites: dict = Field(default_factory=dict)

    @property
    def es_validado(self) -> bool:
        return self.estado_normativo == EstadoNormativo.VALIDADO

    def cita(self) -> str:
        doc = self.manual_referencia or "documento no asignado"
        num = self.numeral or "numeral pendiente"
        return f"{doc}, {num}"


def load_matrix(path: Path) -> dict[str, TestSpec]:
    """Carga la matriz normativa YAML → {test_id: TestSpec}."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    specs: dict[str, TestSpec] = {}
    for row in data.get("pruebas", []):
        # 'variables_requeridas' en la matriz usa nombres canónicos + entradas
        # documentales (checklist_*); TestSpec no las distingue: eso lo hace
        # cada implementación en validate_inputs.
        spec = TestSpec.model_validate(row)
        if spec.id in specs:
            raise ValueError(f"ID de prueba duplicado en la matriz: {spec.id}")
        specs[spec.id] = spec
    if not specs:
        raise ValueError(f"Matriz sin pruebas: {path}")
    return specs
