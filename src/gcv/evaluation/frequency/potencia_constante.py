"""CE-F-07 — Potencia activa constante en la banda 60.0–60.2 Hz (2.2.7.i).

Criterio: P se mantiene esencialmente constante mientras la frecuencia esté
dentro de la banda, sin acciones de regulación adicionales. La tolerancia de
"constante" es de protocolo (parámetro tolerancia_mw, o tolerancia_pct de
p_ref_mw), no normativa.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef


@register("CE-F-07")
class PotenciaActivaConstante(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = super().validate_inputs(data, params)
        if params.get("tolerancia_mw") is None and not (
                params.get("tolerancia_pct") and params.get("p_ref_mw")):
            issues.append(InputIssue(
                "Tolerancia de protocolo requerida: 'tolerancia_mw' o "
                "'tolerancia_pct' + 'p_ref_mw'"))
        return issues

    def _tolerancia(self, params: dict) -> float:
        if params.get("tolerancia_mw") is not None:
            return float(params["tolerancia_mw"])
        return float(params["tolerancia_pct"]) / 100.0 * float(params["p_ref_mw"])

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        banda = self.spec.limites.get("banda_hz", [60.0, 60.2])
        f = pd.to_numeric(df["frequency"], errors="coerce")
        p = pd.to_numeric(df["active_power"], errors="coerce")
        en_banda = (f >= banda[0]) & (f <= banda[1])
        p_banda = p[en_banda].dropna()
        calc = Calculation(extra={"n": int(len(p_banda))})
        if not p_banda.empty:
            mediana = float(p_banda.median())
            desv_max = float((p_banda - mediana).abs().max())
            calc.extra.update({"mediana": mediana, "desv_max": desv_max})
            calc.measured = [
                MeasuredValue(nombre="p_mediana_en_banda", valor=round(mediana, 4), unidad="MW",
                              detalle=f"banda {banda[0]}–{banda[1]} Hz, {len(p_banda)} muestras"),
                MeasuredValue(nombre="desviacion_maxima", valor=round(desv_max, 4), unidad="MW"),
            ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if not calc.extra.get("n"):
            return [CriterionCheck(nombre="p_constante", cumple=None, referencia=ref,
                                   detalle="Sin muestras dentro de la banda de frecuencia")]
        tol = self._tolerancia(wd.params)
        desv = calc.extra["desv_max"]
        return [CriterionCheck(
            nombre="p_constante_en_banda", valor_medido=round(desv, 4),
            limite=round(tol, 4), unidad="MW", comparacion="<=",
            cumple=bool(desv <= tol), referencia=ref,
            detalle="desviación máxima respecto a la mediana dentro de la banda "
                    "(tolerancia de protocolo)")]
