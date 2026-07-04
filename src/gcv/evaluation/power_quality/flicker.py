"""CE-Q-02 — Flicker (Pst/Plt) con severidades precalculadas por el analizador.

Los Pst/Plt deben venir del equipo (IEC 61000-4-15); el cálculo propio desde
forma de onda queda condicionado a fs suficiente y librería validada (riesgo
3 de FASE 1).

Estructura de `limites` cuando el numeral se valide:
    percentil: <p. ej. 95>
    pst_max:   <límite de Pst>
    plt_max:   <límite de Plt>
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.quality_power.harmonics import series_percentile


@register("CE-Q-02")
class Flicker(BaseTest):
    def validate_inputs(self, data, params):
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if not ({"pst", "plt"} & set(data.df.columns)):
            issues.append(InputIssue("Sin señal pst ni plt (severidades del analizador)"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        pct = float(self.spec.limites.get("percentil", 95))
        calc = Calculation()
        calc.extra["percentil"] = pct
        for señal in ("pst", "plt"):
            if señal in df.columns:
                value = series_percentile(df[señal], pct)
                calc.extra[señal] = value
                if value is not None:
                    calc.measured.append(MeasuredValue(
                        nombre=f"{señal}_p{pct:g}", valor=value))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        pct = calc.extra["percentil"]
        checks = []
        for señal in ("pst", "plt"):
            limite = self.spec.limites.get(f"{señal}_max")
            if limite is None:
                continue
            medido = calc.extra.get(señal)
            checks.append(CriterionCheck(
                nombre=f"{señal}_p{pct:g}", valor_medido=medido, limite=float(limite),
                comparacion="<=",
                cumple=bool(medido <= float(limite)) if medido is not None else None,
                referencia=ref,
                detalle=None if medido is not None else f"Sin señal {señal}"))
        if not checks:
            checks.append(CriterionCheck(nombre="flicker", cumple=None, referencia=ref,
                                         detalle="limites.pst_max / plt_max ausentes"))
        return checks
