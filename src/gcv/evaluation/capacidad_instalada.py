"""CE-P-01 — Capacidad instalada neta.

Parámetros de ejecución: `capacidad_declarada_mw` (valor a demostrar).

Estructura de `limites` cuando el numeral POC/Anexo 5 se valide:
    ventana_sostenimiento_s: <duración del promedio móvil exigido>
    tolerancia_pct:          <% admisible por debajo del valor declarado>
"""

from __future__ import annotations

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.statistics import basic_stats, sustained_max


@register("CE-P-01")
class CapacidadInstaladaNeta(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = super().validate_inputs(data, params)
        if not params.get("capacidad_declarada_mw"):
            issues.append(InputIssue("Parámetro 'capacidad_declarada_mw' requerido"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        import pandas as pd

        from gcv.signal_processing.statistics import sample_dt

        df = wd.dataset.df
        calc = Calculation()
        stats = basic_stats(df["active_power"])
        calc.measured = [MeasuredValue(nombre=f"p_{k}", valor=v, unidad="MW")
                         for k, v in stats.items()]

        # horas de operación (P > umbral) y de paro dentro del periodo
        umbral = float(wd.params.get("umbral_operacion_mw", 0.0))
        p = pd.to_numeric(df["active_power"], errors="coerce")
        dt_h = sample_dt(df["timestamp"]) / 3600.0
        operando = (p > umbral) & p.notna()
        horas_op = float(dt_h[operando].sum())
        horas_paro = float(dt_h[~operando].sum())
        calc.extra.update({"horas_op": horas_op, "horas_paro": horas_paro})
        calc.measured += [
            MeasuredValue(nombre="horas_operacion", valor=round(horas_op, 2), unidad="h",
                          detalle=f"P > {umbral} MW"),
            MeasuredValue(nombre="horas_paro", valor=round(horas_paro, 2), unidad="h"),
        ]

        # modalidad abasto aislado: no inyección (P_neta ≤ 0 en el PI)
        if wd.params.get("modalidad") == "abasto_aislado":
            inyecciones = int((p > 0).sum())
            calc.extra["inyecciones"] = inyecciones
            calc.measured.append(MeasuredValue(
                nombre="muestras_con_inyeccion", valor=float(inyecciones), unidad="muestras"))

        window = self.spec.limites.get("ventana_sostenimiento_s")
        if window:
            sustained = sustained_max(df["timestamp"], df["active_power"], float(window))
            calc.extra["sostenido"] = sustained
            if sustained:
                calc.measured.append(MeasuredValue(
                    nombre="p_max_sostenida", valor=sustained["valor"], unidad="MW",
                    detalle=f"promedio móvil de {window} s"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        checks: list[CriterionCheck] = []

        horas_min = lim.get("horas_operacion_min")
        if horas_min is not None:
            checks.append(CriterionCheck(
                nombre="horas_de_operacion",
                valor_medido=round(calc.extra["horas_op"], 2), limite=float(horas_min),
                unidad="h", comparacion=">=",
                cumple=bool(calc.extra["horas_op"] >= float(horas_min)), referencia=ref,
                detalle="operación acumulada al nivel de carga comprometido"))
        paro_max = lim.get("paro_maximo_por_falla_h")
        if paro_max is not None:
            checks.append(CriterionCheck(
                nombre="horas_de_paro",
                valor_medido=round(calc.extra["horas_paro"], 2), limite=float(paro_max),
                unidad="h", comparacion="<=",
                cumple=bool(calc.extra["horas_paro"] <= float(paro_max)), referencia=ref,
                detalle="el límite normativo aplica a paros por falla; confirmar causa "
                        "de los paros registrados"))
        if "inyecciones" in calc.extra:
            checks.append(CriterionCheck(
                nombre="no_inyeccion",
                valor_medido=float(calc.extra["inyecciones"]), limite=0.0,
                unidad="muestras", comparacion="==",
                cumple=calc.extra["inyecciones"] == 0, referencia=ref,
                detalle="modalidad abasto aislado: P_neta ≤ 0 MW en el PI"))

        tol = lim.get("tolerancia_pct")
        sustained = calc.extra.get("sostenido")
        if tol is not None and sustained:
            declarada = float(wd.params["capacidad_declarada_mw"])
            minimo = declarada * (1.0 - float(tol) / 100.0)
            checks.append(CriterionCheck(
                nombre="capacidad_demostrada",
                valor_medido=sustained["valor"], limite=round(minimo, 4), unidad="MW",
                comparacion=">=", cumple=bool(sustained["valor"] >= minimo), referencia=ref,
                detalle=f"declarada {declarada} MW, tolerancia {tol}%"))
        if not checks:
            checks.append(CriterionCheck(nombre="capacidad", cumple=None, referencia=ref,
                                         detalle="Sin criterios configurados en limites"))
        return checks
