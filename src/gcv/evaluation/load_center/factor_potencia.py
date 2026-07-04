"""CC-04 — Factor de potencia en Centro de Carga.

Si no existe señal `power_factor`, se deriva de P y Q:
FP = |P| / sqrt(P² + Q²) (magnitud; la convención de signos exigida debe
confirmarse al validar el numeral CONE).

Estructura de `limites` cuando el numeral se valide:
    fp_min:                  <límite inferior del rango obligatorio>
    fp_max:                  <límite superior; opcional>
    cumplimiento_minimo_pct: <% mínimo de intervalos dentro del rango>
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.statistics import basic_stats


def _fp_series(df: pd.DataFrame) -> pd.Series | None:
    if "power_factor" in df.columns:
        return pd.to_numeric(df["power_factor"], errors="coerce")
    if {"active_power", "reactive_power"} <= set(df.columns):
        p = pd.to_numeric(df["active_power"], errors="coerce")
        q = pd.to_numeric(df["reactive_power"], errors="coerce")
        s = np.sqrt(p**2 + q**2)
        return (p.abs() / s).where(s > 0)
    return None


@register("CC-04")
class FactorPotenciaCentroCarga(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        # No exigir 'power_factor' textual: puede derivarse de P y Q.
        issues = [i for i in super().validate_inputs(data, params)
                  if "power_factor" not in i.mensaje]
        if _fp_series(data.df) is None:
            issues.append(InputIssue(
                "Se requiere señal power_factor, o bien active_power y reactive_power"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        fp = _fp_series(wd.dataset.df)
        calc = Calculation()
        calc.extra["fp"] = fp
        calc.measured = [MeasuredValue(nombre=f"fp_{k}", valor=v)
                         for k, v in basic_stats(fp).items()]
        if "power_factor" not in wd.dataset.df.columns:
            calc.measured.append(MeasuredValue(
                nombre="fp_derivado", valor=None,
                detalle="FP derivado de P y Q (|P|/√(P²+Q²)); convención de signos "
                        "pendiente de confirmar contra el numeral"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        fp_min, min_pct = lim.get("fp_min"), lim.get("cumplimiento_minimo_pct")
        if fp_min is None or min_pct is None:
            return [CriterionCheck(nombre="rango_fp", cumple=None, referencia=ref,
                                   detalle="limites.fp_min / cumplimiento_minimo_pct ausentes")]
        fp = calc.extra["fp"].dropna()
        if fp.empty:
            return [CriterionCheck(nombre="rango_fp", cumple=None, referencia=ref,
                                   detalle="Sin muestras válidas de FP")]
        fp_max = lim.get("fp_max")
        within = fp >= float(fp_min)
        if fp_max is not None:
            within &= fp <= float(fp_max)
        pct = 100.0 * within.sum() / len(fp)
        rango = f"[{fp_min}, {fp_max}]" if fp_max is not None else f">= {fp_min}"
        return [CriterionCheck(
            nombre="rango_fp", valor_medido=round(float(pct), 2), limite=float(min_pct),
            unidad="%", comparacion=">=", cumple=bool(pct >= float(min_pct)),
            referencia=ref, detalle=f"intervalos con FP en {rango}")]
