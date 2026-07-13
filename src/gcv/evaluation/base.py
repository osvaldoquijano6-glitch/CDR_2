"""BaseTest: contrato del motor de reglas determinístico.

Ciclo de ejecución (método plantilla `run`):

    validate_inputs → preprocess → calculate → evaluate → generate_outputs

Garantías del motor, independientes de cada implementación:
  * Sin criterio normativo VALIDADO no hay veredicto: el resultado se degrada
    a NO_EVALUABLE aunque el cálculo se haya realizado (los valores medidos se
    reportan de todos modos como información).
  * Insumos insuficientes (señales faltantes, fs baja, dataset vacío) →
    NO_EVALUABLE con la causa explícita.
  * Todo resultado lleva la cita normativa y los sha256 de las fuentes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue, TestResult, TestStatus
from gcv.evaluation.spec import TestSpec
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset


@dataclass
class InputIssue:
    """Problema de insumos; `blocking=True` impide calcular."""

    mensaje: str
    blocking: bool = True


@dataclass
class WorkingData:
    """Datos preparados para el cálculo (ventanas aplicadas, señales elegidas)."""

    dataset: NormalizedDataset
    params: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Calculation:
    """Salida de calculate(): solo números y evidencia, sin juicio normativo."""

    measured: list[MeasuredValue] = field(default_factory=list)
    plots: list[Evidence] = field(default_factory=list)
    tables: list[Evidence] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseTest(ABC):
    """Clase base de toda prueba. Las subclases NO deciden el estado final:
    devuelven checks y el motor deriva el veredicto."""

    def __init__(self, spec: TestSpec):
        self.spec = spec

    # ─── Puntos de extensión ─────────────────────────────────────────────
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        """Validación mínima común; las subclases pueden extender (super())."""
        issues: list[InputIssue] = []
        if data.df.empty:
            issues.append(InputIssue("Dataset vacío"))
            return issues
        señales = [v for v in self.spec.variables_requeridas
                   if v != "timestamp" and not v.startswith("checklist")]
        faltantes = data.has_signals(señales)
        if faltantes:
            issues.append(InputIssue(f"Señales requeridas ausentes: {faltantes}"))
        fs_min = self.spec.fs_minima_sugerida_hz
        fs = data.quality.fs_detectada_hz
        if fs_min and fs and fs < fs_min:
            issues.append(InputIssue(
                f"Frecuencia de muestreo insuficiente: {fs:.4g} Hz < {fs_min:.4g} Hz requerida"))
        return issues

    def preprocess(self, data: NormalizedDataset, params: dict) -> WorkingData:
        return WorkingData(dataset=data, params=params)

    @abstractmethod
    def calculate(self, wd: WorkingData) -> Calculation:
        """Cálculo eléctrico puro. Sin comparación contra límites."""

    @abstractmethod
    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        """Comparación contra los límites de spec.limites. Cada check cita numeral."""

    def build_conclusion(self, result: TestResult) -> str:
        """Conclusión técnica generada del resultado (sobreescribible)."""
        cita = self.spec.cita()
        if result.status == TestStatus.CUMPLE:
            return (f"{self.spec.nombre}: todos los criterios evaluados se satisfacen "
                    f"conforme a {cita}.")
        if result.status == TestStatus.NO_CUMPLE:
            fallidos = [c.nombre for c in result.pass_fail_details if c.cumple is False]
            return (f"{self.spec.nombre}: incumplimiento en {', '.join(fallidos)} "
                    f"conforme a {cita}.")
        if result.status == TestStatus.PENDIENTE_DOCUMENTAL:
            return f"{self.spec.nombre}: pendiente de evidencia documental ({cita})."
        causas = "; ".join(result.warnings) or "insumos o criterio insuficientes"
        return f"{self.spec.nombre}: no evaluable — {causas}."

    # ─── Método plantilla ────────────────────────────────────────────────
    def run(self, data: NormalizedDataset, params: dict | None = None) -> TestResult:
        params = params or {}
        # límites diferenciados por tipo de central: se resuelven una vez y el
        # resto del ciclo lee spec.limites ya efectivos
        if "por_tipo" in self.spec.limites:
            self.spec = self.spec.model_copy(
                update={"limites": self.spec.limites_efectivos(params.get("tipo_ce"))})
            if not params.get("tipo_ce"):
                pass  # sin tipo declarado: solo llaves base; los checks faltantes lo reportan
        result = TestResult(
            test_id=self.spec.id,
            test_name=self.spec.nombre,
            status=TestStatus.NO_EVALUABLE,
            estado_normativo=self.spec.estado_normativo.value,
            parametros_ejecucion=params,
            fuentes_sha256=[s for s in [data.source_sha256] if s],
        )
        if self.spec.manual_referencia:
            result.normative_reference.append(
                NormRef(documento=self.spec.manual_referencia,
                        numeral=self.spec.numeral,
                        version=self.spec.fuente_documental))

        issues = self.validate_inputs(data, params)
        for issue in issues:
            result.add_warning(issue.mensaje)
        if any(i.blocking for i in issues):
            result.conclusion = self.build_conclusion(result)
            return result

        wd = self.preprocess(data, params)
        calc = self.calculate(wd)
        result.measured_values = calc.measured
        result.plots, result.tables = calc.plots, calc.tables
        result.required_limits = dict(self.spec.limites)

        if not self.spec.es_validado:
            result.add_warning(
                "Criterio normativo no validado "
                f"({self.spec.estado_normativo.value}): se reportan mediciones sin veredicto. "
                + (f"Dato requerido: {self.spec.dato_requerido}" if self.spec.dato_requerido else ""))
            result.conclusion = self.build_conclusion(result)
            return result

        checks = self.evaluate(calc, wd)
        result.pass_fail_details = checks
        evaluables = [c for c in checks if c.cumple is not None]
        if not evaluables:
            result.add_warning("Ningún criterio pudo evaluarse con los datos disponibles")
            result.status = TestStatus.NO_EVALUABLE
        elif all(c.cumple for c in evaluables):
            result.status = TestStatus.CUMPLE
        else:
            result.status = TestStatus.NO_CUMPLE
        if len(evaluables) < len(checks):
            result.add_warning(
                f"{len(checks) - len(evaluables)} criterios no evaluables se excluyeron del veredicto")
        result.conclusion = self.build_conclusion(result)
        return result
