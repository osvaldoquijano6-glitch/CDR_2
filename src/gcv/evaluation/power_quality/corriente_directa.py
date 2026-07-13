"""CE-Q-06 — Inyección de corriente directa (7.5 Manual INTE / nota 2.8 CONE).

"En ningún caso se permite inyección de CD en el Punto de Interconexión".
Operativamente: la componente de CD medida debe quedar bajo el umbral de
detección del instrumento, declarado por el usuario.

Parámetros: umbral_deteccion_a (resolución/umbral del analizador en A).
Señal: corriente_dc (componente de CD reportada por el instrumento).
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef


@register("CE-Q-06")
class InyeccionCorrienteDirecta(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if "corriente_dc" not in data.df.columns:
            issues.append(InputIssue("Señal corriente_dc (componente de CD del analizador) requerida"))
        if not params.get("umbral_deteccion_a"):
            issues.append(InputIssue(
                "Parámetro 'umbral_deteccion_a' requerido (umbral de detección del instrumento)"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        dc = pd.to_numeric(wd.dataset.df["corriente_dc"], errors="coerce").abs()
        calc = Calculation(extra={"dc_max": float(dc.max()) if dc.notna().any() else None})
        calc.measured = [MeasuredValue(nombre="corriente_dc_max", valor=calc.extra["dc_max"],
                                       unidad="A")]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        umbral = float(wd.params["umbral_deteccion_a"])
        dc_max = calc.extra.get("dc_max")
        return [CriterionCheck(
            nombre="sin_inyeccion_cd", valor_medido=dc_max, limite=umbral, unidad="A",
            comparacion="<=",
            cumple=bool(dc_max <= umbral) if dc_max is not None else None,
            referencia=ref,
            detalle="CD por debajo del umbral de detección del instrumento")]
