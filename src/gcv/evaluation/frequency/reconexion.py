"""CE-F-10 — Reconexión automática (2.2.8 Manual INTE; Prueba 6 Anexo 5).

Criterios: reconectar solo con f en [58.8, 60.2] Hz y V en ±5 % de Vnom,
ambas estables durante ≥ 5 min previos; rampa de toma de carga ≤ 10 % de la
Capacidad Instalada Neta por minuto.

Parámetros: t_reconexion (instante de reconexión, ISO), cin_mw, v_base_v.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef


@register("CE-F-10")
class ReconexionAutomatica(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        faltan = [s for s in ("frequency", "active_power") if s not in data.df.columns]
        if faltan:
            issues.append(InputIssue(f"Señales requeridas ausentes: {faltan}"))
        for p in ("t_reconexion", "cin_mw", "v_base_v"):
            if not params.get(p):
                issues.append(InputIssue(f"Parámetro '{p}' requerido"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        lim = self.spec.limites
        t_rec = pd.Timestamp(wd.params["t_reconexion"])
        times = pd.to_datetime(df["timestamp"])
        ventana_s = float(lim.get("ventana_previa_s", 300))
        previa = (times >= t_rec - pd.Timedelta(seconds=ventana_s)) & (times < t_rec)

        calc = Calculation()
        f_prev = pd.to_numeric(df.loc[previa, "frequency"], errors="coerce").dropna()
        calc.extra["f_prev"] = f_prev
        calc.measured += [
            MeasuredValue(nombre="f_min_previa", valor=float(f_prev.min()) if not f_prev.empty else None,
                          unidad="Hz", detalle=f"{ventana_s:.0f} s previos a la reconexión"),
            MeasuredValue(nombre="f_max_previa", valor=float(f_prev.max()) if not f_prev.empty else None,
                          unidad="Hz"),
        ]
        if "voltage" in df.columns:
            v_prev = (pd.to_numeric(df.loc[previa, "voltage"], errors="coerce")
                      / float(wd.params["v_base_v"])).dropna()
            calc.extra["v_prev"] = v_prev
            if not v_prev.empty:
                calc.measured += [
                    MeasuredValue(nombre="v_min_previa", valor=float(v_prev.min()), unidad="pu"),
                    MeasuredValue(nombre="v_max_previa", valor=float(v_prev.max()), unidad="pu"),
                ]

        # rampa de toma de carga: máx ΔP en ventana móvil de 60 s tras la reconexión
        post = times >= t_rec
        p_post = pd.Series(pd.to_numeric(df.loc[post, "active_power"], errors="coerce").values,
                           index=times[post].values).dropna()
        rampa = None
        if len(p_post) >= 2:
            rolled_min = p_post.rolling("60s").min()
            rampa = float((p_post - rolled_min).max())  # MW ganados en cualquier minuto
            calc.measured.append(MeasuredValue(
                nombre="rampa_max", valor=rampa, unidad="MW/min",
                detalle="máximo incremento de P en ventana móvil de 60 s tras la reconexión"))
        calc.extra["rampa"] = rampa
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        checks: list[CriterionCheck] = []

        f_prev = calc.extra.get("f_prev")
        f_rango = lim.get("f_rango_hz")
        if f_rango and f_prev is not None and not f_prev.empty:
            dentro = bool(f_prev.min() >= f_rango[0] and f_prev.max() <= f_rango[1])
            checks.append(CriterionCheck(
                nombre="frecuencia_previa_estable",
                valor_medido=float(f_prev.max()), limite=float(f_rango[1]), unidad="Hz",
                comparacion=f"en [{f_rango[0]}, {f_rango[1]}]", cumple=dentro, referencia=ref,
                detalle=f"mín {f_prev.min():.3f} Hz en los 5 min previos"))
        else:
            checks.append(CriterionCheck(nombre="frecuencia_previa_estable", cumple=None,
                                         referencia=ref, detalle="Sin muestras previas o sin rango"))

        v_prev = calc.extra.get("v_prev")
        v_tol = lim.get("v_tolerancia_pct")
        if v_tol is not None and v_prev is not None and not v_prev.empty:
            lo, hi = 1 - float(v_tol) / 100, 1 + float(v_tol) / 100
            dentro = bool(v_prev.min() >= lo and v_prev.max() <= hi)
            checks.append(CriterionCheck(
                nombre="tension_previa_estable",
                valor_medido=float(v_prev.max()), limite=hi, unidad="pu",
                comparacion=f"en ±{v_tol}% Vnom", cumple=dentro, referencia=ref))
        else:
            checks.append(CriterionCheck(nombre="tension_previa_estable", cumple=None,
                                         referencia=ref,
                                         detalle="Sin señal de tensión en ventana previa"))

        rampa = calc.extra.get("rampa")
        rampa_pct = lim.get("rampa_max_pct_cin_min")
        if rampa_pct is not None and rampa is not None:
            lim_mw = float(rampa_pct) / 100 * float(wd.params["cin_mw"])
            checks.append(CriterionCheck(
                nombre="rampa_toma_de_carga",
                valor_medido=round(rampa, 4), limite=round(lim_mw, 4), unidad="MW/min",
                comparacion="<=", cumple=bool(rampa <= lim_mw), referencia=ref,
                detalle=f"límite {rampa_pct}% de CIN ({wd.params['cin_mw']} MW) por minuto"))
        else:
            checks.append(CriterionCheck(nombre="rampa_toma_de_carga", cumple=None,
                                         referencia=ref, detalle="Sin datos post-reconexión"))
        return checks
