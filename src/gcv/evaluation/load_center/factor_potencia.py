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
        # Las señales FP/P/Q son alternativas (FP directo o derivado de P y Q):
        # se sustituye la validación genérica por la comprobación específica.
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
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
        min_pct = lim.get("cumplimiento_minimo_pct")
        fp = calc.extra["fp"].dropna()
        if fp.empty:
            return [CriterionCheck(nombre="rango_fp", cumple=None, referencia=ref,
                                   detalle="Sin muestras válidas de FP")]

        # Límite por vigencia (Manual CONE 2.4: 0.95 hasta 08-abr-2026; 0.97 después).
        # Se resuelve muestra a muestra por su estampa de tiempo: los periodos que
        # cruzan la fecha de cambio quedan evaluados por tramos automáticamente.
        vigencias = lim.get("vigencias")
        if vigencias and min_pct is not None:
            times = pd.to_datetime(wd.dataset.df.loc[fp.index, "timestamp"])
            fp_min_serie = pd.Series(float("nan"), index=fp.index)
            for tramo in sorted(vigencias, key=lambda v: str(v["desde"])):
                fp_min_serie[times >= pd.Timestamp(tramo["desde"])] = float(tramo["fp_min"])
            if fp_min_serie.isna().any():
                return [CriterionCheck(nombre="rango_fp", cumple=None, referencia=ref,
                                       detalle="Muestras anteriores a toda vigencia declarada")]
            within = fp >= fp_min_serie
            fp_max = lim.get("fp_max")
            if fp_max is not None:
                within &= fp <= float(fp_max)
            pct = 100.0 * within.sum() / len(fp)
            limites_usados = sorted({v for v in fp_min_serie})
            return [CriterionCheck(
                nombre="rango_fp", valor_medido=round(float(pct), 2), limite=float(min_pct),
                unidad="%", comparacion=">=", cumple=bool(pct >= float(min_pct)),
                referencia=ref,
                detalle=f"FP mínimo por vigencia {limites_usados}; medición 5-minutal, "
                        "cumplimiento mensual exigido")]

        fp_min = lim.get("fp_min")
        if fp_min is None or min_pct is None:
            return [CriterionCheck(nombre="rango_fp", cumple=None, referencia=ref,
                                   detalle="limites.fp_min/vigencias o cumplimiento_minimo_pct ausentes")]
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
