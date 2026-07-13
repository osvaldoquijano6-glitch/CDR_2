"""Base común de las pruebas droop: CE-F-03 (alta), CE-F-04 (baja), CE-F-05 (CPF).

Parámetros de ejecución (protocolo de la prueba, `params`):
    estatismo:  S en pu del caso ejecutado (3/5/8 % → 0.03/0.05/0.08)
    p_ref_mw:   potencia de referencia del protocolo
    p_op_mw:    opcional; si falta se deriva del estado estable pre-escalón

Estructura de `limites` cuando el numeral se valide:
    umbral_hz:                (alta/baja) umbral de activación
    banda_muerta_hz:          (CPF) banda muerta máxima
    estatismos_admisibles:    lista de S permitidos
    tolerancia_pct_pref:      tolerancia del error |P−P_esp| en % de P_ref
    cumplimiento_minimo_pct:  % mínimo de muestras en zona activa dentro de tolerancia
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.droop import DroopParams, derive_p_op, expected_power, response_error


class DroopTestBase(BaseTest):
    zona: str  # "alta" | "baja" | "ambas" — definido por cada subclase

    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = super().validate_inputs(data, params)
        if not params.get("estatismo"):
            issues.append(InputIssue("Parámetro 'estatismo' del protocolo requerido (p. ej. 0.05)"))
        if not params.get("p_ref_mw"):
            issues.append(InputIssue("Parámetro 'p_ref_mw' del protocolo requerido"))
        return issues

    def _droop_params(self, wd: WorkingData) -> DroopParams:
        lim = self.spec.limites
        heredados = self.spec.parametros_heredados
        return DroopParams(
            p_ref_mw=float(wd.params["p_ref_mw"]),
            estatismo=float(wd.params["estatismo"]),
            zona=self.zona,
            f_nom_hz=float(wd.params.get("f_nom_hz", 60.0)),
            umbral_hz=lim.get("umbral_hz", heredados.get("umbral_activacion_hz")),
            banda_muerta_hz=float(lim.get("banda_muerta_hz",
                                          heredados.get("banda_muerta_hz", 0.0)) or 0.0),
            p_max_mw=wd.params.get("p_max_mw"),
        )

    def _active_mask(self, freq: pd.Series, dp: DroopParams) -> pd.Series:
        f = pd.to_numeric(freq, errors="coerce")
        if dp.zona == "alta":
            return f > dp.umbral_hz
        if dp.zona == "baja":
            return f < dp.umbral_hz
        return (f - dp.f_nom_hz).abs() > dp.banda_muerta_hz

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        dp = self._droop_params(wd)
        calc = Calculation()
        calc.extra["droop_params"] = dp

        if wd.params.get("p_op_mw") is not None:
            p_op = {"p_op_mw": float(wd.params["p_op_mw"]), "metodo": "declarado_protocolo"}
        else:
            p_op = derive_p_op(df["timestamp"], df["frequency"], df["active_power"],
                               f_nom_hz=dp.f_nom_hz)
        if p_op is None:
            calc.extra["sin_p_op"] = True
            return calc
        calc.extra["p_op"] = p_op
        calc.measured.append(MeasuredValue(
            nombre="p_op", valor=p_op["p_op_mw"], unidad="MW",
            detalle=f"método: {p_op['metodo']}"))

        expected = expected_power(df["frequency"], p_op["p_op_mw"], dp)
        active = self._active_mask(df["frequency"], dp)
        err = response_error(df["active_power"], expected, active_mask=active)
        calc.extra.update({"expected": expected, "active": active, "error": err})

        calc.measured += [
            MeasuredValue(nombre="muestras_zona_activa", valor=float(active.sum()), unidad="muestras"),
        ]
        if err.get("n"):
            calc.measured += [
                MeasuredValue(nombre="error_abs_max", valor=err["error_abs_max_mw"], unidad="MW"),
                MeasuredValue(nombre="error_abs_p95", valor=err["error_abs_p95_mw"], unidad="MW"),
                MeasuredValue(nombre="rmse", valor=err["rmse_mw"], unidad="MW"),
            ]
        calc.tables.append(Evidence(
            tipo="tabla", titulo=f"Respuesta droop ({self.zona}), estatismo {dp.estatismo:.0%}",
            data={"p_op_mw": p_op["p_op_mw"], "error": err}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if calc.extra.get("sin_p_op"):
            return [CriterionCheck(nombre="respuesta_droop", cumple=None, referencia=ref,
                                   detalle="No fue posible derivar P_op del registro")]

        lim = self.spec.limites
        dp: DroopParams = calc.extra["droop_params"]
        checks: list[CriterionCheck] = []

        admisibles = lim.get("estatismos_admisibles")
        if admisibles:
            checks.append(CriterionCheck(
                nombre="estatismo_admisible", valor_medido=dp.estatismo, unidad="pu",
                comparacion="in", cumple=dp.estatismo in admisibles, referencia=ref,
                detalle=f"admisibles: {admisibles}"))

        tol_pct = lim.get("tolerancia_pct_pref")
        min_pct = lim.get("cumplimiento_minimo_pct")
        err = calc.extra.get("error", {})
        if tol_pct is None or min_pct is None:
            checks.append(CriterionCheck(
                nombre="error_respuesta", cumple=None, referencia=ref,
                detalle="limites.tolerancia_pct_pref / cumplimiento_minimo_pct ausentes"))
            return checks
        if not err.get("n"):
            checks.append(CriterionCheck(
                nombre="error_respuesta", cumple=None, referencia=ref,
                detalle="Sin muestras en la zona activa: el evento no activó la respuesta"))
            return checks

        df = wd.dataset.df
        tol_mw = float(tol_pct) / 100.0 * dp.p_ref_mw
        active = calc.extra["active"]
        expected = calc.extra["expected"]
        p = pd.to_numeric(df["active_power"], errors="coerce")
        within = ((p - expected).abs() <= tol_mw) & active
        pct_within = 100.0 * within.sum() / max(int(active.sum()), 1)
        checks.append(CriterionCheck(
            nombre="error_respuesta",
            valor_medido=round(float(pct_within), 2), limite=float(min_pct), unidad="%",
            comparacion=">=", cumple=bool(pct_within >= float(min_pct)), referencia=ref,
            detalle=f"muestras en zona activa dentro de ±{tol_mw:.3f} MW "
                    f"(±{tol_pct}% de P_ref)"))
        return checks
