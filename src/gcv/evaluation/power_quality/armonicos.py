"""CE-Q-04 / CE-Q-05 — Armónicos de tensión (THD) y de corriente (TDD).

Estructura de `limites` cuando el numeral se valide:
    percentil:      <percentil de agregaciones a comparar, p. ej. 95>
    thd_max_pct:    (CE-Q-04) límite de THD de tensión
    tdd_max_pct:    (CE-Q-05) límite de TDD
    armonicos:      {orden: límite_pct, ...} límites individuales

Los armónicos exigidos por la tabla pero ausentes en la medición generan un
check no evaluable (nunca se dan por cumplidos en silencio).
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.quality_power.harmonics import percentile_by_harmonic, series_percentile


class _ArmonicosBase(BaseTest):
    kind: str  # "voltage" | "current"
    total_signal: str  # "thd_voltage" | "tdd"
    total_limit_key: str  # "thd_max_pct" | "tdd_max_pct"
    total_name: str  # "THD" | "TDD"

    def validate_inputs(self, data, params):
        # Basta con el indicador total o con armónicos individuales.
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        has_total = self.total_signal in data.df.columns
        has_individual = bool(percentile_by_harmonic(data.df, self.kind))
        if not has_total and not has_individual:
            from gcv.evaluation.base import InputIssue
            issues.append(InputIssue(
                f"Sin señal {self.total_signal} ni armónicos individuales "
                f"harmonic_{self.kind}_<n>"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        pct = float(self.spec.limites.get("percentil", 95))
        calc = Calculation()
        calc.extra["percentil"] = pct

        if self.total_signal in df.columns:
            total = series_percentile(df[self.total_signal], pct)
            calc.extra["total"] = total
            if total is not None:
                calc.measured.append(MeasuredValue(
                    nombre=f"{self.total_name.lower()}_p{pct:g}", valor=total, unidad="%"))

        individual = percentile_by_harmonic(df, self.kind, pct)
        calc.extra["individual"] = individual
        if individual:
            calc.tables.append(Evidence(
                tipo="tabla", titulo=f"Percentil {pct:g} por armónico ({self.kind})",
                data={"percentiles_pct": individual}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        pct = calc.extra["percentil"]
        checks: list[CriterionCheck] = []

        total_max = lim.get(self.total_limit_key)
        if total_max is not None:
            total = calc.extra.get("total")
            checks.append(CriterionCheck(
                nombre=f"{self.total_name.lower()}_p{pct:g}",
                valor_medido=total, limite=float(total_max), unidad="%", comparacion="<=",
                cumple=bool(total <= float(total_max)) if total is not None else None,
                referencia=ref,
                detalle=None if total is not None else f"Sin señal {self.total_signal}"))

        tabla = lim.get("armonicos") or {}
        individual = calc.extra.get("individual", {})
        for orden, limite in sorted(tabla.items(), key=lambda kv: int(kv[0])):
            orden = int(orden)
            medido = individual.get(orden)
            checks.append(CriterionCheck(
                nombre=f"h{orden}_p{pct:g}",
                valor_medido=medido, limite=float(limite), unidad="%", comparacion="<=",
                cumple=bool(medido <= float(limite)) if medido is not None else None,
                referencia=ref,
                detalle=None if medido is not None else "Armónico exigido sin medición"))

        if not checks:
            checks.append(CriterionCheck(
                nombre="armonicos", cumple=None, referencia=ref,
                detalle=f"limites.{self.total_limit_key} / armonicos ausentes"))
        return checks


@register("CE-Q-04")
class ArmonicosTension(_ArmonicosBase):
    kind = "voltage"
    total_signal = "thd_voltage"
    total_limit_key = "thd_max_pct"
    total_name = "THD"


@register("CE-Q-05")
class ArmonicosCorriente(_ArmonicosBase):
    kind = "current"
    total_signal = "tdd"
    total_limit_key = "tdd_max_pct"
    total_name = "TDD"
