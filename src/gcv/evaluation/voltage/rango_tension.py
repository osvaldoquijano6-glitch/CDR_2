"""CE-V-01 — Rango de tensión en el Punto de Interconexión.

Parámetros de ejecución: `v_base_v` (tensión nominal del POI en V) para
convertir la medición a pu — la base nunca se infiere.

Estructura de `limites` cuando el numeral se valide:
    bandas:
      - {v_min_pu: <pu>, v_max_pu: <pu>, t_min_s: <permanencia exigida; null =
         operación continua>}
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.statistics import basic_stats, time_in_bands


@register("CE-V-01")
class RangoTension(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = super().validate_inputs(data, params)
        v_base = params.get("v_base_v")
        if not v_base or float(v_base) <= 0:
            issues.append(InputIssue(
                "Parámetro 'v_base_v' (tensión nominal del POI en V) requerido para pu"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        v_pu = pd.to_numeric(df["voltage"], errors="coerce") / float(wd.params["v_base_v"])
        calc = Calculation()
        calc.extra["v_pu"] = v_pu
        stats = basic_stats(v_pu)
        calc.measured = [MeasuredValue(nombre=f"v_{k}", valor=v, unidad="pu")
                         for k, v in stats.items()]

        bandas = self.spec.limites.get("bandas")
        if bandas:
            perm = time_in_bands(df["timestamp"], v_pu,
                                 [(b["v_min_pu"], b["v_max_pu"]) for b in bandas])
            filas = [{"v_min_pu": b["v_min_pu"], "v_max_pu": b["v_max_pu"],
                      "t_min_s": b.get("t_min_s"), **p}
                     for b, p in zip(bandas, perm)]
            calc.extra["permanencia"] = filas
            calc.tables.append(Evidence(tipo="tabla",
                                        titulo="Permanencia por banda de tensión (pu)",
                                        data={"filas": filas}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        filas = calc.extra.get("permanencia")
        if not filas:
            return [CriterionCheck(nombre="bandas_de_tension", cumple=None, referencia=ref,
                                   detalle="limites.bandas ausente: sin tabla normativa que comparar")]
        checks = []
        for fila in filas:
            nombre = f"banda {fila['v_min_pu']}-{fila['v_max_pu']} pu"
            exigido = fila.get("t_min_s")
            if exigido is None:
                checks.append(CriterionCheck(
                    nombre=nombre, valor_medido=fila["permanencia_s"], unidad="s",
                    comparacion="operación continua", cumple=True, referencia=ref,
                    detalle=f"{fila['muestras']} muestras en banda sin desconexión registrada"))
            else:
                checks.append(CriterionCheck(
                    nombre=nombre, valor_medido=fila["permanencia_s"], limite=float(exigido),
                    unidad="s", comparacion=">=",
                    cumple=bool(fila["permanencia_s"] >= float(exigido)), referencia=ref))
        return checks
