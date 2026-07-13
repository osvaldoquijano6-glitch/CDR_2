"""CE-F-03/04/05 — Respuesta a alta/baja frecuencia y control primario.

Los tres son el modelo droop (droop_base.DroopTestBase) en distinta zona.
CE-F-05 (CPF) añade la medición de tiempos t1/t2 hacia la potencia esperada
tras el mayor escalón de frecuencia, evaluados solo si el numeral validado
define `t_respuesta_max_s` / `t_establecimiento_max_s` en limites.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import Calculation, WorkingData
from gcv.evaluation.frequency.droop_base import DroopTestBase
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.signal_processing.steps import detect_steps, response_times


@register("CE-F-03")
class RespuestaAltaFrecuencia(DroopTestBase):
    zona = "alta"


@register("CE-F-04")
class RespuestaBajaFrecuencia(DroopTestBase):
    zona = "baja"


@register("CE-F-05")
class ControlPrimarioFrecuencia(DroopTestBase):
    zona = "ambas"

    def calculate(self, wd: WorkingData) -> Calculation:
        calc = super().calculate(wd)
        if calc.extra.get("sin_p_op"):
            return calc
        df = wd.dataset.df
        # mayor escalón de frecuencia del registro (mínimo 0.05 Hz para no
        # confundir ruido con escalón; el protocolo aplica escalones >> 0.05 Hz)
        steps = detect_steps(df["timestamp"], df["frequency"], min_delta=0.05)
        if steps:
            biggest = max(steps, key=lambda s: abs(s.delta))
            dp = calc.extra["droop_params"]
            expected = calc.extra["expected"]
            mask = pd.to_datetime(df["timestamp"]) >= biggest.t
            if mask.any():
                target = float(pd.to_numeric(expected[mask], errors="coerce").iloc[-1])
                tol_pct = self.spec.limites.get("tolerancia_pct_pref", 5.0)
                tol_mw = float(tol_pct) / 100.0 * dp.p_ref_mw
                rt = response_times(df["timestamp"], df["active_power"],
                                    biggest.t, target, tol_mw)
                calc.extra["step"] = biggest
                calc.extra["response"] = rt
                for key, name in (("t1_s", "t1_respuesta"), ("t2_s", "t2_establecimiento")):
                    if rt.get(key) is not None:
                        calc.measured.append(MeasuredValue(
                            nombre=name, valor=rt[key], unidad="s",
                            detalle=f"escalón de {biggest.delta:+.3f} Hz en {biggest.t}"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        checks = super().evaluate(calc, wd)
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        rt = calc.extra.get("response")
        for lim_key, rt_key, nombre in (
            ("t_respuesta_max_s", "t1_s", "tiempo_de_respuesta"),
            ("t_establecimiento_max_s", "t2_s", "tiempo_de_establecimiento"),
        ):
            required = lim.get(lim_key)
            if required is None:
                continue
            measured = rt.get(rt_key) if rt else None
            checks.append(CriterionCheck(
                nombre=nombre,
                valor_medido=measured, limite=float(required), unidad="s", comparacion="<=",
                cumple=bool(measured <= float(required)) if measured is not None else None,
                referencia=ref,
                detalle=None if measured is not None
                else "No se detectó escalón o la potencia no alcanzó la banda objetivo"))
        return checks
