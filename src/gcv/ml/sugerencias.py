"""Módulo ML de apoyo — sugerencias, nunca dictamen.

Frontera dura del sistema (FASE 1 §8): toda salida de este módulo es una
SUGERENCIA con confianza, que requiere confirmación del usuario cuando altera
datos o mapeos. Ninguna función de aquí participa en evaluate() ni en el
veredicto CUMPLE/NO_CUMPLE.

Implementación base con métodos deterministas (difflib + estadística robusta);
scikit-learn puede sustituir los detectores vía el extra `pip install gcv[ml]`
sin cambiar esta interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

from gcv.models import ChannelMapping, MappingMethod
from gcv.normalization.aliases import ALIASES, match_signal, normalize_header


# ─── Sugerencia de mapeo de columnas por similitud ───────────────────────────
def sugerir_mapeos(
    headers: list[str],
    ya_mapeadas: set[str] | None = None,
    umbral: float = 0.72,
) -> list[ChannelMapping]:
    """Para encabezados que el diccionario determinístico NO reconoció,
    propone la señal canónica más parecida (ratio de similitud difusa contra
    el vocabulario de alias). metodo=AUTO_ML_SUGERIDO y confianza<1: la UI
    debe pedir confirmación antes de usarlas."""
    ya_mapeadas = ya_mapeadas or set()
    sugerencias: list[ChannelMapping] = []
    for header in headers:
        if match_signal(header) is not None:
            continue  # el camino determinístico ya lo resuelve
        norm = normalize_header(header)
        if not norm:
            continue
        mejor_señal, mejor_ratio = None, 0.0
        for señal, alias_list in ALIASES.items():
            if señal in ya_mapeadas:
                continue
            for alias in alias_list:
                ratio = SequenceMatcher(None, norm, alias).ratio()
                if ratio > mejor_ratio:
                    mejor_señal, mejor_ratio = señal, ratio
        if mejor_señal and mejor_ratio >= umbral:
            sugerencias.append(ChannelMapping(
                columna_original=header, senal_canonica=mejor_señal,
                metodo=MappingMethod.AUTO_ML_SUGERIDO,
                confianza=round(mejor_ratio, 3)))
    return sugerencias


# ─── Detección de anomalías y clasificación de eventos ───────────────────────
@dataclass(frozen=True)
class Hallazgo:
    """Sugerencia de anomalía/evento. Informativa: no altera datos ni veredictos."""

    tipo: str  # outlier | plana | perdida_senal | escalon | hueco_tension | desconexion
    señal: str
    inicio: pd.Timestamp
    fin: pd.Timestamp
    detalle: str
    confianza: float  # 0..1


def detectar_anomalias(
    df: pd.DataFrame,
    señales: list[str] | None = None,
    time_col: str = "timestamp",
    z_umbral: float = 6.0,
    plana_min_muestras: int = 30,
) -> list[Hallazgo]:
    """Anomalías por señal: outliers (z robusto MAD), tramos planos (sensor
    congelado) y pérdida de señal (NaN consecutivos)."""
    from gcv.normalization.sampling import flag_outliers_mad
    from gcv.signal_processing.events import detect_signal_loss

    times = pd.to_datetime(df[time_col])
    hallazgos: list[Hallazgo] = []
    for col in señales or [c for c in df.columns if c != time_col]:
        serie = pd.to_numeric(df[col], errors="coerce")

        mask = flag_outliers_mad(serie, threshold=z_umbral)
        if mask.any():
            idx = mask[mask].index
            hallazgos.append(Hallazgo(
                "outlier", col, times.loc[idx[0]], times.loc[idx[-1]],
                f"{int(mask.sum())} muestras con z-robusto > {z_umbral}", 0.8))

        # tramo plano: derivada cero sostenida con la señal no constante globalmente
        if serie.nunique(dropna=True) > 1:
            sin_cambio = serie.diff().fillna(1.0) == 0.0
            grupos = (sin_cambio != sin_cambio.shift()).cumsum()
            for _, g in sin_cambio[sin_cambio].groupby(grupos[sin_cambio]).groups.items():
                if len(g) >= plana_min_muestras:
                    hallazgos.append(Hallazgo(
                        "plana", col, times.loc[g[0]], times.loc[g[-1]],
                        f"{len(g)} muestras idénticas consecutivas (posible sensor congelado "
                        "o pérdida de comunicación)", 0.6))

        for ep in detect_signal_loss(times, serie):
            hallazgos.append(Hallazgo(
                "perdida_senal", col, ep.inicio, ep.fin,
                f"{ep.muestras} muestras NaN consecutivas", 0.9))
    return hallazgos


def clasificar_eventos(
    df: pd.DataFrame,
    time_col: str = "timestamp",
    v_base: float | None = None,
) -> list[Hallazgo]:
    """Clasifica eventos operativos con reglas sobre las señales canónicas:
    escalones de frecuencia, huecos de tensión y desconexiones."""
    from gcv.signal_processing.events import detect_disconnection
    from gcv.signal_processing.steps import detect_steps

    times = pd.to_datetime(df[time_col])
    eventos: list[Hallazgo] = []
    if "frequency" in df.columns:
        for s in detect_steps(times, df["frequency"], min_delta=0.1, window_s=5):
            eventos.append(Hallazgo(
                "escalon", "frequency", s.t, s.t,
                f"escalón de {s.delta:+.3f} Hz ({s.antes:.3f} → {s.despues:.3f})", 0.85))
    if "voltage" in df.columns and v_base:
        v_pu = pd.to_numeric(df["voltage"], errors="coerce") / float(v_base)
        bajo = v_pu < 0.90
        grupos = (bajo != bajo.shift()).cumsum()
        for _, g in bajo[bajo].groupby(grupos[bajo]).groups.items():
            eventos.append(Hallazgo(
                "hueco_tension", "voltage", times.loc[g[0]], times.loc[g[-1]],
                f"V < 0.90 pu durante {len(g)} muestras "
                f"(mínimo {float(v_pu.loc[list(g)].min()):.3f} pu)", 0.85))
    if "active_power" in df.columns:
        p = pd.to_numeric(df["active_power"], errors="coerce")
        umbral = max(float(p.max()) * 0.02, 0.0) if p.notna().any() else 0.0
        for ep in detect_disconnection(times, p, threshold=umbral, min_duration_s=1.0):
            eventos.append(Hallazgo(
                "desconexion", "active_power", ep.inicio, ep.fin,
                f"P bajo el 2 % del máximo durante {ep.duracion_s:.1f} s", 0.7))
    return eventos


def pruebas_incompletas(resultados: list) -> list[str]:
    """Señala pruebas cuyo resultado quedó NO_EVALUABLE por insumos, para
    revisión del plan de medición (no modifica ningún dictamen)."""
    avisos = []
    for r in resultados:
        if r.status.value == "NO_EVALUABLE" and r.warnings:
            avisos.append(f"{r.test_id}: {r.warnings[0]}")
    return avisos
