"""CE-F-01 — Rango de frecuencia.

Primera implementación del motor de reglas (FASE 2: demuestra el contrato;
el resto de pruebas prioritarias llega en FASE 3).

Cálculo: estadísticos de frecuencia y permanencia por banda. Evaluación:
solo si spec.limites trae la tabla de bandas validada, con esta estructura:

    limites:
      bandas:
        - {f_min: <Hz>, f_max: <Hz>, t_min_s: <segundos de permanencia exigida
           dentro de la banda sin desconexión>}   # t_min_s opcional (null =
                                                  # operación continua exigida)
      umbral_desconexion_mw: <P bajo el cual se considera desconexión>  # opcional

La tabla debe provenir del numeral citado (estado_normativo: VALIDADO);
mientras no exista, el motor reporta mediciones y NO_EVALUABLE.
"""

from __future__ import annotations

import pandas as pd

from gcv.evaluation.base import BaseTest, Calculation, WorkingData
from gcv.evaluation.registry import register
from gcv.evaluation.result import CriterionCheck, Evidence, MeasuredValue
from gcv.models import NormRef
from gcv.signal_processing.statistics import time_in_bands


def _permanencia_por_banda(df: pd.DataFrame, bandas: list[dict]) -> list[dict]:
    """Segundos acumulados dentro de cada banda [f_min, f_max]."""
    stats = time_in_bands(
        df["timestamp"], df["frequency"],
        [(b["f_min"], b["f_max"]) for b in bandas])
    return [
        {"f_min": b["f_min"], "f_max": b["f_max"], "t_min_s": b.get("t_min_s"),
         "permanencia_s": s["permanencia_s"], "muestras": s["muestras"]}
        for b, s in zip(bandas, stats)
    ]


@register("CE-F-01")
class RangoFrecuencia(BaseTest):
    def calculate(self, wd: WorkingData) -> Calculation:
        df = wd.dataset.df
        freq = pd.to_numeric(df["frequency"], errors="coerce")
        calc = Calculation(
            measured=[
                MeasuredValue(nombre="f_min", valor=float(freq.min()), unidad="Hz"),
                MeasuredValue(nombre="f_max", valor=float(freq.max()), unidad="Hz"),
                MeasuredValue(nombre="f_media", valor=float(freq.mean()), unidad="Hz"),
                MeasuredValue(nombre="f_p95", valor=float(freq.quantile(0.95)), unidad="Hz"),
                MeasuredValue(nombre="f_p05", valor=float(freq.quantile(0.05)), unidad="Hz"),
            ],
        )
        bandas = self.spec.limites.get("bandas")
        if bandas:
            permanencia = _permanencia_por_banda(df, bandas)
            calc.extra["permanencia"] = permanencia
            calc.tables.append(Evidence(
                tipo="tabla", titulo="Permanencia por banda de frecuencia",
                data={"filas": permanencia}))
        return calc

    def evaluate(self, calc: Calculation, wd: WorkingData) -> list[CriterionCheck]:
        ref = NormRef(documento=self.spec.manual_referencia or "",
                      numeral=self.spec.numeral,
                      version=self.spec.fuente_documental)
        checks: list[CriterionCheck] = []
        permanencia = calc.extra.get("permanencia", [])
        if not permanencia:
            return [CriterionCheck(
                nombre="bandas_de_frecuencia",
                cumple=None,
                referencia=ref,
                detalle="spec.limites.bandas ausente: no hay tabla normativa que comparar")]

        df = wd.dataset.df
        p_col = "active_power" if "active_power" in df.columns else None
        umbral_desc = self.spec.limites.get("umbral_desconexion_mw")

        for fila in permanencia:
            exigido = fila.get("t_min_s")
            nombre = f"banda {fila['f_min']}-{fila['f_max']} Hz"
            if exigido is None:
                # operación continua exigida: verificar no-desconexión dentro de la banda
                cumple = True
                detalle = "Operación continua exigida"
                if p_col is not None and umbral_desc is not None and fila["muestras"] > 0:
                    freq = pd.to_numeric(df["frequency"], errors="coerce")
                    mask = (freq >= fila["f_min"]) & (freq <= fila["f_max"])
                    p_en_banda = pd.to_numeric(df.loc[mask, p_col], errors="coerce")
                    desconexiones = int((p_en_banda < umbral_desc).sum())
                    cumple = desconexiones == 0
                    detalle = f"{desconexiones} muestras bajo umbral de desconexión"
                checks.append(CriterionCheck(
                    nombre=nombre, valor_medido=fila["permanencia_s"],
                    limite=None, unidad="s", comparacion="sin desconexión",
                    cumple=cumple, referencia=ref, detalle=detalle))
            else:
                checks.append(CriterionCheck(
                    nombre=nombre,
                    valor_medido=fila["permanencia_s"],
                    limite=float(exigido),
                    unidad="s",
                    comparacion=">=",
                    cumple=bool(fila["permanencia_s"] >= exigido),
                    referencia=ref,
                    detalle=f"{fila['muestras']} muestras en banda"))
        return checks
