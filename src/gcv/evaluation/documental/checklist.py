"""Evaluador genérico de pruebas documentales (checklist con evidencia).

Cubre las verificaciones cuyo criterio es entrega/aceptación documental:
modelos de simulación, protecciones, control, intercambio de información,
corto circuito y plan de trabajo. El checklist exigido viene de la matriz
(`limites.checklist`: lista de ítems del numeral); el estado de cada ítem lo
declara el usuario en parámetros con su evidencia.

Parámetros de ejecución:
    checklist: {item: {"cumple": true/false/null, "evidencia": "oficio/estudio ..."}}

Reglas de dictamen:
    * todos los ítems exigidos con cumple=true y evidencia → CUMPLE
    * algún ítem cumple=false → NO_CUMPLE
    * ítems sin declarar o sin evidencia → PENDIENTE_DOCUMENTAL
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, TestResult, TestStatus
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset


class ChecklistDocumental(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        # prueba documental: no requiere series de tiempo ni fs
        issues: list[InputIssue] = []
        if not self.spec.limites.get("checklist"):
            issues.append(InputIssue("limites.checklist ausente en la matriz"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        exigidos = self.spec.limites.get("checklist", [])
        declarados = wd.params.get("checklist", {})
        filas = []
        for item in exigidos:
            d = declarados.get(item, {})
            filas.append({"item": item, "cumple": d.get("cumple"),
                          "evidencia": d.get("evidencia")})
        calc = Calculation(extra={"filas": filas})
        calc.tables.append(Evidence(tipo="tabla", titulo="Checklist documental",
                                    data={"filas": filas}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        checks = []
        for fila in calc.extra["filas"]:
            declarado = fila["cumple"]
            con_evidencia = bool(fila["evidencia"])
            cumple = bool(declarado and con_evidencia) if declarado is not None else None
            if declarado is True and not con_evidencia:
                cumple = None
            checks.append(CriterionCheck(
                nombre=fila["item"], comparacion="entrega documental",
                cumple=False if declarado is False else cumple,
                referencia=ref,
                detalle=fila["evidencia"] or ("declarado sin evidencia adjunta"
                                              if declarado else "sin declarar")))
        return checks

    def run(self, data: NormalizedDataset, params: dict | None = None) -> TestResult:
        result = super().run(data, params)
        # ítems sin declarar no vuelven la prueba NO_EVALUABLE sino PENDIENTE_DOCUMENTAL
        if result.status == TestStatus.NO_EVALUABLE and result.pass_fail_details:
            pendientes = [c for c in result.pass_fail_details if c.cumple is None]
            if pendientes and not any(c.cumple is False for c in result.pass_fail_details):
                result.status = TestStatus.PENDIENTE_DOCUMENTAL
                result.conclusion = (f"{self.spec.nombre}: pendiente de evidencia documental "
                                     f"({len(pendientes)} ítems) — {self.spec.cita()}.")
        elif (result.status == TestStatus.CUMPLE
              and any(c.cumple is None for c in result.pass_fail_details)):
            result.status = TestStatus.PENDIENTE_DOCUMENTAL
            result.conclusion = (f"{self.spec.nombre}: ítems restantes pendientes de "
                                 f"evidencia — {self.spec.cita()}.")
        return result


# Un registro por prueba documental; el checklist específico vive en la matriz.
for _tid in ("CE-D-01", "CE-F-06", "CC-03", "CC-05", "CC-06", "CC-07", "CC-09", "CC-10"):
    register(_tid)(type(f"Checklist_{_tid.replace('-', '_')}", (ChecklistDocumental,), {}))
