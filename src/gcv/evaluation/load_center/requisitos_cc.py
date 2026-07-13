"""CC-01, CC-02 y CC-08 — Requerimientos medibles del Manual CONE.

CC-01 Tensión (2.1): permanente 95–105 % Vnom; temporal 90–110 % hasta 20 min.
CC-02 Frecuencia (2.2): permanente 59–61 Hz; temporal 58–62.5 Hz hasta 30 min.
CC-08 Calidad (2.8): flicker Pst<1.0/Plt<0.8 (P95 semanal), desbalance de
tensión ≤2 % (P95) y de corriente ≤15 % (promedio). El TDD se evalúa con
CE-Q-05 (mismas Tablas 2.8) usando v_kv + icc_il.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, InputIssue, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, MeasuredValue
from gcv.models import NormRef
from gcv.quality_power.harmonics import series_percentile


def _episodios_max_min(times: pd.Series, mask: pd.Series) -> float:
    """Duración (min) del episodio más largo donde mask es True."""
    if not mask.any():
        return 0.0
    grupos = (mask != mask.shift()).cumsum()
    peor = 0.0
    for _, idx in mask[mask].groupby(grupos[mask]).groups.items():
        dur = (times.loc[idx[-1]] - times.loc[idx[0]]).total_seconds() / 60.0
        peor = max(peor, dur)
    return peor


@register("CC-01")
class TensionCentroCarga(BaseTest):
    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        if "voltage" not in data.df.columns:
            issues.append(InputIssue("Señal voltage requerida"))
        if not params.get("v_nominal_v"):
            issues.append(InputIssue("Parámetro 'v_nominal_v' requerido"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        v_pct = (pd.to_numeric(df["voltage"], errors="coerce")
                 / float(wd.params["v_nominal_v"]) * 100.0)
        times = pd.to_datetime(df["timestamp"])
        lim = self.spec.limites
        perm, temp = lim["permanente_pct"], lim["temporal_pct"]
        fuera_temporal = int(((v_pct < temp[0]) | (v_pct > temp[1])).sum())
        fuera_perm = (v_pct < perm[0]) | (v_pct > perm[1])
        peor_episodio = _episodios_max_min(times, fuera_perm & v_pct.notna())
        calc = Calculation(extra={"fuera_temporal": fuera_temporal,
                                  "peor_episodio_min": peor_episodio})
        calc.measured = [
            MeasuredValue(nombre="v_min", valor=float(v_pct.min()), unidad="% Vnom"),
            MeasuredValue(nombre="v_max", valor=float(v_pct.max()), unidad="% Vnom"),
            MeasuredValue(nombre="episodio_mas_largo_fuera_de_permanente",
                          valor=round(peor_episodio, 2), unidad="min"),
        ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        return [
            CriterionCheck(
                nombre="dentro_de_rango_temporal",
                valor_medido=float(calc.extra["fuera_temporal"]), limite=0.0,
                unidad="muestras", comparacion="==",
                cumple=calc.extra["fuera_temporal"] == 0, referencia=ref,
                detalle=f"rango {lim['temporal_pct'][0]}–{lim['temporal_pct'][1]} % Vnom"),
            CriterionCheck(
                nombre="excursiones_temporales_acotadas",
                valor_medido=round(calc.extra["peor_episodio_min"], 2),
                limite=float(lim["temporal_max_min"]), unidad="min", comparacion="<=",
                cumple=bool(calc.extra["peor_episodio_min"] <= float(lim["temporal_max_min"])),
                referencia=ref,
                detalle=f"episodios fuera de {lim['permanente_pct'][0]}–"
                        f"{lim['permanente_pct'][1]} % Vnom"),
        ]


@register("CC-02")
class FrecuenciaCentroCarga(BaseTest):
    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        f = pd.to_numeric(df["frequency"], errors="coerce")
        times = pd.to_datetime(df["timestamp"])
        bandas = self.spec.limites["bandas"]
        permanente = next(b for b in bandas if b.get("t_capacidad_normativa_s") is None)
        temporal = next(b for b in bandas if b.get("t_capacidad_normativa_s") is not None)
        fuera_temporal = int(((f < temporal["f_min"]) | (f > temporal["f_max"])).sum())
        fuera_perm = ((f < permanente["f_min"]) | (f > permanente["f_max"])) & f.notna()
        peor = _episodios_max_min(times, fuera_perm)
        calc = Calculation(extra={"fuera_temporal": fuera_temporal, "peor_min": peor,
                                  "temporal": temporal, "permanente": permanente})
        calc.measured = [
            MeasuredValue(nombre="f_min", valor=float(f.min()), unidad="Hz"),
            MeasuredValue(nombre="f_max", valor=float(f.max()), unidad="Hz"),
            MeasuredValue(nombre="episodio_mas_largo_fuera_de_permanente",
                          valor=round(peor, 2), unidad="min"),
        ]
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        t, p = calc.extra["temporal"], calc.extra["permanente"]
        max_min = float(t["t_capacidad_normativa_s"]) / 60.0
        return [
            CriterionCheck(
                nombre="dentro_de_rango_temporal",
                valor_medido=float(calc.extra["fuera_temporal"]), limite=0.0,
                unidad="muestras", comparacion="==",
                cumple=calc.extra["fuera_temporal"] == 0, referencia=ref,
                detalle=f"rango {t['f_min']}–{t['f_max']} Hz"),
            CriterionCheck(
                nombre="excursiones_temporales_acotadas",
                valor_medido=round(calc.extra["peor_min"], 2), limite=max_min,
                unidad="min", comparacion="<=",
                cumple=bool(calc.extra["peor_min"] <= max_min), referencia=ref,
                detalle=f"episodios fuera de {p['f_min']}–{p['f_max']} Hz"),
        ]


@register("CC-08")
class CalidadCentroCarga(BaseTest):
    """Indicadores de calidad medibles con señales del analizador Clase A."""

    def validate_inputs(self, data, params) -> list[InputIssue]:
        issues = [i for i in super().validate_inputs(data, params)
                  if "Señales requeridas" not in i.mensaje]
        disponibles = {"pst", "plt", "unbalance"} & set(data.df.columns)
        if not disponibles:
            issues.append(InputIssue(
                "Se requiere al menos una señal de calidad: pst, plt o unbalance"))
        return issues

    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        pct = float(self.spec.limites.get("percentil", 95))
        calc = Calculation(extra={"percentil": pct})
        for señal in ("pst", "plt", "unbalance"):
            if señal in df.columns:
                valor = series_percentile(df[señal], pct)
                calc.extra[señal] = valor
                if valor is not None:
                    calc.measured.append(MeasuredValue(
                        nombre=f"{señal}_p{pct:g}", valor=valor))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "", numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        lim = self.spec.limites
        pct = calc.extra["percentil"]
        pares = (("pst", lim.get("pst_max")), ("plt", lim.get("plt_max")),
                 ("unbalance", lim.get("desbalance_tension_pct")))
        checks = []
        for señal, limite in pares:
            if limite is None:
                continue
            medido = calc.extra.get(señal)
            checks.append(CriterionCheck(
                nombre=f"{señal}_p{pct:g}", valor_medido=medido, limite=float(limite),
                comparacion="<=" if señal != "pst" else "<",
                cumple=(bool(medido < float(limite)) if señal in ("pst", "plt")
                        else bool(medido <= float(limite))) if medido is not None else None,
                referencia=ref,
                detalle=None if medido is not None else f"Sin señal {señal} en la medición"))
        checks.append(CriterionCheck(
            nombre="tdd_corriente", cumple=None, referencia=ref,
            detalle="El TDD se evalúa con la prueba CE-Q-05 (Tablas 2.8) con v_kv e icc_il"))
        return checks
