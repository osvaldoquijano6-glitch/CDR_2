"""CE-Q-03 — Variaciones rápidas de tensión (RVC).

Parámetros de ejecución: `v_nominal_v` (base para ΔV/V).

Estructura de `limites` cuando el numeral se valide:
    limite_pct:        <ΔV/V máximo por evento, %>
    max_eventos:       <número de eventos permitidos en la campaña; opcional>
    ventana_estable_s: <ventana de estado estable del detector; opcional, default 60>
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.quality_power.rvc import detect_rvc


@register("CE-Q-03")
class VariacionesRapidasTension(BaseTest):
    def validate_inputs(self, data, params):
        issues = super().validate_inputs(data, params)
        v_nom = params.get("v_nominal_v")
        if not v_nom or float(v_nom) <= 0:
            issues.append(InputIssue("Parámetro 'v_nominal_v' requerido para ΔV/V"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        calc = Calculation()
        limite = self.spec.limites.get("limite_pct")
        if limite is None:
            calc.extra["sin_umbral"] = True
            return calc
        eventos = detect_rvc(
            df["timestamp"], df["voltage"],
            v_nominal=float(wd.params["v_nominal_v"]),
            threshold_pct=float(limite),
            steady_window_s=float(self.spec.limites.get("ventana_estable_s", 60.0)))
        calc.extra["eventos"] = eventos
        calc.measured.append(MeasuredValue(
            nombre="eventos_rvc", valor=float(len(eventos)), unidad="eventos",
            detalle=f"umbral {limite}% de V nominal"))
        if eventos:
            calc.measured.append(MeasuredValue(
                nombre="delta_v_max", valor=max(e.delta_v_pct_max for e in eventos), unidad="%"))
            calc.tables.append(Evidence(
                tipo="tabla", titulo="Eventos de variación rápida de tensión",
                data={"filas": [{"inicio": str(e.inicio), "fin": str(e.fin),
                                 "delta_v_pct_max": e.delta_v_pct_max} for e in eventos]}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if calc.extra.get("sin_umbral"):
            return [CriterionCheck(nombre="rvc", cumple=None, referencia=ref,
                                   detalle="limites.limite_pct ausente")]
        eventos = calc.extra.get("eventos", [])
        max_eventos = self.spec.limites.get("max_eventos", 0)
        return [CriterionCheck(
            nombre="eventos_rvc_sobre_limite",
            valor_medido=float(len(eventos)), limite=float(max_eventos),
            unidad="eventos", comparacion="<=",
            cumple=bool(len(eventos) <= float(max_eventos)), referencia=ref,
            detalle=f"eventos con ΔV/V > {self.spec.limites['limite_pct']}%")]
