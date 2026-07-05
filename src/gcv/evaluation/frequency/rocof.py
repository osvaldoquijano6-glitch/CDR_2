"""CE-F-02 — Razón de cambio de frecuencia (ROCOF).

Estructura de `limites` cuando el numeral se valide:

    limites:
      rocof_inmunidad_hz_s: <Hz/s que la central debe soportar sin disparo>
      ventana_rocof_ms:     <ancho de ventana de cálculo de df/dt>
      umbral_desconexion_mw: <P bajo la cual se considera desconexión>
      severidad_minima_hz_s: <ROCOF que el evento de prueba debió alcanzar;
                              default = rocof_inmunidad_hz_s>

Criterios: (1) el evento aplicado alcanzó la severidad exigida; (2) la central
permaneció conectada (sin episodios bajo el umbral de desconexión).
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.signal_processing.derivatives import max_abs_rocof, rocof_series
from gcv.signal_processing.events import detect_disconnection

_DEFAULT_WINDOW_MS = 500.0  # usada solo para reporte informativo; la evaluación exige el valor normado


@register("CE-F-02")
class Rocof(BaseTest):
    def _window_s(self, wd: WorkingData) -> float:
        ms = self.spec.limites.get("ventana_rocof_ms") or wd.params.get(
            "ventana_rocof_ms", _DEFAULT_WINDOW_MS)
        return float(ms) / 1000.0

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        window_s = self._window_s(wd)
        peak = max_abs_rocof(df["timestamp"], df["frequency"], window_s)
        serie = rocof_series(df["timestamp"], df["frequency"], window_s)

        calc = Calculation()
        if peak:
            calc.measured += [
                MeasuredValue(nombre="rocof_max_abs", valor=peak["rocof_max_abs_hz_s"],
                              unidad="Hz/s", detalle=f"ventana {window_s*1000:.0f} ms, "
                              f"en {peak['rocof_en']}"),
                MeasuredValue(nombre="rocof_p99_abs",
                              valor=float(serie.abs().quantile(0.99)), unidad="Hz/s"),
            ]
        calc.extra["peak"] = peak
        calc.extra["window_s"] = window_s

        umbral = self.spec.limites.get(
            "umbral_desconexion_mw", wd.params.get("umbral_desconexion_mw"))
        if umbral is not None and "active_power" in df.columns:
            episodios = detect_disconnection(df["timestamp"], df["active_power"], float(umbral))
            calc.extra["desconexiones"] = episodios
            calc.measured.append(MeasuredValue(
                nombre="episodios_desconexion", valor=float(len(episodios)), unidad="eventos"))
            if episodios:
                calc.tables.append(Evidence(
                    tipo="tabla", titulo="Episodios de desconexión detectados",
                    data={"filas": [{"inicio": str(e.inicio), "fin": str(e.fin),
                                     "duracion_s": e.duracion_s} for e in episodios]}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        checks: list[CriterionCheck] = []
        inmunidad = self.spec.limites.get("rocof_inmunidad_hz_s")
        peak = calc.extra.get("peak")

        if inmunidad is None:
            return [CriterionCheck(nombre="rocof", cumple=None, referencia=ref,
                                   detalle="limites.rocof_inmunidad_hz_s ausente")]
        if peak is None:
            return [CriterionCheck(nombre="rocof", cumple=None, referencia=ref,
                                   detalle="No fue posible calcular df/dt (datos insuficientes)")]

        severidad_req = float(self.spec.limites.get("severidad_minima_hz_s", inmunidad))
        checks.append(CriterionCheck(
            nombre="severidad_del_evento",
            valor_medido=peak["rocof_max_abs_hz_s"], limite=severidad_req,
            unidad="Hz/s", comparacion=">=",
            cumple=bool(peak["rocof_max_abs_hz_s"] >= severidad_req),
            referencia=ref,
            detalle="El evento de prueba debe alcanzar el ROCOF de inmunidad exigido"))

        if "desconexiones" in calc.extra:
            episodios = calc.extra["desconexiones"]
            checks.append(CriterionCheck(
                nombre="continuidad_operativa",
                valor_medido=float(len(episodios)), limite=0.0, unidad="eventos",
                comparacion="==", cumple=len(episodios) == 0, referencia=ref,
                detalle="Sin desconexión/disparo durante el evento ROCOF"))
        else:
            checks.append(CriterionCheck(
                nombre="continuidad_operativa", cumple=None, referencia=ref,
                detalle="Sin umbral_desconexion_mw o sin señal de potencia: continuidad no verificable"))
        return checks
