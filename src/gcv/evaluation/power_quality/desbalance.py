"""CE-Q-01 — Desbalance de tensión.

El método de cálculo forma parte del criterio normativo: se ejecuta el que
declare `limites.metodo` una vez validado el numeral.

Estructura de `limites` cuando el numeral se valide:
    metodo:      "nema" (fases) | "iec_ll" (línea-línea) | "unbalance" (señal
                 ya calculada por el analizador)
    limite_pct:  <% máximo>
    percentil:   <p. ej. 95>
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.quality_power.harmonics import series_percentile
from gcv.quality_power.unbalance import unbalance_iec_ll, unbalance_nema

_PHASE = ["voltage_a", "voltage_b", "voltage_c"]
_LINE = ["voltage_ab", "voltage_bc", "voltage_ca"]


def _available_series(df: pd.DataFrame, metodo: str | None) -> tuple[str, pd.Series] | None:
    """(método_usado, serie de desbalance %) según datos y método declarado."""
    if metodo in (None, "unbalance") and "unbalance" in df.columns:
        return "unbalance", pd.to_numeric(df["unbalance"], errors="coerce")
    if metodo in (None, "nema") and all(c in df.columns for c in _PHASE):
        return "nema", unbalance_nema(df[_PHASE[0]], df[_PHASE[1]], df[_PHASE[2]])
    if metodo in (None, "iec_ll") and all(c in df.columns for c in _LINE):
        return "iec_ll", unbalance_iec_ll(df[_LINE[0]], df[_LINE[1]], df[_LINE[2]])
    return None


@register("CE-Q-01")
class Desbalance(BaseTest):
    def validate_inputs(self, data, params):
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if _available_series(data.df, None) is None:
            issues.append(InputIssue(
                "Se requiere señal 'unbalance', o las tres tensiones de fase "
                "(voltage_a/b/c), o las tres de línea (voltage_ab/bc/ca)"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        metodo_norma = self.spec.limites.get("metodo")
        found = _available_series(wd.dataset.df, metodo_norma)
        calc = Calculation()
        if found is None:
            calc.extra["sin_metodo"] = metodo_norma
            return calc
        metodo, serie = found
        pct = float(self.spec.limites.get("percentil", 95))
        value = series_percentile(serie, pct)
        calc.extra.update({"metodo": metodo, "percentil": pct, "valor": value,
                           "p99": series_percentile(serie, 99)})
        if value is not None:
            calc.measured.append(MeasuredValue(
                nombre=f"desbalance_p{pct:g}", valor=value, unidad="%",
                detalle=f"método {metodo}"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if "sin_metodo" in calc.extra:
            return [CriterionCheck(
                nombre="desbalance", cumple=None, referencia=ref,
                detalle=f"El método exigido '{calc.extra['sin_metodo']}' no es calculable "
                        "con las señales disponibles")]
        limite = self.spec.limites.get("limite_pct")
        if limite is None:
            return [CriterionCheck(nombre="desbalance", cumple=None, referencia=ref,
                                   detalle="limites.limite_pct ausente")]
        value = calc.extra.get("valor")
        pct = calc.extra["percentil"]
        checks = [CriterionCheck(
            nombre=f"desbalance_p{pct:g}", valor_medido=value, limite=float(limite),
            unidad="%", comparacion="<=",
            cumple=bool(value <= float(limite)) if value is not None else None,
            referencia=ref, detalle=f"método {calc.extra.get('metodo')}")]
        # Criterio dual del Cap. 7 (Manual INTE): P99 ≤ 1.5 × límite
        if self.spec.limites.get("p99_factor"):
            factor = float(self.spec.limites["p99_factor"])
            p99 = calc.extra.get("p99")
            checks.append(CriterionCheck(
                nombre="desbalance_p99", valor_medido=p99,
                limite=round(factor * float(limite), 4), unidad="%", comparacion="<=",
                cumple=bool(p99 <= factor * float(limite)) if p99 is not None else None,
                referencia=ref, detalle=f"P99 ≤ {factor} × límite"))
        return checks
