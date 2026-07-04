"""CE-P-01 — Capacidad instalada neta.

Parámetros de ejecución: `capacidad_declarada_mw` (valor a demostrar).

Estructura de `limites` cuando el numeral POC/Anexo 5 se valide:
    ventana_sostenimiento_s: <duración del promedio móvil exigido>
    tolerancia_pct:          <% admisible por debajo del valor declarado>
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.statistics import basic_stats, sustained_max


@register("CE-P-01")
class CapacidadInstaladaNeta(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = super().validate_inputs(data, params)
        if not params.get("capacidad_declarada_mw"):
            issues.append(InputIssue("Parámetro 'capacidad_declarada_mw' requerido"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        calc = Calculation()
        stats = basic_stats(df["active_power"])
        calc.measured = [MeasuredValue(nombre=f"p_{k}", valor=v, unidad="MW")
                         for k, v in stats.items()]

        window = self.spec.limites.get("ventana_sostenimiento_s")
        if window:
            sustained = sustained_max(df["timestamp"], df["active_power"], float(window))
            calc.extra["sostenido"] = sustained
            if sustained:
                calc.measured.append(MeasuredValue(
                    nombre="p_max_sostenida", valor=sustained["valor"], unidad="MW",
                    detalle=f"promedio móvil de {window} s, ventana que termina en "
                            f"{sustained['fin_ventana']}"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        tol = self.spec.limites.get("tolerancia_pct")
        sustained = calc.extra.get("sostenido")
        if tol is None or "ventana_sostenimiento_s" not in self.spec.limites:
            return [CriterionCheck(nombre="capacidad_demostrada", cumple=None, referencia=ref,
                                   detalle="limites.ventana_sostenimiento_s / tolerancia_pct ausentes")]
        if not sustained:
            return [CriterionCheck(nombre="capacidad_demostrada", cumple=None, referencia=ref,
                                   detalle="Registro insuficiente para el promedio móvil exigido")]
        declarada = float(wd.params["capacidad_declarada_mw"])
        minimo = declarada * (1.0 - float(tol) / 100.0)
        return [CriterionCheck(
            nombre="capacidad_demostrada",
            valor_medido=sustained["valor"], limite=round(minimo, 4), unidad="MW",
            comparacion=">=", cumple=bool(sustained["valor"] >= minimo), referencia=ref,
            detalle=f"declarada {declarada} MW, tolerancia {tol}%")]
