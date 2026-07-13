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
from gcv.quality_power.harmonics import (
    percentile_by_harmonic, percentile_by_interharmonic, series_percentile)


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
            calc.extra["total_p99"] = series_percentile(df[self.total_signal], 99)
            if total is not None:
                calc.measured.append(MeasuredValue(
                    nombre=f"{self.total_name.lower()}_p{pct:g}", valor=total, unidad="%"))

        individual = percentile_by_harmonic(df, self.kind, pct)
        calc.extra["individual"] = individual
        if individual:
            calc.tables.append(Evidence(
                tipo="tabla", titulo=f"Percentil {pct:g} por armónico ({self.kind})",
                data={"percentiles_pct": individual}))

        inter = percentile_by_interharmonic(df, self.kind, pct)
        calc.extra["interarmonicos"] = inter
        if inter:
            peor = max(inter, key=inter.get)
            calc.measured.append(MeasuredValue(
                nombre=f"interarmonico_max_p{pct:g}", valor=inter[peor], unidad="%",
                detalle=f"grupo interarmónico {peor} (de {len(inter)} medidos)"))
            calc.tables.append(Evidence(
                tipo="tabla", titulo=f"Percentil {pct:g} por grupo interarmónico ({self.kind})",
                data={"percentiles_pct": inter}))
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
            factor = lim.get("p99_factor")
            if factor and total is not None:
                p99 = calc.extra.get("total_p99")
                checks.append(CriterionCheck(
                    nombre=f"{self.total_name.lower()}_p99", valor_medido=p99,
                    limite=round(float(factor) * float(total_max), 4), unidad="%",
                    comparacion="<=",
                    cumple=bool(p99 <= float(factor) * float(total_max)) if p99 is not None else None,
                    referencia=ref, detalle=f"P99 ≤ {factor} × límite"))

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

        inter_max = lim.get("interarmonico_max_pct")
        if inter_max is not None:
            inter = calc.extra.get("interarmonicos", {})
            if inter:
                peor = max(inter, key=inter.get)
                checks.append(CriterionCheck(
                    nombre=f"interarmonico_max_p{pct:g}",
                    valor_medido=inter[peor], limite=float(inter_max), unidad="%",
                    comparacion="<=",
                    cumple=bool(inter[peor] <= float(inter_max)),
                    referencia=ref,
                    detalle=f"máximo en el grupo interarmónico {peor} "
                            f"({len(inter)} grupos medidos)"))
            else:
                checks.append(CriterionCheck(
                    nombre="interarmonicos", valor_medido=None,
                    limite=float(inter_max), unidad="%", comparacion="<=",
                    cumple=None, referencia=ref,
                    detalle="Límite exigido sin medición de interarmónicos "
                            "(interharmonic_*_<n>) del analizador"))

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
    """Los límites dependen del nivel de tensión y de Icc/IL (Tablas 2.8.A/B/C).

    Con `limites.tabla_tdd` y los parámetros `v_kv` + `icc_il` (o icc_a e il_a)
    se resuelven el límite DATD y la tabla por armónica; pares = 25 % del impar.
    """

    kind = "current"
    total_signal = "tdd"
    total_limit_key = "tdd_max_pct"
    total_name = "TDD"

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        lim = self.spec.limites
        if lim.get("tabla_tdd"):
            v_kv = wd.params.get("v_kv")
            icc_il = wd.params.get("icc_il")
            if icc_il is None and wd.params.get("icc_a") and wd.params.get("il_a"):
                icc_il = float(wd.params["icc_a"]) / float(wd.params["il_a"])
            if v_kv is None or icc_il is None:
                ref = NormRef(documento=self.spec.manual_referencia or "",
                              numeral=self.spec.numeral, version=self.spec.fuente_documental)
                return [CriterionCheck(
                    nombre="tdd", cumple=None, referencia=ref,
                    detalle="Se requieren parámetros v_kv e icc_il (o icc_a e il_a) "
                            "para resolver la tabla 2.8")]
            from gcv.quality_power.tdd import limite_armonica, resolver_fila

            fila = resolver_fila(float(v_kv), float(icc_il))
            pares = float(lim.get("pares_pct_de_impares", 25))
            armonicos = {orden: limite_armonica(orden, fila, pares)
                         for orden in calc.extra.get("individual", {})}
            armonicos = {k: v for k, v in armonicos.items() if v is not None}
            resueltos = {k: v for k, v in lim.items() if k != "tabla_tdd"}
            resueltos.update({"tdd_max_pct": fila["datd"], "armonicos": armonicos})
            self.spec = self.spec.model_copy(update={"limites": resueltos})
        return super().evaluate(calc, wd)
