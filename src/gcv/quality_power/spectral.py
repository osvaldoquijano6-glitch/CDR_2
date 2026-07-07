"""Cálculo espectral de armónicos desde forma de onda (COMTRADE u oscilografía).

Cuando el analizador no entrega el reporte de armónicos, las magnitudes
individuales (h2..h50, en % de la fundamental) y el THD se calculan por FFT
sobre ventanas de ancho fijo, siguiendo el enfoque de agrupación de
IEC 61000-4-7 (ventana rectangular de N ciclos exactos de la fundamental).

Requisitos sobre la señal:
- fs uniforme y conocida (se rechaza si el muestreo es irregular >1 %);
- fs ≥ 2 × f_nom × orden_max (Nyquist para el orden solicitado);
- duración ≥ una ventana (por defecto 12 ciclos ≈ 200 ms a 60 Hz).

La salida alimenta a CE-Q-04/05 con el mismo formato que las columnas
`harmonic_<kind>_<n>` del analizador.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

F_NOM_HZ = 60.0
CICLOS_VENTANA = 12          # IEC 61000-4-7: 12 ciclos (~200 ms) en 60 Hz
ORDEN_MAX = 50


@dataclass
class EspectroArmonico:
    """Resultado por ventana agregada: magnitudes en % de la fundamental."""

    fs_hz: float
    f_fundamental_hz: float
    n_ventanas: int
    magnitudes_pct: dict[int, float] = field(default_factory=dict)  # orden → % V1
    thd_pct: float | None = None
    advertencias: list[str] = field(default_factory=list)


def _fs_uniforme(t: pd.Series) -> float | None:
    """fs si el muestreo es uniforme (desviación <1 %); None en caso contrario."""
    dt = pd.to_datetime(t).diff().dt.total_seconds().dropna()
    if dt.empty or (dt <= 0).any():
        return None
    if float(dt.std() / dt.mean()) > 0.01:
        return None
    return 1.0 / float(dt.mean())


def espectro_desde_forma_de_onda(
    df: pd.DataFrame,
    columna: str,
    columna_tiempo: str = "timestamp",
    f_nom_hz: float = F_NOM_HZ,
    ciclos_ventana: int = CICLOS_VENTANA,
    orden_max: int = ORDEN_MAX,
) -> EspectroArmonico | None:
    """Espectro armónico promedio (RMS entre ventanas) de una señal muestreada.

    Devuelve None si la señal no permite el cálculo (muestreo irregular,
    fs insuficiente para el orden pedido o duración menor a una ventana);
    el motivo queda en `advertencias` solo cuando hay resultado parcial.
    """
    fs = _fs_uniforme(df[columna_tiempo])
    if fs is None:
        return None

    x = pd.to_numeric(df[columna], errors="coerce").to_numpy(dtype=float)
    if np.isnan(x).any():
        return None

    n_ventana = int(round(fs * ciclos_ventana / f_nom_hz))
    if n_ventana < 8 or len(x) < n_ventana:
        return None

    # orden máximo observable limitado por Nyquist
    orden_nyquist = int(fs / (2.0 * f_nom_hz))
    advertencias = []
    if orden_nyquist < orden_max:
        advertencias.append(
            f"fs={fs:.6g} Hz limita el análisis al armónico {orden_nyquist} "
            f"(se pidió hasta {orden_max})")
        orden_max = orden_nyquist
    if orden_max < 2:
        return None

    n_ventanas = len(x) // n_ventana
    df_hz = fs / n_ventana                       # resolución espectral
    acum: dict[int, list[float]] = {h: [] for h in range(1, orden_max + 1)}
    for v in range(n_ventanas):
        seg = x[v * n_ventana:(v + 1) * n_ventana]
        seg = seg - seg.mean()                   # remueve DC
        mags = np.abs(np.fft.rfft(seg)) * 2.0 / n_ventana
        for h in range(1, orden_max + 1):
            k = h * f_nom_hz / df_hz             # bin de la armónica h
            k0 = int(round(k))
            if k0 >= len(mags):
                break
            # agrupación ±1 bin (subgrupo armónico IEC 61000-4-7)
            grupo = mags[max(k0 - 1, 1):min(k0 + 2, len(mags))]
            acum[h].append(float(np.sqrt(np.sum(grupo ** 2))))

    if not acum.get(1) or max(np.sqrt(np.mean(np.square(acum[1]))), 0.0) <= 0:
        return None
    v1 = float(np.sqrt(np.mean(np.square(acum[1]))))  # RMS de la fundamental

    magnitudes = {
        h: round(float(np.sqrt(np.mean(np.square(vals)))) / v1 * 100.0, 4)
        for h, vals in acum.items() if h >= 2 and vals
    }
    thd = round(float(np.sqrt(sum((m / 100.0) ** 2 for m in magnitudes.values()))) * 100.0, 4)
    return EspectroArmonico(
        fs_hz=fs, f_fundamental_hz=f_nom_hz, n_ventanas=n_ventanas,
        magnitudes_pct=magnitudes, thd_pct=thd, advertencias=advertencias)


def columnas_armonicas_desde_onda(
    df: pd.DataFrame,
    columna: str,
    kind: str,
    columna_tiempo: str = "timestamp",
    **kwargs,
) -> pd.DataFrame | None:
    """DataFrame de una fila con `harmonic_<kind>_<n>` y `thd_<kind>` en %.

    Formato idéntico al reporte de un analizador, para alimentar CE-Q-04/05
    sin cambios en los evaluadores. None si la señal no permite el cálculo.
    """
    esp = espectro_desde_forma_de_onda(df, columna, columna_tiempo, **kwargs)
    if esp is None:
        return None
    fila: dict[str, object] = {"timestamp": pd.to_datetime(df[columna_tiempo].iloc[0])}
    for h, mag in esp.magnitudes_pct.items():
        fila[f"harmonic_{kind}_{h}"] = mag
    fila["thd_voltage" if kind == "voltage" else "thd_current"] = esp.thd_pct
    return pd.DataFrame([fila])
