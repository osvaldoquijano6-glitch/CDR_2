"""CE-F-08 — Limitación total/parcial de potencia activa (2.2.5 / 2.2.6).

Total: tras la consigna de 0 MW, la aportación debe detenerse en menos de
5 s (asíncronas, interfaz lógica) o en más de 5 s con rampa controlada
(síncronas, evita rechazo súbito), sin desconexión de la red.
Parcial: consigna, rampa y tolerancia definidos por CENACE (parámetros).

Parámetros de ejecución:
    modo:            "total" | "parcial"
    t_consigna:      instante de la instrucción (ISO); si falta se detecta el
                     mayor escalón descendente de setpoint_p
    tecnologia:      SINCRONA | ASINCRONA (define el sentido del criterio total)
    umbral_cero_mw:  P bajo la cual se considera aportación detenida (total)
    consigna_mw, tolerancia_mw, t_max_s: para modo parcial (criterio CENACE)
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.normalization.column_mapper import NormalizedDataset
from gcv.signal_processing.steps import detect_steps


@register("CE-F-08")
class LimitacionPotenciaActiva(BaseTest):
    def validate_inputs(self, data: NormalizedDataset, params: dict) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if "active_power" not in data.df.columns:
            issues.append(InputIssue("Señal active_power requerida"))
        modo = params.get("modo")
        if modo not in ("total", "parcial"):
            issues.append(InputIssue("Parámetro 'modo' requerido: 'total' o 'parcial'"))
        if modo == "total":
            if str(params.get("tecnologia", "")).upper() not in ("SINCRONA", "ASINCRONA"):
                issues.append(InputIssue("Parámetro 'tecnologia' requerido para el criterio total"))
            if params.get("umbral_cero_mw") is None:
                issues.append(InputIssue("Parámetro 'umbral_cero_mw' requerido"))
        return issues

    def _t_consigna(self, wd: WorkingData) -> pd.Timestamp | None:
        if wd.params.get("t_consigna"):
            return pd.Timestamp(wd.params["t_consigna"])
        df = wd.dataset.df
        if "setpoint_p" not in df.columns:
            return None
        sp = pd.to_numeric(df["setpoint_p"], errors="coerce")
        rango = float(sp.max() - sp.min()) if sp.notna().any() else 0.0
        steps = detect_steps(pd.to_datetime(df["timestamp"]), sp,
                             min_delta=max(rango * 0.5, 1e-9), window_s=2)
        bajadas = [s for s in steps if s.delta < 0]
        return max(bajadas, key=lambda s: abs(s.delta)).t if bajadas else None

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        calc = Calculation()
        t0 = self._t_consigna(wd)
        if t0 is None:
            calc.extra["sin_consigna"] = True
            return calc
        times = pd.to_datetime(df["timestamp"])
        p = pd.to_numeric(df["active_power"], errors="coerce")
        post = pd.Series(p[times >= t0].values, index=times[times >= t0].values).dropna()
        calc.extra["t0"] = t0
        calc.measured.append(MeasuredValue(
            nombre="p_al_instante_de_consigna",
            valor=float(post.iloc[0]) if not post.empty else None, unidad="MW",
            detalle=f"consigna en {t0}"))

        if wd.params["modo"] == "total":
            umbral = float(wd.params["umbral_cero_mw"])
            bajo = post[post <= umbral]
            t_alcance = (float((bajo.index[0] - t0).total_seconds())
                         if not bajo.empty else None)
            calc.extra["t_alcance"] = t_alcance
            calc.measured.append(MeasuredValue(
                nombre="t_hasta_cero", valor=t_alcance, unidad="s",
                detalle=f"tiempo hasta P ≤ {umbral} MW"))
        else:
            consigna = wd.params.get("consigna_mw")
            tol = wd.params.get("tolerancia_mw")
            if consigna is not None and tol is not None:
                en_banda = post[(post - float(consigna)).abs() <= float(tol)]
                t_alcance = (float((en_banda.index[0] - t0).total_seconds())
                             if not en_banda.empty else None)
                calc.extra["t_alcance"] = t_alcance
                calc.measured.append(MeasuredValue(
                    nombre="t_hasta_consigna", valor=t_alcance, unidad="s",
                    detalle=f"consigna {consigna} MW ± {tol} MW"))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if calc.extra.get("sin_consigna"):
            return [CriterionCheck(nombre="consigna", cumple=None, referencia=ref,
                                   detalle="Sin t_consigna declarado ni escalón de setpoint_p")]
        t_alcance = calc.extra.get("t_alcance")
        if wd.params["modo"] == "total":
            t_lim = float(self.spec.limites.get("t_limite_s", 5))
            sincrona = str(wd.params["tecnologia"]).upper() == "SINCRONA"
            if t_alcance is None:
                return [CriterionCheck(nombre="limitacion_total", cumple=None, referencia=ref,
                                       detalle="P nunca alcanzó el umbral de cero")]
            if sincrona:
                # 2.2.5 síncronas (Anexo 5 P23): rampa controlada, en MÁS de 5 s
                return [CriterionCheck(
                    nombre="limitacion_total", valor_medido=t_alcance, limite=t_lim,
                    unidad="s", comparacion=">", cumple=bool(t_alcance > t_lim),
                    referencia=ref, detalle="síncrona: rampa controlada (evita rechazo súbito)")]
            return [CriterionCheck(
                nombre="limitacion_total", valor_medido=t_alcance, limite=t_lim,
                unidad="s", comparacion="<", cumple=bool(t_alcance < t_lim),
                referencia=ref, detalle="asíncrona: interfaz lógica < 5 s")]

        t_max = wd.params.get("t_max_s")
        if t_max is None or "t_alcance" not in calc.extra:
            return [CriterionCheck(
                nombre="limitacion_parcial", cumple=None, referencia=ref,
                detalle="Criterio parcial definido por CENACE: requiere parámetros "
                        "consigna_mw, tolerancia_mw y t_max_s (documentar el oficio)")]
        return [CriterionCheck(
            nombre="limitacion_parcial", valor_medido=t_alcance, limite=float(t_max),
            unidad="s", comparacion="<=",
            cumple=bool(t_alcance <= float(t_max)) if t_alcance is not None else None,
            referencia=ref, detalle="tiempo y tolerancia del oficio CENACE")]
