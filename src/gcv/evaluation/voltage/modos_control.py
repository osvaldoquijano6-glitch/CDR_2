"""CE-V-04/05/06 — Modos de control de tensión, potencia reactiva y FP.

Sección 3.5.3 del Manual INTE (asíncronas B*/C/D): ante escalón de consigna,
alcance del 90 % en ≤ 3 s, estabilización en ≤ 5 s y error en régimen
permanente por modo (V: 0.5 % · Q: 2 % · FP: 0.1 %).

Estructura de `limites`:
    t90_max_s, t_estabilizacion_max_s, error_max_pct

Parámetros de ejecución:
    error_base: base del error porcentual (V: v_base_v en V → pu; Q: q_max_mvar;
                FP: 1.0). Obligatoria para dictaminar el error.
    t_escalon:  instante del escalón de consigna (ISO); si falta, se detecta el
                mayor escalón de la señal de consigna.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.steps import detect_steps, response_times


class ControlEscalonBase(BaseTest):
    señal: str  # variable controlada
    consigna: str  # señal de consigna

    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        faltan = [s for s in (self.señal, self.consigna) if s not in data.df.columns]
        if faltan:
            issues.append(InputIssue(f"Señales requeridas ausentes: {faltan}"))
        if not params.get("error_base"):
            issues.append(InputIssue(
                "Parámetro 'error_base' requerido (base del error porcentual del modo)"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        calc = Calculation()
        times = pd.to_datetime(df["timestamp"])
        consigna = pd.to_numeric(df[self.consigna], errors="coerce")
        medida = pd.to_numeric(df[self.señal], errors="coerce")

        if wd.params.get("t_escalon"):
            t0 = pd.Timestamp(wd.params["t_escalon"])
            antes = consigna[times < t0]
            despues = consigna[times >= t0]
            if antes.dropna().empty or despues.dropna().empty:
                calc.extra["sin_escalon"] = True
                return calc
            c_ini, c_fin = float(antes.dropna().iloc[-1]), float(despues.dropna().iloc[-1])
        else:
            rango = float(consigna.max() - consigna.min()) if consigna.notna().any() else 0.0
            steps = detect_steps(times, consigna, min_delta=max(rango * 0.5, 1e-9), window_s=2)
            if not steps:
                calc.extra["sin_escalon"] = True
                return calc
            t0 = max(steps, key=lambda s: abs(s.delta)).t
            # la consigna es una señal escalonada: sus niveles reales son los
            # valores estables antes/después, no las medianas móviles del detector
            antes = consigna[times < t0].dropna()
            despues = consigna[times > t0].dropna()
            if antes.empty or despues.empty:
                calc.extra["sin_escalon"] = True
                return calc
            c_ini, c_fin = float(antes.iloc[-1]), float(despues.median())

        delta = c_fin - c_ini
        base = float(wd.params["error_base"])
        err_max = self.spec.limites.get("error_max_pct")
        tol_estab = (float(err_max) / 100.0 * base) if err_max is not None else abs(delta) * 0.05

        t90 = response_times(times, medida, t0, target=c_fin, tolerance=abs(delta) * 0.10)
        estab = response_times(times, medida, t0, target=c_fin, tolerance=tol_estab)

        post = medida[times >= t0].dropna()
        n_final = max(len(post) // 5, 1)
        v_final = float(post.tail(n_final).mean()) if not post.empty else None
        error_pct = (abs(v_final - c_fin) / base * 100.0) if v_final is not None else None

        calc.extra.update({"t90_s": t90["t1_s"], "t_estab_s": estab["t2_s"],
                           "error_pct": error_pct, "delta": delta, "t0": str(t0)})
        calc.measured = [
            MeasuredValue(nombre="consigna_inicial", valor=c_ini),
            MeasuredValue(nombre="consigna_final", valor=c_fin),
            MeasuredValue(nombre="t90", valor=t90["t1_s"], unidad="s",
                          detalle=f"escalón en {t0}"),
            MeasuredValue(nombre="t_estabilizacion", valor=estab["t2_s"], unidad="s"),
            MeasuredValue(nombre="error_regimen_permanente",
                          valor=round(error_pct, 4) if error_pct is not None else None,
                          unidad="%", detalle=f"base {base}"),
        ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if calc.extra.get("sin_escalon"):
            return [CriterionCheck(nombre="escalon_de_consigna", cumple=None, referencia=ref,
                                   detalle="No se detectó escalón en la señal de consigna")]
        lim = self.spec.limites
        checks: list[CriterionCheck] = []
        for lim_key, extra_key, nombre in (
            ("t90_max_s", "t90_s", "alcance_90pct"),
            ("t_estabilizacion_max_s", "t_estab_s", "estabilizacion"),
        ):
            exigido = lim.get(lim_key)
            if exigido is None:
                continue
            medido = calc.extra.get(extra_key)
            checks.append(CriterionCheck(
                nombre=nombre, valor_medido=medido, limite=float(exigido), unidad="s",
                comparacion="<=",
                cumple=bool(medido <= float(exigido)) if medido is not None else None,
                referencia=ref,
                detalle=None if medido is not None else "La señal no alcanzó la banda objetivo"))
        err_max = lim.get("error_max_pct")
        if err_max is not None:
            error = calc.extra.get("error_pct")
            checks.append(CriterionCheck(
                nombre="error_regimen_permanente", valor_medido=error,
                limite=float(err_max), unidad="%", comparacion="<=",
                cumple=bool(error <= float(err_max)) if error is not None else None,
                referencia=ref))
        return checks


@register("CE-V-04")
class ControlTension(ControlEscalonBase):
    señal = "voltage"
    consigna = "setpoint_v"


@register("CE-V-05")
class ControlPotenciaReactiva(ControlEscalonBase):
    señal = "reactive_power"
    consigna = "setpoint_q"


@register("CE-V-06")
class ControlFactorPotencia(ControlEscalonBase):
    señal = "power_factor"
    consigna = "setpoint_fp"
