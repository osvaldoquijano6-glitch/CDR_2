"""CE-F-09 — Rampa de variación de carga (Prueba 22 Anexo 5; tipos C/D).

Criterio: rampa de subida y bajada ≤ 10 % de Pn por minuto.
Parámetros: pn_mw (potencia nominal de referencia de la rampa).
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef


@register("CE-F-09")
class RampaVariacionCarga(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if "active_power" not in data.df.columns:
            issues.append(InputIssue("Señal active_power requerida"))
        if not params.get("pn_mw"):
            issues.append(InputIssue("Parámetro 'pn_mw' requerido (base de la rampa)"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        times = pd.to_datetime(df["timestamp"])
        p = pd.Series(pd.to_numeric(df["active_power"], errors="coerce").values,
                      index=times.values).dropna()
        calc = Calculation()
        if len(p) < 3:
            return calc
        subida = float((p - p.rolling("60s").min()).max())
        bajada = float((p.rolling("60s").max() - p).max())
        calc.extra.update({"subida": subida, "bajada": bajada})
        calc.measured = [
            MeasuredValue(nombre="rampa_subida_max", valor=round(subida, 4), unidad="MW/min",
                          detalle="máximo incremento en ventana móvil de 60 s"),
            MeasuredValue(nombre="rampa_bajada_max", valor=round(bajada, 4), unidad="MW/min"),
        ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        pct = self.spec.limites.get("rampa_max_pct_pn_min")
        if pct is None or "subida" not in calc.extra:
            return [CriterionCheck(nombre="rampa", cumple=None, referencia=ref,
                                   detalle="Sin límite en matriz o registro insuficiente")]
        lim_mw = float(pct) / 100.0 * float(wd.params["pn_mw"])
        checks = []
        for nombre, valor in (("rampa_subida", calc.extra["subida"]),
                              ("rampa_bajada", calc.extra["bajada"])):
            checks.append(CriterionCheck(
                nombre=nombre, valor_medido=round(valor, 4), limite=round(lim_mw, 4),
                unidad="MW/min", comparacion="<=", cumple=bool(valor <= lim_mw),
                referencia=ref, detalle=f"límite {pct}% de Pn ({wd.params['pn_mw']} MW)/min"))
        return checks
