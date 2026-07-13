"""CE-V-07 — Comportamiento dinámico ante falla (huecos de tensión, Zona A).

Cap. 4 del Manual INTE (CdR 2.0): la central debe permanecer conectada
mientras la trayectoria V(t) esté dentro de la Zona A, delimitada por la
envolvente inferior (curva LVRT) y superior (HVRT). Las curvas dependen de la
tecnología y el tipo: `limites.curvas` = {sincrona_BC, asincrona_BC,
sincrona_D, asincrona_D} con puntos [t_s, v_pu].

Parámetros de ejecución:
    v_base_v:   base de conversión a pu (obligatoria)
    t_falla:    instante de inicio de falla (ISO); si falta, se detecta como la
                primera muestra con V < 0.9 pu
    tecnologia: SINCRONA | ASINCRONA   (para elegir curva)
    tipo_ce:    B | C | D
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef


def _curva(puntos: list[list[float]], t: np.ndarray, superior: bool) -> np.ndarray:
    """Envolvente por interpolación lineal; fuera del último punto se mantiene."""
    pts = sorted((float(a), float(b)) for a, b in puntos)
    xs, ys = zip(*pts)
    if superior:
        # tras el último punto la cota superior queda en el último valor (1.10 pu)
        return np.interp(t, xs, ys, left=ys[0], right=ys[-1])
    return np.interp(t, xs, ys, left=ys[0], right=ys[-1])


@register("CE-V-07")
class HuecosTension(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if "voltage" not in data.df.columns:
            issues.append(InputIssue("Se requiere señal voltage (RMS de secuencia positiva)"))
        if not params.get("v_base_v") or float(params.get("v_base_v", 0)) <= 0:
            issues.append(InputIssue("Parámetro 'v_base_v' requerido para pu"))
        tec = str(params.get("tecnologia", "")).upper()
        tipo = str(params.get("tipo_ce", "")).upper()
        if tec not in ("SINCRONA", "ASINCRONA") or tipo not in ("B", "C", "D"):
            issues.append(InputIssue(
                "Parámetros 'tecnologia' (SINCRONA/ASINCRONA) y 'tipo_ce' (B/C/D) requeridos "
                "para seleccionar la curva de Zona A"))
        return issues

    def _clave_curva(self, params: dict) -> str:
        tec = "sincrona" if str(params["tecnologia"]).upper() == "SINCRONA" else "asincrona"
        tipo = "D" if str(params["tipo_ce"]).upper() == "D" else "BC"
        return f"{tec}_{tipo}"

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        calc = Calculation()
        curvas = self.spec.limites.get("curvas") or {}
        clave = self._clave_curva(wd.params)
        if clave not in curvas:
            calc.extra["sin_curva"] = clave
            return calc

        v_pu = pd.to_numeric(df["voltage"], errors="coerce") / float(wd.params["v_base_v"])
        times = pd.to_datetime(df["timestamp"])
        if wd.params.get("t_falla"):
            t0 = pd.Timestamp(wd.params["t_falla"])
        else:
            bajo = times[v_pu < 0.90]
            if bajo.empty:
                calc.extra["sin_evento"] = True
                return calc
            t0 = bajo.iloc[0]
        t_rel = (times - t0).dt.total_seconds().values

        curva = curvas[clave]
        t_fin = max(p[0] for p in curva["inferior"])
        ventana = (t_rel >= 0) & (t_rel <= t_fin)
        low = _curva(curva["inferior"], t_rel[ventana], superior=False)
        high = _curva(curva["superior"], t_rel[ventana], superior=True)
        v_win = v_pu.values[ventana]
        viol_baja = int(np.sum(v_win < low - 1e-9))
        viol_alta = int(np.sum(v_win > high + 1e-9))

        calc.extra.update({"viol_baja": viol_baja, "viol_alta": viol_alta,
                           "clave": clave, "muestras": int(ventana.sum()), "t0": str(t0)})
        calc.measured = [
            MeasuredValue(nombre="v_min", valor=float(np.nanmin(v_win)) if len(v_win) else None,
                          unidad="pu", detalle=f"ventana Zona A [{0}, {t_fin}] s desde {t0}"),
            MeasuredValue(nombre="muestras_en_ventana", valor=float(ventana.sum()), unidad="muestras"),
            MeasuredValue(nombre="violaciones_envolvente",
                          valor=float(viol_baja + viol_alta), unidad="muestras"),
        ]
        calc.tables.append(Evidence(
            tipo="tabla", titulo=f"Zona A ({clave})",
            data={"curva_inferior": curva["inferior"], "curva_superior": curva["superior"],
                  "violaciones_bajo": viol_baja, "violaciones_sobre": viol_alta}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        if calc.extra.get("sin_curva"):
            return [CriterionCheck(nombre="zona_a", cumple=None, referencia=ref,
                                   detalle=f"Curva '{calc.extra['sin_curva']}' ausente en limites.curvas")]
        if calc.extra.get("sin_evento"):
            return [CriterionCheck(nombre="zona_a", cumple=None, referencia=ref,
                                   detalle="Sin hueco de tensión en el registro (V nunca < 0.90 pu) "
                                           "y sin t_falla declarado")]
        if calc.extra.get("muestras", 0) < 3:
            return [CriterionCheck(nombre="zona_a", cumple=None, referencia=ref,
                                   detalle="Muestras insuficientes dentro de la ventana de la curva")]
        viol = calc.extra["viol_baja"] + calc.extra["viol_alta"]
        return [CriterionCheck(
            nombre="permanencia_zona_a", valor_medido=float(viol), limite=0.0,
            unidad="muestras fuera", comparacion="==", cumple=viol == 0, referencia=ref,
            detalle=f"curva {calc.extra['clave']}; bajo envolvente: {calc.extra['viol_baja']}, "
                    f"sobre envolvente: {calc.extra['viol_alta']}")]
