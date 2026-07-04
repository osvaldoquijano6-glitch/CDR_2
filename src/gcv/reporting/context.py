"""ReportContext: todo lo que las plantillas de reporte necesitan, ya resuelto."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import plotly.graph_objects as go

from gcv.evaluation.result import TestResult
from gcv.models import Installation
from gcv.normalization.column_mapper import NormalizedDataset


@dataclass
class ReportContext:
    proyecto: str
    installation: Installation
    resultados: list[TestResult]
    datasets: list[NormalizedDataset] = field(default_factory=list)
    figuras: dict[str, list[go.Figure]] = field(default_factory=dict)  # test_id → figs
    responsable: str | None = None
    fecha: datetime = field(default_factory=datetime.now)
    objetivo: str = (
        "Verificar el cumplimiento de los requerimientos técnicos aplicables "
        "conforme al Código de Red y manuales regulatorios vigentes.")
    alcance: str | None = None
    metodologia: str = (
        "Carga y normalización de mediciones con bitácora de transformaciones; "
        "evaluación determinística contra criterios de la matriz normativa; "
        "toda comparación cita documento y numeral. Los criterios no validados "
        "documentalmente producen resultado NO EVALUABLE.")

    @property
    def resumen(self) -> dict[str, int]:
        counts = {"CUMPLE": 0, "NO_CUMPLE": 0, "NO_EVALUABLE": 0, "PENDIENTE_DOCUMENTAL": 0}
        for r in self.resultados:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        return counts

    @property
    def pendientes(self) -> list[TestResult]:
        return [r for r in self.resultados if r.status.value in
                ("NO_EVALUABLE", "PENDIENTE_DOCUMENTAL")]
