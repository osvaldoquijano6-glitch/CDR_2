"""CE-V-02 y CE-V-03 — Capacidad de potencia reactiva.

CE-V-02 (Prueba 13, tipos B/C/D): sostener F.P. de al menos 0.95 en atraso y
0.95 en adelanto en el PI, evaluado en los niveles de carga del protocolo.

CE-V-03 (Pruebas 14/15, tipos C/D): perfil Q/Pmáx — alcanzar al menos ±0.33
(área blanca obligatoria de la Tabla 3.3.2); rango máximo exigible ±0.5.
Parámetros: pmax_mw (Capacidad Instalada Neta).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef


def _fp_con_signo(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(FP magnitud, Q) — el signo de Q separa atraso/adelanto."""
    p = pd.to_numeric(df["active_power"], errors="coerce")
    q = pd.to_numeric(df["reactive_power"], errors="coerce")
    s = np.sqrt(p**2 + q**2)
    return (p.abs() / s).where(s > 0), q


@register("CE-V-02")
class CapacidadReactiva(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        faltan = [c for c in ("active_power", "reactive_power") if c not in data.df.columns]
        if faltan:
            issues.append(InputIssue(f"Señales requeridas ausentes: {faltan}"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        fp, q = _fp_con_signo(wd.dataset.df)
        calc = Calculation(extra={"fp": fp, "q": q})
        inductivo = fp[q > 0].dropna()   # entrega de Q (sobreexcitado / atraso)
        capacitivo = fp[q < 0].dropna()  # absorción de Q (subexcitado / adelanto)
        calc.extra["fp_atraso"] = float(inductivo.min()) if not inductivo.empty else None
        calc.extra["fp_adelanto"] = float(capacitivo.min()) if not capacitivo.empty else None
        calc.measured = [
            MeasuredValue(nombre="q_max_entregada", unidad="MVAr",
                          valor=float(q.max()) if q.notna().any() else None),
            MeasuredValue(nombre="q_max_absorbida", unidad="MVAr",
                          valor=float(q.min()) if q.notna().any() else None),
            MeasuredValue(nombre="fp_minimo_en_atraso", valor=calc.extra["fp_atraso"]),
            MeasuredValue(nombre="fp_minimo_en_adelanto", valor=calc.extra["fp_adelanto"]),
        ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        fp_min = self.spec.limites.get("fp_min")
        if fp_min is None:
            return [CriterionCheck(nombre="capacidad_reactiva", cumple=None, referencia=ref,
                                   detalle="limites.fp_min ausente")]
        checks = []
        for nombre, valor in (("fp_en_atraso", calc.extra.get("fp_atraso")),
                              ("fp_en_adelanto", calc.extra.get("fp_adelanto"))):
            checks.append(CriterionCheck(
                nombre=nombre, valor_medido=valor, limite=float(fp_min), comparacion=">=",
                cumple=bool(valor >= float(fp_min)) if valor is not None else None,
                referencia=ref,
                detalle=None if valor is not None
                else "La prueba no barrió esta condición (sin muestras con ese signo de Q)"))
        return checks


@register("CE-V-03")
class PerfilQPmax(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        faltan = [c for c in ("active_power", "reactive_power") if c not in data.df.columns]
        if faltan:
            issues.append(InputIssue(f"Señales requeridas ausentes: {faltan}"))
        if not params.get("pmax_mw"):
            issues.append(InputIssue("Parámetro 'pmax_mw' (Capacidad Instalada Neta) requerido"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        pmax = float(wd.params["pmax_mw"])
        q_pmax = pd.to_numeric(df["reactive_power"], errors="coerce") / pmax
        calc = Calculation(extra={"q_pmax_max": float(q_pmax.max()),
                                  "q_pmax_min": float(q_pmax.min())})
        calc.measured = [
            MeasuredValue(nombre="q_pmax_entregado", valor=round(calc.extra["q_pmax_max"], 4),
                          unidad="pu de Pmáx"),
            MeasuredValue(nombre="q_pmax_absorbido", valor=round(calc.extra["q_pmax_min"], 4),
                          unidad="pu de Pmáx"),
        ]
        calc.tables.append(Evidence(
            tipo="tabla", titulo="Perfil Q/Pmáx",
            data={"q_pmax_max": calc.extra["q_pmax_max"],
                  "q_pmax_min": calc.extra["q_pmax_min"], "pmax_mw": pmax}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        obligatorio = self.spec.limites.get("q_pmax_obligatorio")
        if obligatorio is None:
            return [CriterionCheck(nombre="perfil_q_pmax", cumple=None, referencia=ref,
                                   detalle="limites.q_pmax_obligatorio ausente")]
        obligatorio = float(obligatorio)
        return [
            CriterionCheck(
                nombre="q_pmax_entrega", valor_medido=round(calc.extra["q_pmax_max"], 4),
                limite=obligatorio, comparacion=">=",
                cumple=bool(calc.extra["q_pmax_max"] >= obligatorio), referencia=ref,
                detalle="área blanca obligatoria (Tabla 3.3.2)"),
            CriterionCheck(
                nombre="q_pmax_absorcion", valor_medido=round(calc.extra["q_pmax_min"], 4),
                limite=-obligatorio, comparacion="<=",
                cumple=bool(calc.extra["q_pmax_min"] <= -obligatorio), referencia=ref),
        ]
