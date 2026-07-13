"""
core/droop.py — Modelo droop primario piecewise para pruebas P3, P8, P9.

Curvas teoricas y evaluacion de error para pruebas de frecuencia.
Pendiente referida a P_ref (criterio CENACE).
P_op se infiere de las mediciones dentro de la banda muerta (~60 Hz).
"""

from __future__ import annotations

import pandas as pd


PRUEBAS = {
    3: {
        "nombre": "Respuesta a Alta Frecuencia",
        "f_min": 59.97,
        "f_max": 62.70,
        "S_default": 0.08,
        "S_opciones": [0.03, 0.05, 0.08],
        "zona_f_inicio": 60.20,
    },
    8: {
        "nombre": "Respuesta a Baja Frecuencia",
        "f_min": 59.49,
        "f_max": 60.03,
        "S_default": 0.03,
        "S_opciones": [0.03, 0.05, 0.08],
        "zona_f_inicio": 59.80,
    },
    9: {
        "nombre": "Control Primario de Frecuencia",
        "f_min": 59.49,
        "f_max": 62.70,
        "S_default": 0.03,
        "S_opciones": [0.03, 0.05, 0.08],
        "zona_f_inicio": None,
    },
}


def _detectar_segmentos_estables(
    freq: pd.Series,
    umbral_std: float = 0.02,
    tamano_min: int = 5,
) -> list[tuple[int, int]]:
    """Detecta segmentos consecutivos donde la frecuencia es estable.

    Retorna lista de (inicio, fin) indices en el array original.
    """
    segmentos = []
    inicio = 0
    valores = freq.values
    n = len(valores)

    for i in range(tamano_min, n + 1):
        segmento = valores[max(0, i - tamano_min):i]
        validos = segmento[~pd.isna(segmento)]
        if len(validos) >= tamano_min and float(validos.std()) > umbral_std:
            # Frecuencia se volvio inestable, cerrar segmento anterior
            if inicio < i - tamano_min:
                fin = i - tamano_min
                if fin - inicio >= tamano_min:
                    segmentos.append((inicio, fin))
            inicio = i

    # Cerrar ultimo segmento
    if inicio < n - tamano_min:
        segmentos.append((inicio, n))

    return segmentos


def derivar_p_op(
    df: pd.DataFrame,
    col_freq: str = "frequency",
    col_pot: str = "active_power",
    col_time: str = "time",
    f_nom: float = 60.0,
    db: float = 0.030,
) -> dict | None:
    """Estima P_op desde el estado estable previo al escalon de frecuencia.

    Estrategia en cascada:
    1. Primer segmento estable (std freq < 0.02 Hz) dentro de los primeros 30% del registro
    2. Cualquier punto con frecuencia en 59.95-60.05 Hz en la primera mitad
    3. Fallback: mediana de los primeros 100 puntos
    """
    if df.empty:
        return None

    df_sorted = df.sort_values(col_time).reset_index(drop=True)
    freq_vals = pd.to_numeric(df_sorted[col_freq], errors="coerce")
    pot_vals = pd.to_numeric(df_sorted[col_pot], errors="coerce")

    n_total = len(df_sorted)
    limite_busqueda = max(50, int(n_total * 0.30))
    freq_busqueda = freq_vals.head(limite_busqueda)

    # Metodo 1: Detectar segmentos estables y usar el primero cercano a f_nom
    segmentos = _detectar_segmentos_estables(freq_busqueda, umbral_std=0.02, tamano_min=5)

    for inicio, fin in segmentos:
        segmento_freq = freq_vals.iloc[inicio:fin]
        media_freq = float(segmento_freq.dropna().mean())
        if abs(media_freq - f_nom) < 0.15:  # dentro de 0.15 Hz de 60 Hz
            segmento_pot = pot_vals.iloc[inicio:fin].dropna()
            if len(segmento_pot) >= 3:
                return {
                    "p_op": float(segmento_pot.median()),
                    "n_muestras": len(segmento_pot),
                    "metodo": "segmento_estable_pre_escalon",
                }

    # Metodo 2: Todos los puntos en primera mitad con frecuencia ~60 Hz
    limite_mitad = n_total // 2
    primera_mitad = df_sorted.head(limite_mitad)
    freq_mitad = freq_vals.head(limite_mitad)
    pot_mitad = pot_vals.head(limite_mitad)

    cercanos_60 = primera_mitad[
        (freq_mitad >= 59.95) & (freq_mitad <= 60.05)
    ]
    if len(cercanos_60) >= 5:
        pot_cercanos = pot_vals.loc[cercanos_60.index].dropna()
        if len(pot_cercanos) >= 5:
            return {
                "p_op": float(pot_cercanos.median()),
                "n_muestras": len(cercanos_60),
                "metodo": "mediana_cercanos_60hz_mitad",
            }

    # Metodo 3: Mediana de los primeros 100 puntos validos
    primeros_validos = pot_vals.head(100).dropna()
    if len(primeros_validos) > 0:
        return {
            "p_op": float(primeros_validos.median()),
            "n_muestras": len(primeros_validos),
            "metodo": "mediana_primeros_100",
        }

    return None


def potencia_teorica(
    f: float,
    S: float,
    p_op: float,
    p_ref: float,
    f_nom: float = 60.0,
    db: float = 0.030,
    f_sat_high: float = 60.20,
) -> float:
    """Potencia activa teorica (MW) para una frecuencia f (Hz).

    Modelo piecewise con droop referido a frecuencia nominal:
    - f < f_nom-db  => zona baja frecuencia, potencia incrementa
    - f_nom-db <= f <= f_nom+db  => banda muerta, potencia = P_op
    - f > f_nom+db  => zona alta frecuencia, potencia decrece

    Formula: P = P_op - (P_ref/S) * (f - f_nom)/f_nom
    """
    f_db_low = f_nom - db
    f_db_high = f_nom + db

    if f < f_db_low:
        P = p_op + (p_ref / S) * (f_nom - f) / f_nom
        return min(P, p_ref)
    if f <= f_db_high:
        return p_op
    # f > f_db_high: droop referido a f_nom (60.00), no al borde de banda muerta
    P = p_op + (p_ref / S) * (f_nom - f) / f_nom
    return max(P, 0.0)


def generar_curva_teorica(
    df: pd.DataFrame,
    S: float,
    p_op: float,
    p_ref: float,
    col_freq: str = "frequency",
) -> pd.Series:
    """Genera serie de potencia teorica para cada punto de frecuencia."""
    return pd.Series(
        [
            potencia_teorica(float(f), S, p_op, p_ref)
            for f in df[col_freq]
        ],
        index=df.index,
    )


def evaluar_error(
    f_medida: float,
    p_medida: float,
    S: float,
    p_op: float,
    p_ref: float,
) -> dict:
    """Compara medicion contra teorica.

    Semafaro:
    - verde: error <= 2%
    - amarillo: error <= 5%
    - rojo: error > 5%
    """
    p_teo = potencia_teorica(f_medida, S, p_op, p_ref)
    err_abs = p_medida - p_teo
    err_rel = err_abs / p_teo if p_teo != 0 else None

    if err_rel is None:
        semaforo = "indefinido"
    elif abs(err_rel) <= 0.02:
        semaforo = "verde"
    elif abs(err_rel) <= 0.05:
        semaforo = "amarillo"
    else:
        semaforo = "rojo"

    return {
        "p_teorica": round(p_teo, 4),
        "error_mw": round(err_abs, 4),
        "error_pct": round(err_rel * 100, 2) if err_rel is not None else None,
        "semaforo": semaforo,
    }


def construir_tabla_evaluacion(
    df: pd.DataFrame,
    S: float,
    p_op: float,
    p_ref: float,
    col_freq: str = "frequency",
    col_pot: str = "active_power",
) -> pd.DataFrame:
    """Construye tabla completa de evaluacion punto a punto."""
    rows = []
    for _, row in df.iterrows():
        f = float(row[col_freq])
        p = float(row[col_pot])
        ev = evaluar_error(f, p, S, p_op, p_ref)
        rows.append(
            {
                "frecuencia_hz": round(f, 4),
                "potencia_mw": round(p, 4),
                "potencia_teorica_mw": ev["p_teorica"],
                "error_mw": ev["error_mw"],
                "error_pct": ev["error_pct"],
                "semaforo": ev["semaforo"],
            }
        )
    return pd.DataFrame(rows)


def resumir_semaforo(tabla: pd.DataFrame) -> dict:
    """Resume porcentajes de semaforo."""
    total = len(tabla)
    if total == 0:
        return {"verde": 0.0, "amarillo": 0.0, "rojo": 0.0, "indefinido": 0.0}

    counts = tabla["semaforo"].value_counts()
    return {
        "verde": round(counts.get("verde", 0) / total * 100, 1),
        "amarillo": round(counts.get("amarillo", 0) / total * 100, 1),
        "rojo": round(counts.get("rojo", 0) / total * 100, 1),
        "indefinido": round(counts.get("indefinido", 0) / total * 100, 1),
    }
