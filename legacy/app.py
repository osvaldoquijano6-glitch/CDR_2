"""
Aplicación Profesional de Análisis de Pruebas — Código de Red / Anexo 5
Herramienta para análisis normativo de Centrales Eléctricas.
"""

from __future__ import annotations

import io
import html
import json
import os
import re
import sys
import tempfile
import traceback
import unicodedata
import zipfile
from types import SimpleNamespace
from pathlib import Path

# ─── Bootstrap de arranque ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
RUNNING_FROM_STREAMLIT = any(
    name == "streamlit" or name.startswith("streamlit.") for name in sys.modules
)

if __name__ == "__main__" and not RUNNING_FROM_STREAMLIT:
    launcher = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    os.execv(
        str(launcher),
        [
            str(launcher),
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "app.py"),
            *sys.argv[1:],
        ],
    )

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ─── Rutas ─────────────────────────────────────────────────────────────────────
os.environ.setdefault("MPLCONFIGDIR", str((PROJECT_ROOT / ".mplconfig").resolve()))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.registry import REGISTRY
from tests.simple import run_p25, run_p28_summary, run_simple
from tests.multi import run_multi
from tests.multi_zones import run_zones_multi
from core.depur import load_sources, run_cut_job, CutJob
from core.export import write_xlsx
from core.io import load_table, detect_time_column, _parse_datetime_series
from core.naming import artifact_filename, dataframe_date_label, project_token, unique_path

PROJECTS_DIR = PROJECT_ROOT / "projects"
COMPANY_LOGO_PATH = PROJECT_ROOT / "LOGO.png"

GRAPH_COLOR_PRESETS = {
    "Operativo": {
        "freq_color": "#0f766e",
        "power_color": "#2563eb",
        "description": "Lectura tecnica para operacion diaria y validacion rapida.",
    },
    "Contraste": {
        "freq_color": "#b45309",
        "power_color": "#0891b2",
        "description": "Mayor separacion visual para eventos, rampas y escalones.",
    },
    "Reporte": {
        "freq_color": "#047857",
        "power_color": "#4f46e5",
        "description": "Acabado sobrio para evidencia, informe y presentacion.",
    },
}

VISUAL_COLOR_PALETTES = {
    "Índigo Laboratorio": {
        "bg": "#F6F7FB",
        "surface": "#FFFFFF",
        "surface_soft": "#EEF1FA",
        "surface_tint": "#EDEBFF",
        "ink": "#1E1B4B",
        "muted": "#64748B",
        "line": "#DADDF0",
        "line_strong": "#C1C4E4",
        "primary": "#312E81",
        "primary_strong": "#1E1B4B",
        "secondary": "#0891B2",
        "warning": "#B45309",
        "danger": "#DC2626",
        "ok": "#0F766E",
        "sidebar": "#1E1B4B",
        "sidebar_end": "#11103A",
    },
    "Laboratorio teal": {
        "bg": "#f4f7fb",
        "surface": "#ffffff",
        "surface_soft": "#eef4f8",
        "surface_tint": "#e6f3f1",
        "ink": "#102033",
        "muted": "#64748b",
        "line": "#d7e2ea",
        "line_strong": "#b9c9d6",
        "primary": "#0f766e",
        "primary_strong": "#115e59",
        "secondary": "#2563eb",
        "warning": "#b45309",
        "danger": "#dc2626",
        "ok": "#047857",
        "sidebar": "#102033",
        "sidebar_end": "#0b1826",
    },
    "Azul ejecutivo": {
        "bg": "#f5f8fc",
        "surface": "#ffffff",
        "surface_soft": "#edf4fb",
        "surface_tint": "#e7f0ff",
        "ink": "#10223f",
        "muted": "#5e7089",
        "line": "#d5e0ec",
        "line_strong": "#b8c9da",
        "primary": "#1d4ed8",
        "primary_strong": "#1e3a8a",
        "secondary": "#0f766e",
        "warning": "#a16207",
        "danger": "#b91c1c",
        "ok": "#047857",
        "sidebar": "#111f38",
        "sidebar_end": "#091426",
    },
    "Grafito cian": {
        "bg": "#f3f6f8",
        "surface": "#ffffff",
        "surface_soft": "#edf2f5",
        "surface_tint": "#e4f7fb",
        "ink": "#17212b",
        "muted": "#617180",
        "line": "#d4dee6",
        "line_strong": "#b8c7d2",
        "primary": "#0891b2",
        "primary_strong": "#155e75",
        "secondary": "#334155",
        "warning": "#b45309",
        "danger": "#dc2626",
        "ok": "#047857",
        "sidebar": "#17212b",
        "sidebar_end": "#0d141b",
    },
    "Verde regulatorio": {
        "bg": "#f5f8f4",
        "surface": "#ffffff",
        "surface_soft": "#eef5ec",
        "surface_tint": "#e7f4df",
        "ink": "#17251c",
        "muted": "#607064",
        "line": "#d8e4d4",
        "line_strong": "#bdd0b8",
        "primary": "#2f6f3e",
        "primary_strong": "#1f4d2b",
        "secondary": "#2563eb",
        "warning": "#a16207",
        "danger": "#b91c1c",
        "ok": "#047857",
        "sidebar": "#14251a",
        "sidebar_end": "#09150d",
    },
}

STATUS_META = {
    "Completada": {
        "slug": "completada",
        "icon": "",
        "color": "#4ade80",
        "soft": "rgba(74,222,128,0.12)",
        "border": "rgba(74,222,128,0.25)",
    },
    "En progreso": {
        "slug": "en-progreso",
        "icon": "",
        "color": "#fbbf24",
        "soft": "rgba(251,191,36,0.12)",
        "border": "rgba(251,191,36,0.25)",
    },
    "Pendiente": {
        "slug": "pendiente",
        "icon": "",
        "color": "#94a3b8",
        "soft": "rgba(51,65,85,0.50)",
        "border": "rgba(51,65,85,0.60)",
    },
    "Pendiente a documentación": {
        "slug": "doc",
        "icon": "",
        "color": "#38bdf8",
        "soft": "rgba(56,189,248,0.12)",
        "border": "rgba(56,189,248,0.30)",
    },
}

VERDICT_META = {
    "": {"slug": "none", "label": "—", "color": "#64748b"},
    "Cumple": {"slug": "cumple", "label": "Cumple", "color": "#4ade80"},
    "No cumple": {
        "slug": "nocumple",
        "label": "No cumple",
        "color": "#f87171",
    },
    "Pendiente a revisión": {
        "slug": "revision",
        "label": "Pend. revisión",
        "color": "#fbbf24",
    },
    "Pendiente a documentación": {
        "slug": "doc",
        "label": "Pend. docs",
        "color": "#38bdf8",
    },
    "Repetir prueba": {
        "slug": "repeat",
        "label": "Repetir",
        "color": "#fb923c",
    },
}

CENTRAL_CATALOGS = {
    "asincrona": {
        "nombre": "Pruebas Centrales Electricas Asincronas",
        "tests": [
            {
                "id": 1,
                "nombre": "Rango de frecuencia",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P1",
            },
            {
                "id": 2,
                "nombre": "Razon de cambio 2.0 Hz/s",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P2",
            },
            {
                "id": 3,
                "nombre": "Respuesta a alta frecuencia",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P3",
            },
            {
                "id": 4,
                "nombre": "Potencia activa constante en el rango de respuesta a alta frecuencia",
                "tipos": ["A", "B"],
                "implemented_code": "P4",
            },
            {
                "id": 5,
                "nombre": "Limitacion total de potencia activa",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 6,
                "nombre": "Reconexion automatica",
                "tipos": ["A", "B"],
                "implemented_code": "P6",
            },
            {
                "id": 7,
                "nombre": "Limitacion parcial de potencia activa",
                "tipos": ["B"],
            },
            {
                "id": 8,
                "nombre": "Respuesta a baja frecuencia",
                "tipos": ["B", "C", "D"],
                "implemented_code": "P8",
            },
            {
                "id": 9,
                "nombre": "Control primario de frecuencia",
                "tipos": ["B", "C", "D"],
                "implemented_code": "P9",
            },
            {
                "id": 10,
                "nombre": "Control secundario de frecuencia",
                "tipos": ["C", "D"],
            },
            {
                "id": 11,
                "nombre": "Rango de tension en el punto de interconexion",
                "tipos": ["A"],
                "implemented_code": "P12",
            },
            {
                "id": 12,
                "nombre": "Rango de tension en el punto de interconexion",
                "tipos": ["B", "C", "D"],
                "implemented_code": "P12",
            },
            {
                "id": 13,
                "nombre": "Capacidad de potencia reactiva",
                "tipos": ["B"],
                "implemented_code": "P13",
            },
            {
                "id": 14,
                "nombre": "Capacidad de potencia reactiva a potencia maxima",
                "tipos": ["C", "D"],
            },
            {
                "id": 15,
                "nombre": "Capacidad de potencia reactiva debajo de la potencia maxima",
                "tipos": ["C", "D"],
            },
            {"id": 16, "nombre": "Control de voltaje", "tipos": ["C", "D"]},
            {"id": 17, "nombre": "Control de potencia reactiva", "tipos": ["C", "D"]},
            {"id": 18, "nombre": "Control de F.P.", "tipos": ["C", "D"]},
            {
                "id": 19,
                "nombre": "Amortiguamiento de oscilaciones de potencia",
                "tipos": ["C", "D"],
            },
            {
                "id": 20,
                "nombre": "Control de tension en condiciones dinamicas o de falla",
                "tipos": ["B", "C", "D"],
            },
            {"id": 21, "nombre": "Runback/Rundown", "tipos": ["C", "D"]},
            {"id": 22, "nombre": "Rampa de Variacion de Carga", "tipos": ["C", "D"]},
            {"id": 23, "nombre": "Rechazo de Carga Parcial", "tipos": ["C", "D"]},
            {
                "id": 24,
                "nombre": "Modelos de simulacion",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 25,
                "nombre": "Capacidad instalada neta",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P25",
            },
            {
                "id": 26,
                "nombre": "Requerimientos de Calidad de la Potencia",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P26",
            },
            {
                "id": 27,
                "nombre": "Comportamiento de modo de control de tension - potencia reactiva",
                "tipos": ["B", "C", "D"],
            },
            {
                "id": 28,
                "nombre": "Control de frecuencia",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P28",
            },
            {
                "id": 31,
                "nombre": "Alta frecuencia con zona esperada",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P3Z",
            },
            {
                "id": 81,
                "nombre": "Baja frecuencia con zona esperada",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P8Z",
            },
            {
                "id": 91,
                "nombre": "Control primario con zona esperada",
                "tipos": ["A", "B", "C", "D"],
                "implemented_code": "P9Z",
            },
        ],
    },
    "sincrona": {
        "nombre": "Pruebas de Centrales El\u00e9ctricas S\u00edncronas",
        "tests": [
            # --- unidad / control_tension_avr ---
            {
                "id": 1,  "nombre": "Rango Operativo de Tensión",                              "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_only",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Voltaje del generador Vg / tensión en terminales",
                    "y2": "Consigna de voltaje Vgsp o excitación Vf/If",
                    "senales": ["Vg", "Vgsp", "Vf", "If"],
                    "criterio_visual": "Mostrar barrido de 90% a 110% del voltaje nominal y regreso a 100%.",
                },
            },
            {
                "id": 2,  "nombre": "Escalón de Tensión / Respuesta transitoria",              "tipos": ["B","C","D"],      "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Voltaje del generador Vg",
                    "y2": "Consigna de voltaje Vgsp / respuesta de excitación",
                    "senales": ["Vg", "Vgsp", "Vf", "If"],
                    "criterio_visual": "Marcar inicio del escalón, regreso, tiempo de respuesta, tiempo de estabilización y sobrepaso.",
                },
            },
            {
                "id": 3,  "nombre": "Limitador V/Hz",                                          "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_only",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia o velocidad equivalente",
                    "y2": "Voltaje del generador / relación V/Hz",
                    "senales": ["f", "Vg", "V_Hz"],
                    "criterio_visual": "Evidenciar que la relación V/Hz permanece dentro del rango esperado del limitador.",
                },
            },
            {
                "id": 4,  "nombre": "Secuencia Excitación–Desexcitación",                      "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "secuencia",
                    "x": "Tiempo",
                    "y1": "Estado de excitación",
                    "y2": "Voltaje del generador / voltaje de campo",
                    "senales": ["estado_excitación", "Vg", "Vf", "If"],
                    "criterio_visual": "Mostrar tiempos de excitación y desexcitación automática o por paro de emergencia.",
                },
            },
            {
                "id": 5,  "nombre": "Seguidor automático entre canales y UCE's",              "tipos": ["A","B"],          "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": False,
                    "grafica": "tabla",
                    "senales": ["canal_activo", "canal_respaldo", "error_transferencia"],
                    "criterio_visual": "Normalmente se documenta con tabla de error de seguimiento; graficar solo si existen señales de ambos canales.",
                },
            },
            {
                "id": 6,  "nombre": "PSS",                                                     "tipos": ["C","D"],          "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "freq_power",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa / oscilación",
                    "y2": "Señal PSS o variable de excitación",
                    "senales": ["P", "PSS", "Vf", "If"],
                    "criterio_visual": "Comparar amortiguamiento con PSS fuera de servicio y en servicio.",
                },
            },
            {
                "id": 7,  "nombre": "Limitador de mínima excitación (MEL)",                    "tipos": ["C","D"],          "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "curva_pq_o_doble_eje",
                    "x": "Tiempo o P",
                    "y1": "Potencia reactiva Q",
                    "y2": "Voltaje del generador / corriente de campo",
                    "senales": ["P", "Q", "Vg", "If"],
                    "criterio_visual": "Evidenciar actuación del limitador de mínima excitación respecto al límite inferior de la curva de capabilidad.",
                },
            },
            {
                "id": 8,  "nombre": "Limitador de máxima excitación (OEL)",                    "tipos": ["C","D"],          "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "curva_pq_o_doble_eje",
                    "x": "Tiempo o P",
                    "y1": "Potencia reactiva Q",
                    "y2": "Corriente de campo If",
                    "senales": ["P", "Q", "If", "Vf"],
                    "criterio_visual": "Evidenciar actuación del limitador de máxima excitación respecto al límite superior de la curva de capabilidad.",
                },
            },
            {
                "id": 9,  "nombre": "Compensador de MVAr",                                     "tipos": ["B","C","D"],      "nivel": "unidad", "familia": "control_tension_avr",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia reactiva Q",
                    "y2": "Voltaje en bus / consigna del compensador",
                    "senales": ["Q", "Vbus", "setpoint_CR"],
                    "criterio_visual": "Mostrar respuesta del compensador ante ajustes 0%, ±4%, ±8% y ±12% si existen datos.",
                },
            },

            # --- unidad / control_velocidad_gobernador ---
            {
                "id": 10, "nombre": "Apertura / cierre de elementos finales de control",       "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": False,
                    "grafica": "tabla_secuencia",
                    "senales": ["orden_apertura", "orden_cierre", "posición", "tiempo"],
                    "criterio_visual": "Puede documentarse en tabla de carrera y tiempos; graficar solo si hay señal cuantitativa de apertura/cierre.",
                },
            },
            {
                "id": 11, "nombre": "Secuencia de arranque",                                   "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "secuencia",
                    "x": "Tiempo",
                    "y1": "Estados de arranque",
                    "y2": "Velocidad / frecuencia / tensión",
                    "senales": ["estado_arranque", "rpm", "f", "Vg"],
                    "criterio_visual": "Mostrar secuencia de arranque, tiempos y transición hasta tensión y velocidad nominales.",
                },
            },
            {
                "id": 12, "nombre": "Variador de velocidad (65F)",                             "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "speed_load",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Velocidad o frecuencia",
                    "y2": "Consigna de velocidad",
                    "senales": ["rpm", "f", "speed_setpoint"],
                    "criterio_visual": "Evidenciar control de velocidad dentro del rango 57 Hz a 63 Hz.",
                },
            },
            {
                "id": 13, "nombre": "Escalones de velocidad",                                  "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "speed_load",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Velocidad o frecuencia",
                    "y2": "Consigna de velocidad",
                    "senales": ["rpm", "f", "speed_setpoint"],
                    "criterio_visual": "Marcar inicio del escalón, sobrepaso y tiempo de estabilización.",
                },
            },
            {
                "id": 14, "nombre": "Protección por sobrevelocidad",                           "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "speed_load",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Velocidad del rotor rpm o % velocidad nominal",
                    "y2": "Estado de protección / disparo",
                    "senales": ["rpm", "speed_percent", "trip_overspeed"],
                    "criterio_visual": "Evidenciar actuación de protección por sobrevelocidad alrededor de 110% a 112%.",
                },
            },
            {
                "id": 15, "nombre": "Variador de carga (65P)",                                 "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Consigna de carga / posición de carga",
                    "senales": ["P", "load_setpoint", "posición_carga"],
                    "criterio_visual": "Mostrar barrido de potencia mínima a máxima y regreso.",
                },
            },
            {
                "id": 16, "nombre": "Limitador de carga (65L)",                                "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Límite de carga / consigna",
                    "senales": ["P", "load_limit", "load_setpoint"],
                    "criterio_visual": "Evidenciar que el limitador restringe la potencia dentro del valor configurado.",
                },
            },
            {
                "id": 17, "nombre": "Estatismo",                                               "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "freq_power_ref",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia o velocidad",
                    "y2": "Potencia activa P",
                    "senales": ["f", "rpm", "P"],
                    "criterio_visual": "Mostrar pendiente frecuencia-potencia para estatismo 3%, 5% y 8%; marcar respuesta y estabilización.",
                },
            },
            {
                "id": 18, "nombre": "Escalones de potencia",                                   "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Consigna de potencia",
                    "senales": ["P", "P_setpoint"],
                    "criterio_visual": "Marcar escalón de potencia, sobrepaso y tiempo de estabilización.",
                },
            },
            {
                "id": 19, "nombre": "Rechazo de carga",                                        "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "island",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P / carga",
                    "y2": "Frecuencia o velocidad",
                    "senales": ["P", "f", "rpm", "breaker_status"],
                    "criterio_visual": "Mostrar rechazo de carga, permanencia excitada, velocidad nominal y tiempo de estabilización.",
                },
            },
            {
                "id": 20, "nombre": "Operación en isla",                                       "tipos": ["A","B","C","D"], "nivel": "unidad", "familia": "control_velocidad_gobernador",
                "template_key": "island",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia",
                    "y2": "Tensión / potencia activa",
                    "senales": ["f", "Vg", "P", "breaker_status"],
                    "criterio_visual": "Evidenciar estabilidad durante operación en isla y posterior condición estable.",
                },
            },

            # --- central / frecuencia_potencia_activa ---
            {
                "id": 21, "nombre": "Razón de cambio 2.5 Hz/s",                                "tipos": ["A","B","C","D"], "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "rocof_power",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia simulada / ROCOF",
                    "y2": "Potencia activa P",
                    "senales": ["f", "rocof", "P", "f_simulada"],
                    "criterio_visual": "Mostrar escalón o rampa equivalente a 2.5 Hz/s y permanencia interconectada.",
                },
            },
            {
                "id": 22, "nombre": "Rango de frecuencia",                                     "tipos": ["A","B","C","D"], "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "freq_power",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia",
                    "y2": "Potencia activa P",
                    "senales": ["f", "P", "breaker_status"],
                    "criterio_visual": "Mostrar permanencia conectada en rangos de frecuencia y respuesta de potencia si el control está activo.",
                },
            },
            {
                "id": 23, "nombre": "Limitación total de potencia activa",                     "tipos": ["A","B","C","D"], "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Consigna de potencia",
                    "senales": ["P", "P_setpoint", "f"],
                    "criterio_visual": "Evidenciar reducción total de potencia activa sin desconexión indebida.",
                },
            },
            {
                "id": 24, "nombre": "Reconexión automática",                                   "tipos": ["A","B"],          "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "power_ramp",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Frecuencia / tensión",
                    "senales": ["P", "f", "V", "breaker_status"],
                    "criterio_visual": "Mostrar 5 minutos previos en condiciones permitidas y rampa de incremento de potencia.",
                },
            },
            {
                "id": 25, "nombre": "Limitación parcial de potencia activa",                   "tipos": ["B"],              "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Consigna parcial de potencia",
                    "senales": ["P", "P_setpoint"],
                    "criterio_visual": "Mostrar seguimiento de consigna parcial definida por CENACE.",
                },
            },
            {
                "id": 26, "nombre": "Control primario de frecuencia",                          "tipos": ["A","B","C","D"], "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "freq_power_curve",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia",
                    "y2": "Potencia activa P",
                    "senales": ["f", "P", "P_ref"],
                    "criterio_visual": "Mostrar activación de control primario, banda muerta, estatismo y tiempo de estabilización.",
                },
            },
            {
                "id": 27, "nombre": "Control secundario de frecuencia",                        "tipos": ["C","D"],          "nivel": "central", "familia": "frecuencia_potencia_activa",
                "template_key": "freq_power_ref",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia / ACE o señal AGC",
                    "y2": "Potencia activa P / consigna AGC",
                    "senales": ["f", "P", "AGC_setpoint"],
                    "criterio_visual": "Mostrar seguimiento de control secundario si la central tipo C/D cuenta con AGC.",
                },
            },

            # --- central / tension_reactivos_poi ---
            {
                "id": 28, "nombre": "Rango de tensión en el punto de interconexión",           "tipos": ["A"],              "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "voltage_only",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "tension_tiempo",
                    "x": "Tiempo",
                    "y1": "Tensión en POI",
                    "y2": "Límites normativos",
                    "senales": ["V_POI"],
                    "criterio_visual": "Mostrar permanencia dentro de 0.90 pu a 1.10 pu para central tipo A.",
                },
            },
            {
                "id": 29, "nombre": "Rango de tensión en el punto de interconexión",           "tipos": ["B","C","D"],      "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "voltage_only",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "tension_tiempo",
                    "x": "Tiempo",
                    "y1": "Tensión en POI",
                    "y2": "Límites normativos",
                    "senales": ["V_POI"],
                    "criterio_visual": "Mostrar permanencia en rangos de tensión para centrales tipo B, C y D.",
                },
            },
            {
                "id": 30, "nombre": "Capacidad de potencia reactiva",                          "tipos": ["B"],              "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "reactive_pf",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Potencia reactiva Q",
                    "y2": "Factor de potencia FP",
                    "senales": ["Q", "FP", "P"],
                    "criterio_visual": "Evidenciar capacidad de mantener FP dentro del criterio requerido para tipo B.",
                },
            },
            {
                "id": 31, "nombre": "Capacidad de potencia reactiva a potencia máxima",        "tipos": ["C","D"],          "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "curva_pq",
                    "x": "Potencia activa P",
                    "y1": "Potencia reactiva Q/Pmax",
                    "y2": "Límite de capabilidad",
                    "senales": ["P", "Q", "V_POI"],
                    "criterio_visual": "Mostrar capacidad de potencia reactiva a potencia máxima para tipo C/D.",
                },
            },
            {
                "id": 32, "nombre": "Capacidad de potencia reactiva debajo de potencia máxima", "tipos": ["C","D"],         "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "curva_pq",
                    "x": "Potencia activa P",
                    "y1": "Potencia reactiva Q/Pmax",
                    "y2": "Límite de capabilidad",
                    "senales": ["P", "Q", "V_POI"],
                    "criterio_visual": "Mostrar perfil P-Q debajo de potencia máxima para tipo C/D.",
                },
            },
            {
                "id": 33, "nombre": "Sistema de control de tensión",                           "tipos": ["B","C","D"],      "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "voltage_reactive",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Tensión en POI / Vbus",
                    "y2": "Potencia reactiva Q / consigna de tensión",
                    "senales": ["V_POI", "Vbus", "Q", "V_setpoint"],
                    "criterio_visual": "Mostrar respuesta del sistema de control de tensión ante cambios de consigna.",
                },
            },
            {
                "id": 34, "nombre": "Control de tensión en condiciones dinámicas o de falla",  "tipos": ["B","C","D"],      "nivel": "central", "familia": "tension_reactivos_poi",
                "template_key": "frt",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "frt",
                    "x": "Tiempo",
                    "y1": "Tensión durante falla",
                    "y2": "Potencia activa/reactiva o estado de conexión",
                    "senales": ["V", "P", "Q", "breaker_status"],
                    "criterio_visual": "Mostrar permanencia dentro de la envolvente de falla y recuperación posterior.",
                },
            },

            # --- central / restauracion_operacion_especial ---
            {
                "id": 35, "nombre": "Arranque de emergencia",                                  "tipos": ["C","D"],          "nivel": "central", "familia": "restauracion_operacion_especial",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "secuencia",
                    "x": "Tiempo",
                    "y1": "Estados de arranque de emergencia",
                    "y2": "Frecuencia / tensión",
                    "senales": ["estado", "f", "V"],
                    "criterio_visual": "Mostrar capacidad de arranque de emergencia y transición a condición estable.",
                },
            },
            {
                "id": 36, "nombre": "Operación en modo isla",                                  "tipos": ["C","D"],          "nivel": "central", "familia": "restauracion_operacion_especial",
                "template_key": "island",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "doble_eje",
                    "x": "Tiempo",
                    "y1": "Frecuencia",
                    "y2": "Tensión / potencia activa",
                    "senales": ["f", "V", "P"],
                    "criterio_visual": "Mostrar estabilidad de variables durante modo isla.",
                },
            },
            {
                "id": 37, "nombre": "Resincronización rápida",                                 "tipos": ["C","D"],          "nivel": "central", "familia": "restauracion_operacion_especial",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "secuencia",
                    "x": "Tiempo",
                    "y1": "Estado de sincronización",
                    "y2": "Frecuencia / tensión / ángulo si existe",
                    "senales": ["sync_status", "f", "V", "angle"],
                    "criterio_visual": "Mostrar condiciones previas y cierre de resincronización rápida.",
                },
            },

            # --- central / administracion_sen ---
            {
                "id": 38, "nombre": "Requerimientos generales de administración del sistema",                   "tipos": ["B","C","D"], "nivel": "central", "familia": "administracion_sen",
                "template_key": "simulation",
                "graph_guideline": {
                    "usar_grafica": False,
                    "grafica": "documental",
                    "senales": [],
                    "criterio_visual": "Se documenta con evidencias de administración, comunicación, protecciones, telemetría e información del sistema.",
                },
            },
            {
                "id": 39, "nombre": "Requerimientos generales de administración del sistema — complemento",     "tipos": ["C","D"],      "nivel": "central", "familia": "administracion_sen",
                "template_key": "simulation",
                "graph_guideline": {
                    "usar_grafica": False,
                    "grafica": "documental",
                    "senales": [],
                    "criterio_visual": "Complemento documental de administración del sistema; sin gráfica obligatoria salvo evidencia SCADA específica.",
                },
            },
            {
                "id": 40, "nombre": "Requerimientos generales de administración del sistema — complemento",     "tipos": ["D"],          "nivel": "central", "familia": "administracion_sen",
                "template_key": "simulation",
                "graph_guideline": {
                    "usar_grafica": False,
                    "grafica": "documental",
                    "senales": [],
                    "criterio_visual": "Complemento documental para central tipo D; sin gráfica obligatoria salvo evidencia específica.",
                },
            },

            # --- central / modelos_simulacion ---
            {
                "id": 41, "nombre": "Modelos de simulación",                                  "tipos": ["A","B","C","D"], "nivel": "central", "familia": "modelos_simulacion",
                "template_key": "simulation",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "medido_vs_modelo",
                    "x": "Tiempo o punto de operación",
                    "y1": "Variable medida",
                    "y2": "Variable simulada / error",
                    "senales": ["medido", "simulado", "error"],
                    "criterio_visual": "Comparar medición contra modelo de simulación validado.",
                },
            },

            # --- operacion_desempeno / desempeno_operativo ---
            {
                "id": 42, "nombre": "Capacidad instalada neta, carga máxima y secuencias de arranque/paros", "tipos": ["B","C","D"], "nivel": "operacion_desempeno", "familia": "desempeno_operativo",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "tendencia_operativa",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Estado de operación / carga máxima",
                    "senales": ["P", "estado", "carga_maxima"],
                    "criterio_visual": "Mostrar operación, carga máxima y secuencias de arranque/paros.",
                },
            },
            {
                "id": 43, "nombre": "Operación en automático confiable",                      "tipos": ["B","C","D"], "nivel": "operacion_desempeno", "familia": "desempeno_operativo",
                "template_key": "sequence",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "tendencia_operativa",
                    "x": "Tiempo",
                    "y1": "Potencia activa P",
                    "y2": "Modo automático / estado de control",
                    "senales": ["P", "modo_auto", "estado_control"],
                    "criterio_visual": "Mostrar continuidad de operación automática confiable.",
                },
            },
            {
                "id": 44, "nombre": "Verificación de capacidad instalada neta y consumos",    "tipos": ["B","C","D"], "nivel": "operacion_desempeno", "familia": "desempeno_operativo",
                "template_key": "power_setpoint",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "tendencia_operativa",
                    "x": "Tiempo",
                    "y1": "Capacidad neta / potencia activa",
                    "y2": "Consumos propios",
                    "senales": ["P_neta", "P_bruta", "consumos"],
                    "criterio_visual": "Evidenciar capacidad instalada neta y consumos propios.",
                },
            },

            # --- operacion_desempeno / calidad_potencia ---
            {
                "id": 45, "nombre": "Requerimientos de calidad de la potencia",               "tipos": ["A","B","C","D"], "nivel": "operacion_desempeno", "familia": "calidad_potencia",
                "template_key": "quality",
                "graph_guideline": {
                    "usar_grafica": True,
                    "grafica": "calidad_potencia",
                    "x": "Tiempo / periodo de medición",
                    "y1": "Indicadores de calidad",
                    "y2": "Límites normativos",
                    "senales": ["THD", "flicker", "desbalance", "FP", "armónicos"],
                    "criterio_visual": "Mostrar tendencias de calidad de potencia durante al menos 10 días consecutivos.",
                },
            },
        ],
    },
}


def _build_catalog_indexes() -> tuple[
    dict[str, list[dict]], dict[str, dict[str, dict]]
]:
    ordered: dict[str, list[dict]] = {}
    by_key: dict[str, dict[str, dict]] = {}

    for central_kind, data in CENTRAL_CATALOGS.items():
        ordered[central_kind] = []
        by_key[central_kind] = {}

        for raw_test in data["tests"]:
            test_key = f"{central_kind}:{raw_test['id']}"
            test_entry = {**raw_test, "key": test_key, "central_kind": central_kind}
            ordered[central_kind].append(test_entry)
            by_key[central_kind][test_key] = test_entry

    return ordered, by_key


CATALOG_TESTS, CATALOG_BY_KEY = _build_catalog_indexes()

PRUEBAS_CODIGO_RED = {
    "asincrona": {
        1: "Prueba 1 - Sección 2.1 - 58.8≤f≤61.2 continuo; 61.2–61.8 Hz 30 min; 58.2–58.8 Hz 30 min; 61.8–63 Hz 15 min; 57–58.2 Hz 15 min",
        2: "Prueba 2 - Sección 2.2.1 - Permanecer conectada",
        3: "Prueba 3 - Sección 2.2.2 - Regulación seleccionable 3%–8% a partir de 60.2 Hz",
        4: "Prueba 4 - Sección 2.2.2 - 60–60.2 Hz potencia constante",
        5: "Prueba 5 - Sección 2.2.4 - Alcanzar consigna ≤5 s",
        6: "Prueba 6 - Sección 2.2.5 - f 58.8–60.2 Hz y V ±10% durante ≥5 min; rampa ≤10%/min",
        7: "Prueba 7 - Sección 2.2.4 - Definido por CENACE",
        8: "Prueba 8 - Sección 2.2.2 - Regulación 3%–8% a partir de 59.8 Hz",
        9: "Prueba 9 - Sección 2.2.2 - Característica de regulación 3%–8%",
        10: "Prueba 10 - Sección 2.2.3 - Insensibilidad 5–15 mHz; banda muerta ±0.03 Hz; activación ≤2 s; estabilización ≤30 s",
        11: "Prueba 11 - Sección 3.2 - 0.90≤V≤1.10 pu",
        12: "Prueba 12 - Sección 3.2 - 0.95≤V≤1.10 pu 30 min; 0.90≤V≤1.05 pu 30 min",
        13: "Prueba 13 - Sección 4.5 - Mantener FP ≥0.95 mediante control de Q",
        14: "Prueba 14 - Sección 4.5 - Cumplir rango mínimo de potencia reactiva",
        15: "Prueba 15 - Sección 4.5 - Rango dinámico de Q (± respecto a Pmax)",
        16: "Prueba 16 - Sección 4.5 - t1≤3 s, t2≤5 s, tolerancia ±2%",
        17: "Prueba 17 - Sección 4.5 - t1≤3 s, t2≤5 s, tolerancia ±2%",
        18: "Prueba 18 - Sección 4.5 - t1≤3 s, t2≤5 s, tolerancia ±0.1%",
        19: "Prueba 19 - Sección 2.3 - Cumplir amortiguamiento requerido",
        20: "Prueba 20 - Sección 5.3 - Permanecer dentro de curva FRT y responder dinámicamente",
        21: "Prueba 21 - Sección 2.2.4 - Verificar Runback/Rundown",
        22: "Prueba 22 - Sección 2.2.4 - Rampa ≤10% Pnom/min",
        23: "Prueba 23 - Sección 5.3 - Medir sobretensión y tiempo de desconexión",
        24: "Prueba 24 - Sección 6 - Modelo validado",
        25: "Prueba 25 - Sección 1 - Operación continua 240 h al 100%",
        26: "Prueba 26 - Sección 4 - Mediciones durante 10 días consecutivos",
        27: "Prueba 27 - Sección 4.5 - Operación en modo control Q/V",
        28: "Prueba 28 - Sección 2.2 - Cumplir control de frecuencia y rampa",
        31: "Prueba 31 - Alta frecuencia con zona esperada - Evaluacion con modelo droop piecewise, estatismos 3%, 5%, 8%",
        81: "Prueba 81 - Baja frecuencia con zona esperada - Evaluacion con modelo droop piecewise, estatismos 3%, 5%, 8%",
        91: "Prueba 91 - Control primario con zona esperada - Evaluacion con modelo droop piecewise, estatismos 3%, 5%, 8%",
    },
    "sincrona": {
        1:  "Prueba 1 - Sección 3.2 - Rango de tensión 0.50≤V≤1.10 pu en bornes de generación",
        2:  "Prueba 2 - Sección 3.3 - Escalón de tensión: t1≤0.7 s, t2≤1.0 s; t1≤0.5 s, t2≤2.0 s",
        3:  "Prueba 3 - Sección 3.4 - Limitador V/Hz: operación 1.07–1.12 pu",
        4:  "Prueba 4 - Sección 3 - Secuencia de excitación y desexcitación automática y manual",
        5:  "Prueba 5 - Sección 3 - Error de seguimiento entre canales y UCE ≤1%",
        6:  "Prueba 6 - Sección 2.3 - PSS: amortiguamiento de oscilaciones ≤30%",
        7:  "Prueba 7 - Sección 3 - Limitador de mínima excitación (MEL): límite inferior de Q",
        8:  "Prueba 8 - Sección 3 - Limitador de máxima excitación (OEL): límite superior de Q",
        9:  "Prueba 9 - Sección 4.5 - Compensador de MVAr: ±12% de potencia reactiva",
        10: "Prueba 10 - Sección 2.2 - Apertura/cierre: verificar tiempos y carrera de elementos finales",
        11: "Prueba 11 - Sección 2.2 - Secuencia de arranque: verificar tiempos y estados",
        12: "Prueba 12 - Sección 2.1 - Variador de velocidad (65F): rango 57–63 Hz",
        13: "Prueba 13 - Sección 2.2 - Escalones de velocidad: asentamiento t≤30 s",
        14: "Prueba 14 - Sección 2.1 - Protección por sobrevelocidad: umbral 110–112%",
        15: "Prueba 15 - Sección 2.2 - Variador de carga (65P): desde mínima a máxima potencia",
        16: "Prueba 16 - Sección 2.2 - Limitador de carga (65L): cumplir límites de carga",
        17: "Prueba 17 - Sección 2.2.2 - Estatismo: regulación seleccionable 3%–8%",
        18: "Prueba 18 - Sección 2.2 - Escalones de potencia: variación 10% de Pnom",
        19: "Prueba 19 - Sección 5.3 - Rechazo de carga: cambio automático a operación en isla",
        20: "Prueba 20 - Sección 5.3 - Operación en isla: estabilidad de frecuencia y tensión",
        21: "Prueba 21 - Sección 2.2.1 - Razón de cambio 2.5 Hz/s: permanecer conectada",
        22: "Prueba 22 - Sección 2.1 - Rango de frecuencia: 58.8≤f≤61.2 Hz continuo y rangos extendidos",
        23: "Prueba 23 - Sección 2.2.4 - Limitación total de potencia activa por frecuencia",
        24: "Prueba 24 - Sección 2.2.5 - Reconexión automática: f 58.8–60.2 Hz y V ±10% ≥5 min; rampa ≤10%/min",
        25: "Prueba 25 - Sección 2.2.4 - Limitación parcial de potencia activa: definido por CENACE",
        26: "Prueba 26 - Sección 2.2.2 - Control primario de frecuencia: característica de regulación 3%–8%",
        27: "Prueba 27 - Sección 2.2.3 - Control secundario: insensibilidad 5–15 mHz; banda muerta ±0.03 Hz; activación ≤2 s; estabilización ≤30 s",
        28: "Prueba 28 - Sección 3.2 - Rango de tensión en POI: 0.90≤V≤1.10 pu (Tipo A)",
        29: "Prueba 29 - Sección 3.2 - Rango de tensión en POI: 0.95≤V≤1.10 pu 30 min; 0.90≤V≤1.05 pu 30 min (Tipos B,C,D)",
        30: "Prueba 30 - Sección 4.5 - Capacidad de potencia reactiva: mantener FP ≥0.95 (Tipo B)",
        31: "Prueba 31 - Sección 4.5 - Capacidad de potencia reactiva a potencia máxima (Tipos C,D)",
        32: "Prueba 32 - Sección 4.5 - Capacidad de potencia reactiva debajo de potencia máxima (Tipos C,D)",
        33: "Prueba 33 - Sección 4.5 - Sistema de control de tensión: t1≤3 s, t2≤5 s, tolerancia ±2%",
        34: "Prueba 34 - Sección 5.3 - Control de tensión en condiciones dinámicas o de falla: curva FRT",
        35: "Prueba 35 - Sección 5.3 - Arranque de emergencia: capacidad de auto-arranque",
        36: "Prueba 36 - Sección 5.3 - Operación en modo isla: estabilidad en desconexión de red",
        37: "Prueba 37 - Sección 5.3 - Resincronización rápida: sincronización automática posterior a falla",
        38: "Prueba 38 - Sección 6 - Requerimientos de administración del sistema SEN",
        39: "Prueba 39 - Sección 6 - Requerimientos de administración del sistema — complemento",
        40: "Prueba 40 - Sección 6 - Requerimientos de administración del sistema — complemento",
        41: "Prueba 41 - Sección 6 - Modelos de simulación validados",
        42: "Prueba 42 - Sección 1 - Capacidad instalada neta, carga máxima y secuencias de arranque/paro",
        43: "Prueba 43 - Sección 1 - Operación en automático confiable: continuidad operativa",
        44: "Prueba 44 - Sección 1 - Verificación de capacidad instalada neta y consumos",
        45: "Prueba 45 - Sección 4 - Requerimientos de calidad de la potencia: mediciones 10 días consecutivos",
    },
}

GRAPH_TEMPLATES = {
    "freq_power": {
        "title": "Frecuencia y potencia activa",
        "layout": "Serie temporal en doble eje",
        "x": "Tiempo",
        "series": ["Frecuencia (Hz)", "Potencia activa (MW)"],
    },
    "freq_power_ref": {
        "title": "Frecuencia, potencia activa y referencia",
        "layout": "Serie temporal en doble eje con referencia",
        "x": "Tiempo",
        "series": ["Frecuencia (Hz)", "Potencia activa (MW)", "Setpoint / referencia"],
    },
    "rocof_power": {
        "title": "ROCOF/frecuencia y potencia activa",
        "layout": "Serie temporal de evento con variable derivada",
        "x": "Tiempo",
        "series": [
            "Frecuencia o ROCOF",
            "Potencia activa (MW)",
            "Referencia si aplica",
        ],
    },
    "freq_power_cases": {
        "title": "Frecuencia y potencia activa por casos",
        "layout": "Serie temporal por caso con comparación de estatismo",
        "x": "Tiempo",
        "series": ["Frecuencia (Hz)", "Potencia activa (MW)", "Casos 3%-5%-8%"],
    },
    "freq_power_curve": {
        "title": "Frecuencia y potencia con curva teórica",
        "layout": "Serie temporal con banda o curva de referencia",
        "x": "Tiempo",
        "series": ["Frecuencia (Hz)", "Potencia activa (MW)", "Curva teórica"],
    },
    "freq_power_zones": {
        "title": "Frecuencia y potencia con zona esperada",
        "layout": "Serie temporal con zona sombreada y curva teorica droop",
        "x": "Tiempo",
        "series": ["Frecuencia (Hz)", "Potencia activa (MW)", "Curva teorica", "Zona esperada"],
    },
    "voltage_only": {
        "title": "Tensión en el punto de interconexión",
        "layout": "Serie temporal simple o doble umbral",
        "x": "Tiempo",
        "series": ["Tensión (pu o kV)", "Límites normativos"],
    },
    "voltage_power": {
        "title": "Tensión y potencia activa",
        "layout": "Serie temporal en doble eje",
        "x": "Tiempo",
        "series": ["Tensión", "Potencia activa"],
    },
    "voltage_reactive": {
        "title": "Tensión y potencia reactiva",
        "layout": "Serie temporal en doble eje",
        "x": "Tiempo",
        "series": ["Tensión", "Potencia reactiva"],
    },
    "reactive_pf": {
        "title": "Potencia reactiva y factor de potencia",
        "layout": "Serie temporal con validación de capacidad",
        "x": "Tiempo",
        "series": [
            "Potencia reactiva (MVAr)",
            "Factor de potencia",
            "Límites o referencia",
        ],
    },
    "power_setpoint": {
        "title": "Potencia activa y consigna",
        "layout": "Serie temporal de seguimiento",
        "x": "Tiempo",
        "series": ["Potencia activa (MW)", "Consigna / referencia"],
    },
    "power_ramp": {
        "title": "Potencia activa y rampa",
        "layout": "Serie temporal con pendiente de carga",
        "x": "Tiempo",
        "series": ["Potencia activa (MW)", "Pendiente o rampa objetivo"],
    },
    "quality": {
        "title": "Calidad de potencia",
        "layout": "Tendencias y resumen por periodo",
        "x": "Tiempo / periodo",
        "series": ["THD", "Desbalance", "Factor de potencia", "Indicadores de calidad"],
    },
    "frt": {
        "title": "Curva FRT y respuesta dinámica",
        "layout": "Tensión/frecuencia contra envolvente normativa",
        "x": "Tiempo",
        "series": ["Tensión o frecuencia", "Curva FRT", "Potencia activa/reactiva"],
    },
    "simulation": {
        "title": "Medido vs modelo",
        "layout": "Comparativa de simulación y medición",
        "x": "Tiempo o barrido de operación",
        "series": ["Variable medida", "Variable simulada", "Error"],
    },
    "sequence": {
        "title": "Secuencia operativa",
        "layout": "Trazas de estados y tiempos de actuación",
        "x": "Tiempo",
        "series": ["Estados", "Mandos", "Respuesta del equipo"],
    },
    "speed_load": {
        "title": "Velocidad/frecuencia y carga",
        "layout": "Serie temporal en doble eje",
        "x": "Tiempo",
        "series": ["Velocidad o frecuencia", "Carga / potencia"],
    },
    "island": {
        "title": "Operación en isla",
        "layout": "Serie temporal de estabilidad",
        "x": "Tiempo",
        "series": ["Frecuencia", "Tensión", "Potencia activa"],
    },
}

TEST_GRAPH_PROFILES = {
    "asincrona": {
        1: "freq_power",
        2: "rocof_power",
        3: "freq_power_curve",
        4: "freq_power_ref",
        5: "power_setpoint",
        6: "power_ramp",
        7: "power_setpoint",
        8: "freq_power_cases",
        9: "freq_power_curve",
        10: "freq_power_ref",
        11: "voltage_only",
        12: "voltage_only",
        13: "reactive_pf",
        14: "voltage_reactive",
        15: "voltage_reactive",
        16: "voltage_reactive",
        17: "voltage_reactive",
        18: "reactive_pf",
        19: "freq_power",
        20: "frt",
        21: "power_ramp",
        22: "power_ramp",
        23: "frt",
        24: "simulation",
        25: "power_setpoint",
        26: "quality",
        27: "voltage_reactive",
        28: "freq_power_ref",
        31: "freq_power_zones",
        81: "freq_power_zones",
        91: "freq_power_zones",
    },
}

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pruebas de Centrales · Código de Red",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS SaaS/Laboratorio ─────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #f4f7fb;
    --surface: #ffffff;
    --surface-soft: #eef4f8;
    --surface-tint: #e6f3f1;
    --ink: #102033;
    --muted: #64748b;
    --line: #d7e2ea;
    --line-strong: #b9c9d6;
    --primary: #0f766e;
    --primary-strong: #115e59;
    --secondary: #2563eb;
    --warning: #b45309;
    --danger: #dc2626;
    --ok: #047857;
    --sidebar: #102033;
    --sidebar-soft: #16324a;
    --shadow: 0 14px 36px rgba(15, 32, 51, 0.08);
}

/* Radio navigation */
div[role="radiogroup"] > label > div:first-child { display: none !important; }
div[role="radiogroup"] > label {
    padding: 10px 12px;
    background: transparent;
    border-radius: 8px;
    margin-bottom: 6px;
    border: 1px solid transparent;
    transition: background 0.16s ease, border-color 0.16s ease;
}
div[role="radiogroup"] > label:hover {
    background: rgba(230, 243, 241, 0.10);
    border-color: rgba(148, 163, 184, 0.22);
}
div[role="radiogroup"] > label[data-checked="true"], 
div[role="radiogroup"] > label[aria-checked="true"] {
    background: rgba(15, 118, 110, 0.18);
    border-left: 3px solid #2dd4bf;
    color: #fff !important;
}
div[role="radiogroup"] > label[aria-checked="true"] p {
    font-weight: 700 !important;
}

*, *::before, *::after { box-sizing: border-box; }

.stApp {
    font-family: 'Inter', sans-serif !important;
    background:
        linear-gradient(180deg, rgba(230, 243, 241, 0.72) 0, rgba(244, 247, 251, 0) 260px),
        var(--bg);
    color: var(--ink);
    -webkit-font-smoothing: antialiased;
}

.main .block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
}

h1, h2, h3, h4,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    font-family: 'Inter', sans-serif !important;
    color: var(--ink) !important;
    letter-spacing: 0;
    font-weight: 700 !important;
}

.stMarkdown p, .stMarkdown li, .stCaption, .stAlert p {
    font-family: 'Inter', sans-serif;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--ink);
}

.top-shell {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 24px 32px;
    margin-bottom: 24px;
    box-shadow: var(--shadow);
}

.top-brand {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
}
.top-brand-mark {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; color: #ffffff;
    flex-shrink: 0;
}
.top-brand-text {
    display: flex;
    flex-direction: column;
}
.top-brand-name {
    font-weight: 800; font-size: 1.4rem; color: var(--ink);
    letter-spacing: 0; line-height: 1.2;
}
.top-brand-sub {
    font-size: 0.9rem; color: var(--muted);
    letter-spacing: 0; text-transform: uppercase;
    font-weight: 600;
}

.top-inline-summary {
    background: var(--surface-soft);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 0.95rem;
    color: var(--muted);
    line-height: 1.5;
}
.top-inline-summary strong {
    color: var(--ink);
    font-weight: 700;
    font-size: 1.1rem;
    display: block;
    margin-bottom: 4px;
}

/* ── Module title bar (integrated) ────────────────────────── */
.module-title-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 32px 0 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--line);
}
.module-title-bar h2 {
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    color: var(--ink) !important;
    margin: 0 !important;
}
.module-title-bar .module-icon {
    font-size: 1.8rem;
    line-height: 1;
    background: var(--surface-tint);
    padding: 10px;
    border-radius: 8px;
}

.app-header {
    margin-bottom: 16px;
}
.app-header h1 {
    font-size: 1.5rem !important;
}
.header-badge {
    background: var(--surface-tint);
    color: var(--primary-strong);
    font-size: 0.75rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    text-transform: uppercase;
    margin-bottom: 8px;
    display: inline-block;
}

.stButton > button {
    font-family: 'Inter', sans-serif !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.96rem !important;
    padding: 10px 18px !important;
    transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease !important;
    border: 1px solid var(--line-strong) !important;
}
.stButton > button[kind="primary"] {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 8px 20px rgba(15, 118, 110, 0.18) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--primary-strong) !important;
    box-shadow: 0 10px 24px rgba(15, 118, 110, 0.22) !important;
}
.stButton > button:not([kind="primary"]) {
    background: var(--surface) !important;
    color: var(--ink) !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: var(--surface-soft) !important;
    color: var(--primary-strong) !important;
}

.stDownloadButton > button {
    font-family: 'Inter', sans-serif !important;
    background: var(--surface) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 8px !important;
    color: var(--primary-strong) !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 10px 20px !important;
}
.stDownloadButton > button:hover {
    background: var(--surface-tint) !important;
    border-color: var(--primary) !important;
}
button[kind="secondary"],
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
}
[data-testid="stBaseButton-secondary"] {
    background: #ffffff !important;
    color: var(--ink) !important;
    border: 1px solid var(--line-strong) !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-tint) !important;
    border-color: var(--primary) !important;
    color: var(--primary-strong) !important;
}
[data-testid="stBaseButton-primary"] {
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    color: #ffffff !important;
    box-shadow: 0 8px 20px rgba(15, 118, 110, 0.18) !important;
}

.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea textarea {
    font-family: 'Inter', sans-serif !important;
    background: var(--surface) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 8px !important;
    color: var(--ink) !important;
    font-size: 0.96rem !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(15, 118, 110, 0.14) !important;
}
.stSelectbox label, .stTextInput label, .stNumberInput label,
.stTextArea label, .stFileUploader label, .stDateInput label,
.stMultiSelect label {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    color: var(--muted) !important;
    font-weight: 600 !important;
    margin-bottom: 8px !important;
}

/* ── Selects, dropdown menus and multiselect chips ───────── */
div[data-baseweb="select"] {
    font-family: 'Inter', sans-serif !important;
}
div[data-baseweb="select"] > div {
    min-height: 42px !important;
    background: var(--surface) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 0 rgba(15, 32, 51, 0.02) !important;
}
div[data-baseweb="select"] > div:hover {
    border-color: var(--primary) !important;
}
div[data-baseweb="select"] input,
div[data-baseweb="select"] span,
div[data-baseweb="select"] div {
    color: var(--ink) !important;
}
div[data-baseweb="select"] svg {
    color: var(--primary) !important;
}
div[data-baseweb="popover"] {
    z-index: 999999 !important;
}
div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] div[role="listbox"] {
    background: #ffffff !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    box-shadow: 0 18px 42px rgba(15, 32, 51, 0.18) !important;
    padding: 6px !important;
}
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] div[role="option"] {
    color: var(--ink) !important;
    border-radius: 6px !important;
    margin: 2px 0 !important;
}
div[data-baseweb="popover"] li:hover,
div[data-baseweb="popover"] div[role="option"]:hover {
    background: var(--surface-tint) !important;
    color: var(--primary-strong) !important;
}
div[data-baseweb="tag"] {
    background: var(--surface-tint) !important;
    border: 1px solid #b9d9d2 !important;
    border-radius: 999px !important;
    color: var(--primary-strong) !important;
}
div[data-baseweb="tag"] span {
    color: var(--primary-strong) !important;
}

/* ── File upload dropzones ───────────────────────────────── */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    padding: 12px !important;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
}
[data-testid="stFileUploaderDropzone"] {
    background:
        linear-gradient(135deg, rgba(15, 118, 110, 0.06), rgba(37, 99, 235, 0.04)),
        #ffffff !important;
    border: 1px dashed var(--line-strong) !important;
    border-radius: 8px !important;
    min-height: 116px !important;
    transition: border-color 0.16s ease, background 0.16s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--primary) !important;
    background: var(--surface-tint) !important;
}
[data-testid="stFileUploaderDropzone"] * {
    font-family: 'Inter', sans-serif !important;
    color: var(--ink) !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    font-weight: 800 !important;
    padding: 8px 14px !important;
}
[data-testid="stFileUploaderFile"] {
    background: var(--surface-soft) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--sidebar) 0%, var(--sidebar-end, #0b1826) 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] * {
    color: #d8e6ef;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: rgba(255, 255, 255, 0.08) !important;
    border-color: rgba(255, 255, 255, 0.16) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] input,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {
    color: #ffffff !important;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #a9c3cf !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--line) !important;
    gap: 18px !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding: 12px 0 !important;
    color: var(--muted) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
}

.streamlit-expanderHeader {
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: var(--ink) !important;
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
}

.card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
}
.card-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 12px;
}
.card-sub {
    font-size: 0.95rem;
    color: var(--muted);
    margin-bottom: 16px;
    line-height: 1.6;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
}
.kpi-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 20px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.06);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 6px; height: 100%;
}
.kpi-done::before { background: var(--ok); }
.kpi-prog::before { background: var(--warning); }
.kpi-total::before { background: var(--secondary); }

.kpi-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0;
    font-weight: 700;
    color: var(--muted);
    margin-bottom: 8px;
}
.kpi-value {
    font-family: 'Inter', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--ink);
    line-height: 1;
    margin-bottom: 8px;
}
.kpi-sub {
    font-size: 0.9rem;
    color: var(--muted);
    line-height: 1.5;
}

.crono-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    transition: border-color 0.16s ease, box-shadow 0.16s ease;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
}
.crono-card:hover {
    border-color: var(--primary);
    box-shadow: 0 12px 32px rgba(15, 32, 51, 0.08);
}
.crono-card-header {
    margin-bottom: 16px;
}
.crono-card-badge {
    display: inline-flex;
    align-items: center; gap: 6px;
    font-size: 0.8rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    text-transform: uppercase;
    margin-bottom: 12px;
}
.badge-completada { background: rgba(4, 120, 87, 0.10); color: var(--ok); border: 1px solid rgba(4, 120, 87, 0.24); }
.badge-en-progreso { background: rgba(180, 83, 9, 0.10); color: var(--warning); border: 1px solid rgba(180, 83, 9, 0.24); }
.badge-pendiente { background: var(--surface-soft); color: var(--muted); border: 1px solid var(--line); }
.badge-doc { background: rgba(8, 145, 178, 0.10); color: #0891b2; border: 1px solid rgba(8, 145, 178, 0.22); }

.crono-card-id {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--ink);
}
.crono-card-name {
    font-size: 1rem;
    color: var(--ink);
    line-height: 1.5;
    margin-top: 4px;
}
.crono-card-meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 16px;
    margin: 16px 0;
    background: var(--surface-soft);
    padding: 12px;
    border-radius: 8px;
}
.crono-card-meta-item {
    font-size: 0.9rem;
    color: var(--ink);
    line-height: 1.4;
}
.crono-card-meta-item span {
    display: block;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0;
    color: var(--muted);
    font-weight: 700;
    margin-bottom: 2px;
}

.crono-veredicto-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 12px 0 4px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
}
.crono-veredicto-label {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0;
    color: var(--muted);
    font-weight: 700;
}

.veredicto-none { color: var(--muted); font-size: 0.9rem; font-weight: 600; }
.veredicto-cumple { color: var(--ok); font-size: 0.9rem; font-weight: 700; }
.veredicto-nocumple { color: var(--danger); font-size: 0.9rem; font-weight: 700; }
.veredicto-revision { color: var(--warning); font-size: 0.9rem; font-weight: 700; }
.veredicto-doc { color: #0891b2; font-size: 0.9rem; font-weight: 700; }
.veredicto-repeat { color: #c2410c; font-size: 0.9rem; font-weight: 700; }

.crono-footer {
    background: var(--surface-soft);
    border-radius: 8px;
    padding: 16px;
    border: 1px solid var(--line);
}
.crono-footer-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 8px;
}
.crono-footer-text {
    font-size: 0.9rem;
    color: var(--muted);
    line-height: 1.6;
    margin-bottom: 12px;
}
.crono-footer-ref {
    font-size: 0.85rem;
    color: var(--muted);
    background: var(--surface);
    padding: 8px 12px;
    border-radius: 8px;
    display: inline-block;
}

.crono-table-wrap {
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--line);
    background: var(--surface);
}
.crono-table-wrap table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
}
.crono-table-wrap th {
    background: var(--surface-soft);
    color: var(--primary-strong);
    font-weight: 700;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0;
    padding: 14px 16px;
    text-align: left;
    border-bottom: 1px solid var(--line);
}
.crono-table-wrap td {
    padding: 14px 16px;
    border-bottom: 1px solid var(--line);
    color: var(--ink);
}
.crono-table-wrap tr:hover td {
    background: var(--surface-soft);
}

.project-summary {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
}
.project-summary-title {
    font-weight: 800;
    font-size: 1.2rem;
    color: var(--ink);
    margin-bottom: 6px;
}
.project-summary-meta {
    font-size: 0.95rem;
    color: var(--muted);
    line-height: 1.6;
}

.section-label {
    font-size: 0.9rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0;
    color: var(--primary);
    margin: 32px 0 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
}

.plot-panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
    box-shadow: var(--shadow);
}

.export-toolbar {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
}
.export-toolbar-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 6px;
}
.export-toolbar-sub {
    font-size: 0.9rem;
    color: var(--muted);
    margin-bottom: 16px;
}

.style-preview {
    display: flex; gap: 16px;
    margin: 12px 0;
}
.style-chip {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.95rem; color: var(--ink);
    background: var(--surface-soft);
    padding: 6px 12px;
    border-radius: 8px;
}
.style-swatch {
    width: 16px; height: 16px;
    border-radius: 4px;
    display: inline-block;
}

.view-toggle { display: flex; gap: 8px; }

.caso-block { margin-bottom: 12px; }
.caso-label {
    font-size: 1.05rem;
    color: var(--ink);
    font-weight: 600;
    display: flex; align-items: center; gap: 12px;
}
.caso-badge {
    background: var(--secondary);
    color: #ffffff;
    font-size: 0.85rem;
    font-weight: 800;
    padding: 4px 12px;
    border-radius: 999px;
}

.advanced-shell, .settings-shell {
    background: transparent;
}

.evidence-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    transition: border-color 0.16s ease, box-shadow 0.16s ease;
}
.evidence-card:hover { 
    border-color: var(--primary);
    box-shadow: 0 10px 24px rgba(15, 32, 51, 0.08);
}
.evidence-card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 6px;
}
.evidence-card-meta {
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 12px;
}

.gallery-toolbar {
    margin-bottom: 16px;
}
.gallery-grid-note {
    font-size: 0.9rem;
    color: var(--muted);
    margin-bottom: 16px;
    font-weight: 600;
}

.timeline-summary {
    font-size: 0.95rem;
    color: var(--muted);
    margin-bottom: 16px;
    line-height: 1.6;
    background: var(--surface-soft);
    padding: 12px 16px;
    border-radius: 8px;
}

.stProgress > div > div > div {
    background: var(--primary) !important;
    border-radius: 999px !important;
}

.stDataFrame {
    border-radius: 8px !important;
    overflow: hidden;
    border: 1px solid var(--line) !important;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
    background: var(--surface) !important;
}
[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05) !important;
}
[data-testid="stDataFrame"] *,
[data-testid="stDataEditor"] * {
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stDataFrame"] canvas,
[data-testid="stDataEditor"] canvas {
    background: #ffffff !important;
}
[data-testid="stDataFrame"] button,
[data-testid="stDataEditor"] button {
    color: var(--primary-strong) !important;
    border-radius: 6px !important;
}

/* ── Native lab tables used for read-only data ───────────── */
.lab-table-wrap {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    margin: 10px 0 18px;
    box-shadow: 0 8px 24px rgba(15, 32, 51, 0.05);
}
.lab-table-caption {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    background: #f8fbfd;
    border-bottom: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.86rem;
    font-weight: 700;
    text-transform: uppercase;
}
.lab-table-scroll {
    overflow-x: auto;
}
.lab-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.92rem;
}
.lab-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--surface-tint);
    color: var(--primary-strong);
    padding: 11px 13px;
    text-align: left;
    font-weight: 800;
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
}
.lab-table tbody td {
    padding: 11px 13px;
    color: var(--ink);
    border-bottom: 1px solid #edf2f6;
    vertical-align: top;
}
.lab-table tbody tr:nth-child(even) td {
    background: #fbfdfe;
}
.lab-table tbody tr:hover td {
    background: var(--surface-tint);
}
.lab-table-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 800;
    white-space: nowrap;
}
.lab-badge-ok { background: rgba(4, 120, 87, 0.10); color: #047857; border: 1px solid rgba(4, 120, 87, 0.22); }
.lab-badge-warn { background: rgba(180, 83, 9, 0.10); color: #b45309; border: 1px solid rgba(180, 83, 9, 0.22); }
.lab-badge-danger { background: rgba(220, 38, 38, 0.10); color: #dc2626; border: 1px solid rgba(220, 38, 38, 0.22); }
.lab-badge-neutral { background: #eef4f8; color: #64748b; border: 1px solid #d7e2ea; }

/* ── Test selector replacing the old editable grid ───────── */
.test-selector-group {
    margin: 16px 0 8px;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--surface-tint);
    border: 1px solid var(--line-strong);
    color: var(--primary-strong);
    font-size: 0.86rem;
    font-weight: 800;
}
.test-row-shell {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    margin: 4px 0 8px;
    box-shadow: 0 6px 16px rgba(15, 32, 51, 0.04);
}
.test-row-title {
    color: var(--ink);
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1.35;
}
.test-row-meta {
    color: var(--muted);
    font-size: 0.82rem;
    line-height: 1.4;
    margin-top: 2px;
}
[data-testid="stCheckbox"] label {
    align-items: center !important;
}
[data-testid="stCheckbox"] p {
    color: var(--ink) !important;
    font-weight: 600 !important;
}

hr {
    border-color: var(--line) !important;
    margin: 24px 0 !important;
}

.stAlert {
    border-radius: 8px !important;
    font-size: 0.95rem !important;
    border: 1px solid var(--line) !important;
}

.stFileUploader > div {
    border-radius: 8px !important;
    background: var(--surface) !important;
    border: 1px dashed var(--line-strong) !important;
    padding: 16px !important;
}
.stFileUploader > div:hover {
    border-color: var(--primary) !important;
}

/* ── Final uploader/button readability pass ──────────────── */
.main [data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    padding: 12px !important;
    box-shadow: 0 10px 28px rgba(30, 27, 75, 0.08) !important;
}
.main [data-testid="stFileUploader"] label,
.main [data-testid="stFileUploader"] label *,
.main [data-testid="stFileUploader"] small,
.main [data-testid="stFileUploader"] section > div > span,
.main [data-testid="stFileUploaderDropzone"] > div,
.main [data-testid="stFileUploaderDropzone"] p,
.main [data-testid="stFileUploaderDropzone"] span {
    color: var(--ink) !important;
}
.main [data-testid="stFileUploaderDropzone"] {
    background: #ffffff !important;
    border: 1px dashed var(--line-strong) !important;
    border-radius: 8px !important;
    min-height: 122px !important;
    box-shadow: inset 0 0 0 1px rgba(49, 46, 129, 0.03) !important;
}
.main [data-testid="stFileUploaderDropzone"]:hover {
    background: var(--surface-tint) !important;
    border-color: var(--primary) !important;
}
.main [data-testid="stFileUploaderDropzone"] button,
.main [data-testid="stFileUploaderDropzone"] button[kind],
.main [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    font-weight: 800 !important;
}
.main [data-testid="stFileUploaderDropzone"] button *,
.main [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] *,
.main [data-testid="stFileUploaderDropzone"] button p,
.main [data-testid="stFileUploaderDropzone"] button span {
    color: #ffffff !important;
}
.main [data-testid="stFileUploaderFile"] {
    background: var(--surface-soft) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
}
.main [data-testid="stFileUploaderFile"] * {
    color: var(--ink) !important;
}
.main .stButton > button,
.main .stDownloadButton > button,
.main [data-testid="stBaseButton-secondary"],
.main [data-testid="stBaseButton-primary"] {
    min-height: 42px !important;
}
.main .stButton > button[kind="primary"],
.main [data-testid="stBaseButton-primary"] {
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    color: #ffffff !important;
}
.main .stButton > button[kind="primary"] *,
.main [data-testid="stBaseButton-primary"] * {
    color: #ffffff !important;
}
.main .stButton > button:not([kind="primary"]),
.main .stDownloadButton > button,
.main [data-testid="stBaseButton-secondary"] {
    background: #ffffff !important;
    border: 1px solid var(--line-strong) !important;
    color: var(--primary-strong) !important;
}
.main .stButton > button:not([kind="primary"]) *,
.main .stDownloadButton > button *,
.main [data-testid="stBaseButton-secondary"] * {
    color: var(--primary-strong) !important;
}

/* ── Hard override for Streamlit upload buttons ──────────── */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploaderDropzone"] button[kind],
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1px solid var(--primary) !important;
    border-radius: 8px !important;
    box-shadow: 0 6px 16px rgba(30, 27, 75, 0.10) !important;
    color: var(--primary-strong) !important;
    opacity: 1 !important;
}
[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stFileUploaderDropzone"] button p,
[data-testid="stFileUploaderDropzone"] button span,
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] *,
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] * {
    color: var(--primary-strong) !important;
    opacity: 1 !important;
    -webkit-text-fill-color: var(--primary-strong) !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]:hover,
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-tint) !important;
    background-color: var(--surface-tint) !important;
    border-color: var(--primary-strong) !important;
}

/* ── Upload tray only: hide Streamlit's internal browse button ─ */
[data-testid="stFileUploaderDropzone"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 132px !important;
    cursor: pointer !important;
    position: relative !important;
    padding-top: 44px !important;
}
[data-testid="stFileUploaderDropzone"]::before {
    content: "";
    position: absolute;
    top: 20px;
    left: 50%;
    width: 28px;
    height: 28px;
    transform: translateX(-50%);
    background-color: var(--primary);
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 16V4'/%3E%3Cpath d='m7 9 5-5 5 5'/%3E%3Cpath d='M20 16.5v2.25A2.25 2.25 0 0 1 17.75 21H6.25A2.25 2.25 0 0 1 4 18.75V16.5'/%3E%3C/svg%3E") center / contain no-repeat;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 16V4'/%3E%3Cpath d='m7 9 5-5 5 5'/%3E%3Cpath d='M20 16.5v2.25A2.25 2.25 0 0 1 17.75 21H6.25A2.25 2.25 0 0 1 4 18.75V16.5'/%3E%3C/svg%3E") center / contain no-repeat;
}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {
    text-align: center !important;
    color: var(--muted) !important;
}

@media (max-width: 768px) {
    .kpi-grid { grid-template-columns: 1fr; }
    .crono-card-meta { grid-template-columns: 1fr; }
    .top-shell { padding: 16px; }
    .module-title-bar h2 { font-size: 1.4rem !important; }
}
</style>
""",
    unsafe_allow_html=True,
)



# ─── Helpers ───────────────────────────────────────────────────────────────────
def save_upload(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getbuffer())
    tmp.close()
    return Path(tmp.name)


def render_header(title: str, subtitle: str, icon: str = ""):
    st.markdown(
        f"""
    <div class="app-header">
        <div class="header-badge">{icon} Código de Red</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "proyecto"


def _project_label(project: dict) -> str:
    return project["central_name"]


def _read_json_file(file_path: Path) -> dict:
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _codigo_red_criterio(test_key: str) -> str:
    test = _get_catalog_test(test_key)
    return PRUEBAS_CODIGO_RED.get(test["central_kind"], {}).get(
        test["id"],
        "Criterio de aceptación pendiente por definir en el Código de Red 2.0.",
    )


def _graph_profile(test_key: str) -> dict:
    test = _get_catalog_test(test_key)
    template_key = test.get(
        "template_key",
        TEST_GRAPH_PROFILES.get(test["central_kind"], {}).get(test["id"], "freq_power"),
    )
    profile = {**GRAPH_TEMPLATES[template_key]}

    if test["central_kind"] == "sincrona":
        guideline = test.get("graph_guideline", {})
        profile.update(
            {
                "usar_grafica": guideline.get("usar_grafica", True),
                "grafica": guideline.get("grafica", template_key),
                "y1": guideline.get("y1", "Variable principal"),
                "y2": guideline.get("y2", "Variable secundaria"),
                "senales": guideline.get("senales", []),
                "criterio_visual": guideline.get(
                    "criterio_visual",
                    "Lineamiento gráfico pendiente por definir.",
                ),
            }
        )

    return profile


def _html_text(value: object) -> str:
    return html.escape(str(value), quote=True)


def _format_lab_cell(value: object) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _lab_badge_class(column: str, value: object) -> str | None:
    normalized = str(value).strip().lower()
    column_key = column.strip().lower()
    if column_key == "semaforo":
        return {
            "verde": "lab-badge-ok",
            "amarillo": "lab-badge-warn",
            "rojo": "lab-badge-danger",
        }.get(normalized, "lab-badge-neutral")
    if column_key == "estado":
        if "completada" in normalized:
            return "lab-badge-ok"
        if "progreso" in normalized or "revision" in normalized:
            return "lab-badge-warn"
        if "document" in normalized:
            return "lab-badge-neutral"
        return "lab-badge-neutral"
    if column_key == "veredicto":
        if "cumple" == normalized:
            return "lab-badge-ok"
        if "no cumple" in normalized:
            return "lab-badge-danger"
        if "pendiente" in normalized or "repetir" in normalized:
            return "lab-badge-warn"
        return "lab-badge-neutral"
    return None


def _render_lab_table(
    df: pd.DataFrame,
    *,
    caption: str = "",
    hide_index: bool = True,
    max_rows: int | None = None,
) -> None:
    if df is None or df.empty:
        st.info("No hay registros para mostrar.")
        return

    display_df = df.copy()
    display_df = display_df[[col for col in display_df.columns if not str(col).startswith("_")]]
    if max_rows is not None:
        display_df = display_df.head(max_rows)

    columns = list(display_df.columns)
    header_cells = "".join(f"<th>{_html_text(col)}</th>" for col in columns)
    if not hide_index:
        header_cells = "<th>#</th>" + header_cells

    body_rows = []
    for idx, row in display_df.iterrows():
        cells = []
        if not hide_index:
            cells.append(f"<td>{_html_text(idx)}</td>")
        for col in columns:
            value = row[col]
            text = _format_lab_cell(value)
            badge_class = _lab_badge_class(str(col), value)
            if badge_class:
                cell_html = f'<span class="lab-table-badge {badge_class}">{_html_text(text)}</span>'
            else:
                cell_html = _html_text(text)
            cells.append(f"<td>{cell_html}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    caption_html = (
        f'<div class="lab-table-caption">{_html_text(caption)}</div>' if caption else ""
    )
    st.markdown(
        f"""
        <div class="lab-table-wrap">
            {caption_html}
            <div class="lab-table-scroll">
                <table class="lab-table">
                    <thead><tr>{header_cells}</tr></thead>
                    <tbody>{''.join(body_rows)}</tbody>
                </table>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _technical_summary_html(
    test_key: str,
    conclusion: str,
    scope_title: str | None = None,
    scope_text: str | None = None,
) -> str:
    graph_profile = _graph_profile(test_key)
    graph_type = graph_profile.get("grafica", graph_profile.get("title", ""))
    graph_title = graph_profile.get("title", "")
    graph_label = graph_type
    if graph_title and graph_title != graph_type:
        graph_label = f"{graph_type} · {graph_title}"

    signal_list = ", ".join(graph_profile.get("senales", [])) or "No aplica"
    graph_required = "Sí" if graph_profile.get("usar_grafica", True) else "No obligatoria"
    y1 = graph_profile.get("y1", "No definido")
    y2 = graph_profile.get("y2", "No definido")
    visual_criterion = graph_profile.get(
        "criterio_visual",
        "Lineamiento grafico pendiente por definir.",
    )

    scope_block = ""
    if scope_title and scope_text:
        scope_block = f"""
            <div class="card-title">{_html_text(scope_title)}</div>
            <p style="color:#475569; line-height:1.7; margin:0 0 14px 0;">{_html_text(scope_text)}</p>
        """

    return f"""
        <div class="card">
            {scope_block}
            <div class="card-title">Tipo de gráfica</div>
            <p style="color:#475569; line-height:1.7; margin:0 0 14px 0;">{_html_text(graph_label)}</p>
            <div class="card-title">Lineamiento gráfico</div>
            <p style="color:#475569; line-height:1.7; margin:0 0 10px 0;">{_html_text(visual_criterion)}</p>
            <p style="color:#64748b; line-height:1.7; margin:0 0 14px 0;">
                Uso de gráfica: {_html_text(graph_required)}<br>
                Eje Y1: {_html_text(y1)}<br>
                Eje Y2: {_html_text(y2)}<br>
                Señales requeridas: {_html_text(signal_list)}
            </p>
            <div class="card-title">Criterio de aceptación</div>
            <p style="color:#475569; line-height:1.7; margin:0 0 14px 0;">{_html_text(_codigo_red_criterio(test_key))}</p>
            <div class="card-title">Conclusión normativa</div>
            <p style="color:#102033; line-height:1.7; margin:0;">{_html_text(conclusion)}</p>
        </div>
    """


def _get_catalog_test(test_key: str) -> dict:
    central_kind, _ = test_key.split(":", 1)
    return CATALOG_BY_KEY[central_kind][test_key]


def _test_label(test_key: str) -> str:
    test = _get_catalog_test(test_key)
    return f"{test['id']:02d} · {test['nombre']}"


def _project_family_label(project: dict) -> str:
    return CENTRAL_CATALOGS[project["central_kind"]]["nombre"]


def _eligible_tests(central_kind: str, central_class: str) -> list[str]:
    return [
        test["key"]
        for test in CATALOG_TESTS[central_kind]
        if central_class in test.get("tipos", [])
    ]


def _normalize_test_ids(
    test_ids: list[str], central_kind: str, central_class: str
) -> list[str]:
    eligible = set(_eligible_tests(central_kind, central_class))
    return [
        test_id
        for test_id in _eligible_tests(central_kind, central_class)
        if test_id in eligible and test_id in set(test_ids)
    ]


def _normalize_project_record(project: dict, slug: str) -> dict | None:
    central_name = project.get("central_name", "").strip()
    if not central_name:
        return None

    central_kind = project.get("central_kind", "asincrona").strip().lower()
    central_class = str(project.get("central_class", "A")).strip().upper()
    applicable_tests = project.get("applicable_tests", [])

    if central_kind not in CENTRAL_CATALOGS:
        central_kind = "asincrona"
    if central_class not in {"A", "B", "C", "D"}:
        central_class = "A"

    normalized_tests = _normalize_test_ids(
        applicable_tests, central_kind, central_class
    )
    if not normalized_tests:
        normalized_tests = _eligible_tests(central_kind, central_class)

    return {
        "slug": slug,
        "central_name": central_name,
        "central_kind": central_kind,
        "central_class": central_class,
        "applicable_tests": normalized_tests,
    }


def _project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def _project_file(slug: str, filename: str) -> Path:
    return _project_dir(slug) / filename


def _project_output_dir(project: dict) -> Path:
    out_dir = _project_dir(project["slug"]) / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _project_depur_dir(project: dict) -> Path:
    out_dir = _project_dir(project["slug"]) / "DEPUR" / "SALIDAS"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []

    projects: list[dict] = []
    for project_path in sorted(PROJECTS_DIR.iterdir()):
        if not project_path.is_dir():
            continue

        metadata_file = project_path / "metadata.json"
        if not metadata_file.exists():
            continue

        project = _normalize_project_record(
            _read_json_file(metadata_file),
            project_path.name,
        )
        if not project:
            continue
        projects.append(project)

    projects.sort(key=lambda item: (_project_label(item).lower(), item["slug"]))
    return projects


def _next_project_slug(base_slug: str) -> str:
    slug = base_slug
    index = 2
    while _project_dir(slug).exists():
        slug = f"{base_slug}-{index}"
        index += 1
    return slug


def _save_project_metadata(
    slug: str,
    central_name: str,
    central_kind: str,
    central_class: str,
    applicable_tests: list[str],
) -> dict:
    normalized_tests = _normalize_test_ids(
        applicable_tests, central_kind, central_class
    )
    project = {
        "slug": slug,
        "central_name": central_name.strip(),
        "central_kind": central_kind,
        "central_class": central_class,
        "applicable_tests": normalized_tests,
    }

    project_dir = _project_dir(slug)
    project_dir.mkdir(parents=True, exist_ok=True)
    _project_output_dir(project)
    _project_depur_dir(project)
    schedule_file = _project_file(slug, "cronograma.json")
    saved_schedule = _read_json_file(schedule_file) if schedule_file.exists() else {}

    synced_schedule = _default_schedule_for_tests(normalized_tests)
    for pid in normalized_tests:
        entry = saved_schedule.get(pid)
        if isinstance(entry, dict):
            synced_schedule[pid] = {
                "estado": entry.get("estado", "Pendiente"),
                "fecha": entry.get("fecha", ""),
                "nota": entry.get("nota", ""),
            }

    _project_file(slug, "metadata.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    schedule_file.write_text(
        json.dumps(synced_schedule, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return project


def _render_active_project(project: dict | None) -> None:
    if not project:
        st.info(
            "Selecciona o crea una central antes de trabajar con cronograma, análisis o depuración."
        )
        return

    st.markdown(
        f"""
        <div class="project-summary">
            <div class="project-summary-title">{_project_label(project)}</div>
            <div class="project-summary-meta">
                <strong>Familia:</strong> {_project_family_label(project)}<br>
                <strong>Tipo:</strong> {project["central_class"]}<br>
                <strong>Pruebas aplicables:</strong> {len(project.get("applicable_tests", []))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_exception(prefix: str, exc: Exception) -> None:
    st.error(f"{prefix}: {exc}")
    with st.expander("Ver detalle"):
        st.code(traceback.format_exc())


def _default_schedule_for_tests(test_ids: list[str]) -> dict:
    return {
        pid: {
            "estado": "Pendiente",
            "fecha_inicio": "",
            "fecha_termino": "",
            "fecha_inicio_auto": "",
            "fecha_termino_auto": "",
            "duracion_min": "",
            "origen_tiempo": "",
            "nota": "",
            "veredicto": "",
        }
        for pid in test_ids
    }


def _has_manual_analysis_template(test_key: str) -> bool:
    test = _get_catalog_test(test_key)
    return test["central_kind"] == "sincrona" and bool(test.get("graph_guideline"))


def _analysis_templates_for_project(project: dict) -> list[str]:
    analysis_tests: list[str] = []
    for test_key in project.get("applicable_tests", []):
        implemented_code = _get_catalog_test(test_key).get("implemented_code")
        if implemented_code in REGISTRY or _has_manual_analysis_template(test_key):
            analysis_tests.append(test_key)
    return analysis_tests


# ─── Cronograma ────────────────────────────────────────────────────────────────
def _load_schedule(project: dict) -> dict:
    applicable_tests = project.get("applicable_tests", [])
    schedule = _default_schedule_for_tests(applicable_tests)
    schedule_file = _project_file(project["slug"], "cronograma.json")

    saved = _read_json_file(schedule_file) if schedule_file.exists() else {}

    for pid in applicable_tests:
        entry = saved.get(pid)
        if isinstance(entry, dict):
            old_fecha = entry.get("fecha", "")
            schedule[pid] = {
                "estado": entry.get("estado", "Pendiente"),
                "fecha_inicio": entry.get("fecha_inicio") or entry.get("fecha") or "",
                "fecha_termino": entry.get("fecha_termino") or "",
                "fecha_inicio_auto": entry.get("fecha_inicio_auto", ""),
                "fecha_termino_auto": entry.get("fecha_termino_auto", ""),
                "duracion_min": entry.get("duracion_min", ""),
                "origen_tiempo": entry.get("origen_tiempo", ""),
                "nota": entry.get("nota", ""),
                "veredicto": entry.get("veredicto", ""),
            }

    return schedule


def _save_schedule(project: dict, schedule: dict) -> None:
    _project_dir(project["slug"]).mkdir(parents=True, exist_ok=True)
    _project_file(project["slug"], "cronograma.json").write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


IMAGE_EVIDENCE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DATA_EVIDENCE_EXTENSIONS = {".csv", ".xlsx", ".xls"}
EVIDENCE_EXTENSIONS = IMAGE_EVIDENCE_EXTENSIONS | DATA_EVIDENCE_EXTENSIONS


def _find_test_evidence(project: dict, test_id: int) -> list[Path]:
    out_dir = _project_output_dir(project)
    if not out_dir.exists():
        return []
    evidence_paths: list[Path] = []
    for ext in EVIDENCE_EXTENSIONS:
        evidence_paths.extend(out_dir.rglob(f"*P{test_id}_*{ext}"))
    return sorted(evidence_paths)


def _render_evidence_file(path: Path, key: str) -> None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EVIDENCE_EXTENSIONS:
        st.image(str(path), use_container_width=True)
        return

    st.caption("Archivo de datos adjunto")
    if suffix == ".csv":
        try:
            _render_lab_table(pd.read_csv(path), caption="Vista previa CSV", max_rows=20)
        except Exception:
            st.info("No fue posible previsualizar el CSV, pero el archivo esta guardado.")
    elif suffix in {".xlsx", ".xls"}:
        try:
            _render_lab_table(pd.read_excel(path), caption="Vista previa Excel", max_rows=20)
        except Exception:
            st.info("No fue posible previsualizar el Excel, pero el archivo esta guardado.")

    with open(path, "rb") as fh:
        st.download_button(
            "Descargar archivo",
            data=fh.read(),
            file_name=path.name,
            key=key,
        )


def _normalize_signal_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


SYNC_SIGNAL_ALIASES = {
    "vg": ["vg", "voltaje generador", "tension generador", "terminales", "voltage generator"],
    "vgsp": ["vgsp", "vref", "voltaje referencia", "consigna voltaje", "setpoint voltaje"],
    "vf": ["vf", "voltaje campo", "field voltage"],
    "if": ["if", "corriente campo", "field current"],
    "f": ["f", "freq", "frecuencia", "frequency"],
    "v_hz": ["v hz", "v/hz", "v hz ratio"],
    "p": ["p", "mw", "potencia activa", "active power"],
    "q": ["q", "mvar", "potencia reactiva", "reactive power"],
    "fp": ["fp", "factor potencia", "power factor"],
    "rpm": ["rpm", "velocidad", "speed"],
    "speed_percent": ["speed percent", "porcentaje velocidad", "velocidad porcentaje"],
    "v_poi": ["v poi", "voltaje poi", "tension poi", "voltage poi"],
    "vbus": ["vbus", "voltaje bus", "tension bus"],
    "v": ["v", "voltaje", "tension", "voltage"],
    "p_setpoint": ["p setpoint", "pref", "consigna potencia", "potencia referencia"],
    "p_ref": ["p ref", "pref", "referencia potencia"],
    "load_setpoint": ["load setpoint", "consigna carga"],
    "load_limit": ["load limit", "limite carga"],
    "pss": ["pss"],
    "rocof": ["rocof", "df dt"],
    "f_simulada": ["f simulada", "frecuencia simulada"],
    "breaker_status": ["breaker", "interruptor", "estado interruptor"],
    "agc_setpoint": ["agc", "agc setpoint", "consigna agc"],
}


def _signal_aliases(signal: str) -> list[str]:
    normalized = _normalize_signal_text(signal)
    aliases = [normalized]
    aliases.extend(SYNC_SIGNAL_ALIASES.get(normalized.replace(" ", "_"), []))
    aliases.extend(SYNC_SIGNAL_ALIASES.get(normalized, []))
    return list(dict.fromkeys(_normalize_signal_text(alias) for alias in aliases if alias))


def _detect_signal_column(columns: list[str], signal: str, used: set[str] | None = None) -> str | None:
    used = used or set()
    normalized_columns = {column: _normalize_signal_text(column) for column in columns if column not in used}
    aliases = _signal_aliases(signal)
    for alias in aliases:
        for column, normalized in normalized_columns.items():
            if normalized == alias:
                return column
    for alias in aliases:
        alias_words = alias.split()
        for column, normalized in normalized_columns.items():
            words = normalized.split()
            if len(alias_words) == 1:
                if alias_words[0] in words:
                    return column
            elif all(word in words for word in alias_words):
                return column
    return None


def _prepare_sincrona_dataframe(raw: pd.DataFrame, time_col: str, value_cols: list[str]) -> pd.DataFrame:
    if not value_cols:
        raise ValueError("Selecciona al menos una columna de señal para graficar.")

    df = raw[[time_col, *value_cols]].copy()
    df[time_col] = _parse_datetime_series(df[time_col])
    rename_map = {time_col: "time"}
    for col in value_cols:
        rename_map[col] = str(col)
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = (
        df.rename(columns=rename_map)
        .dropna(subset=["time"])
        .sort_values("time")
        .drop_duplicates(subset=["time"])
        .reset_index(drop=True)
    )
    signal_cols = [col for col in df.columns if col != "time"]
    df = df.dropna(subset=signal_cols, how="all")
    if df.empty:
        raise ValueError("No hay datos numéricos útiles para las señales seleccionadas.")
    return df


def _sincrona_output_path(project: dict, test_info: dict, output_dir: Path, df: pd.DataFrame) -> Path:
    return unique_path(
        output_dir
        / artifact_filename(
            output_dir,
            descriptor="grafica_sincrona",
            ext=".png",
            test_id=f"P{test_info['id']}",
            df=df,
        )
    )


def _plot_sincrona_png(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
    graph_profile: dict,
) -> Path:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    signal_cols = [col for col in df.columns if col != "time"]
    rows = max(1, len(signal_cols))
    fig, axes = plt.subplots(rows, 1, figsize=(15, max(5.5, 2.8 * rows)), sharex=True)
    if rows == 1:
        axes = [axes]

    visual = _active_visual_palette()
    palette = _active_series_palette()
    fig.patch.set_facecolor(visual["bg"])
    for idx, col in enumerate(signal_cols):
        ax = axes[idx]
        ax.set_facecolor(visual["surface"])
        ax.plot(df["time"], df[col], linewidth=1.9, color=palette[idx % len(palette)], label=col)
        ax.set_ylabel(col, color=visual["ink"])
        ax.grid(True, color=visual["line"], alpha=0.75)
        ax.tick_params(axis="both", colors=visual["muted"])
        for spine in ax.spines.values():
            spine.set_color(visual["line_strong"])
        ax.legend(loc="upper right")

    axes[-1].set_xlabel("Tiempo")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate(rotation=20)
    fig.suptitle(title, fontsize=15, fontweight="bold", color=visual["ink"])
    criterion = graph_profile.get("criterio_visual", "")
    if criterion:
        fig.text(0.01, 0.01, criterion, fontsize=9, color=visual["muted"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _build_sincrona_interactive_figure(result, test_key: str) -> go.Figure | None:
    df = getattr(result, "df", None)
    if df is None or df.empty:
        return None
    graph_profile = _graph_profile(test_key)
    signal_cols = [col for col in df.columns if col != "time"]
    if not signal_cols:
        return None
    rows = len(signal_cols)
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=signal_cols,
    )
    palette = _active_series_palette()
    for idx, col in enumerate(signal_cols, start=1):
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=palette[(idx - 1) % len(palette)], width=2.1),
                showlegend=rows == 1,
            ),
            row=idx,
            col=1,
        )
        fig.update_yaxes(title_text=col, row=idx, col=1)
    fig.update_xaxes(title_text=graph_profile.get("x", "Tiempo"), row=rows, col=1)
    return _apply_plotly_layout(fig, _test_label(test_key), height=260 * rows + 110)


def _run_sincrona_analysis(
    project: dict,
    test_key: str,
    source_path: Path,
    time_col: str,
    value_cols: list[str],
) -> SimpleNamespace:
    test_info = _get_catalog_test(test_key)
    graph_profile = _graph_profile(test_key)
    output_dir = _project_output_dir(project)
    raw = load_table(source_path)
    df = _prepare_sincrona_dataframe(raw, time_col, value_cols)
    output_path = _sincrona_output_path(project, test_info, output_dir, df)
    _plot_sincrona_png(df, output_path, _test_label(test_key), graph_profile)
    return SimpleNamespace(
        output_path=output_path,
        row_count=len(df),
        test_id=f"S{test_info['id']}",
        df=df,
        output_paths=[output_path],
    )


def _show_sincrona_result(result, test_key: str) -> None:
    st.success(f"Gráfica generada · {result.row_count:,} registros procesados")
    fig = _build_sincrona_interactive_figure(result, test_key)
    if fig is not None:
        st.markdown('<div class="plot-panel">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, key=f"plotly_sincrona_{test_key}")
        st.markdown('</div>', unsafe_allow_html=True)
    if result.output_path.exists():
        with open(result.output_path, "rb") as fh:
            st.download_button(
                "Descargar PNG",
                data=fh.read(),
                file_name=result.output_path.name,
                mime="image/png",
                key=f"dl_sincrona_{test_key}",
            )
        with st.expander("Ver PNG exportado", expanded=False):
            st.image(str(result.output_path), use_container_width=True)


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


import datetime


def _parse_date(val: str) -> datetime.date | None:
    if not val:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _date_to_str(val: datetime.date | None) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime.date):
        return val.strftime("%d/%m/%Y")
    return str(val)


def _parse_datetime_value(val: str) -> datetime.datetime | None:
    if not val:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            parsed = datetime.datetime.strptime(val, fmt)
            if fmt == "%d/%m/%Y":
                parsed = datetime.datetime.combine(parsed.date(), datetime.time.min)
            return parsed
        except ValueError:
            continue
    return None


def _datetime_to_str(val: datetime.datetime | None) -> str:
    if val is None:
        return ""
    return val.strftime("%d/%m/%Y %H:%M:%S")


def _effective_schedule_window(entry: dict) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    start = _parse_datetime_value(entry.get("fecha_inicio_auto", "")) or _parse_datetime_value(entry.get("fecha_inicio", ""))
    end = _parse_datetime_value(entry.get("fecha_termino_auto", "")) or _parse_datetime_value(entry.get("fecha_termino", ""))
    return start, end


def _effective_schedule_labels(entry: dict) -> tuple[str, str]:
    start, end = _effective_schedule_window(entry)
    start_label = _datetime_to_str(start) if start else (entry.get("fecha_inicio") or "—")
    end_label = _datetime_to_str(end) if end else (entry.get("fecha_termino") or "—")
    return start_label, end_label


def _format_duration_minutes(value: object) -> str:
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return "—"
    if minutes <= 0:
        return "—"
    if minutes < 60:
        return f"{minutes:.0f} min"
    hours = minutes / 60.0
    if hours < 24:
        return f"{hours:.1f} h"
    days = int(hours // 24)
    rem_hours = hours - days * 24
    return f"{days} d {rem_hours:.1f} h"


def _result_time_window(result) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    frames = getattr(result, "frames", None) or {}
    merged = frames.get("merged")
    if isinstance(merged, pd.DataFrame) and not merged.empty and "time" in merged.columns:
        times = pd.to_datetime(merged["time"], errors="coerce").dropna()
        if not times.empty:
            return times.min().to_pydatetime(), times.max().to_pydatetime()

    df = getattr(result, "df", None)
    if isinstance(df, pd.DataFrame) and not df.empty and "time" in df.columns:
        times = pd.to_datetime(df["time"], errors="coerce").dropna()
        if not times.empty:
            return times.min().to_pydatetime(), times.max().to_pydatetime()

    successful = getattr(result, "successful", None)
    if successful:
        starts: list[datetime.datetime] = []
        ends: list[datetime.datetime] = []
        for case in successful:
            case_df = getattr(case, "df", None)
            if isinstance(case_df, pd.DataFrame) and not case_df.empty and "time" in case_df.columns:
                times = pd.to_datetime(case_df["time"], errors="coerce").dropna()
                if not times.empty:
                    starts.append(times.min().to_pydatetime())
                    ends.append(times.max().to_pydatetime())
        if starts and ends:
            return min(starts), max(ends)

    return None, None


def _autosync_schedule_from_result(project: dict, test_key: str, result) -> None:
    start_dt, end_dt = _result_time_window(result)
    if start_dt is None or end_dt is None:
        return
    schedule = _load_schedule(project)
    entry = schedule.get(test_key, _default_schedule_for_tests([test_key])[test_key])
    duration_min = max((end_dt - start_dt).total_seconds() / 60.0, 0.0)
    schedule[test_key] = {
        **entry,
        "estado": "Completada",
        "fecha_inicio_auto": _datetime_to_str(start_dt),
        "fecha_termino_auto": _datetime_to_str(end_dt),
        "duracion_min": round(duration_min, 1),
        "origen_tiempo": "automatico",
    }
    _save_schedule(project, schedule)


def _build_schedule_export_df(
    test_ids: list[str],
    schedule: dict,
    evidence_map: dict[str, list[Path]],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for pid in test_ids:
        test_info = _get_catalog_test(pid)
        entry = schedule.get(pid, _default_schedule_for_tests([pid])[pid])
        graph_profile = _graph_profile(pid)
        start_label, end_label = _effective_schedule_labels(entry)
        rows.append(
            {
                "Prueba": f"P{test_info['id']:02d}",
                "Nombre": test_info["nombre"],
                "Estado": entry.get("estado", "Pendiente"),
                "Veredicto": _veredict_style(entry.get("veredicto", ""))["label"],
                "Fecha inicio": start_label,
                "Fecha termino": end_label,
                "Duracion": _format_duration_minutes(entry.get("duracion_min", "")),
                "Evidencias": len(evidence_map.get(pid, [])),
                "Tipo de grafica": graph_profile.get("grafica", graph_profile["title"]),
                "Eje Y1": graph_profile.get("y1", "—"),
                "Eje Y2": graph_profile.get("y2", "—"),
                "Señales requeridas": ", ".join(graph_profile.get("senales", [])) or "—",
                "Criterio visual": graph_profile.get("criterio_visual", "—"),
                "Observaciones": entry.get("nota", ""),
            }
        )
    return pd.DataFrame(rows)


def _build_timeline_dataframe(
    filtered_ids: list[str],
    schedule: dict,
    evidence_map: dict[str, list[Path]],
) -> tuple[pd.DataFrame, list[str], int]:
    timeline_rows: list[dict] = []
    missing_dates: list[str] = []
    partial_dates = 0

    for pid in filtered_ids:
        test_info = _get_catalog_test(pid)
        entry = schedule.get(pid, _default_schedule_for_tests([pid])[pid])
        start_dt, end_dt = _effective_schedule_window(entry)

        if start_dt is None and end_dt is None:
            missing_dates.append(f"P{test_info['id']:02d} · {test_info['nombre']}")
            continue

        if start_dt is None:
            start_dt = end_dt
            partial_dates += 1
        if end_dt is None:
            end_dt = start_dt
            partial_dates += 1
        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt
        if start_dt == end_dt:
            duration_value = entry.get("duracion_min", "")
            try:
                duration_min = max(float(duration_value), 1.0)
            except (TypeError, ValueError):
                duration_min = 1.0
            end_dt = start_dt + datetime.timedelta(minutes=duration_min)

        timeline_rows.append(
            {
                "Prueba": f"P{test_info['id']:02d} · {test_info['nombre']}",
                "Estado": entry.get("estado", "Pendiente"),
                "Inicio": start_dt,
                "Fin": end_dt,
                "InicioLabel": _datetime_to_str(start_dt),
                "FinLabel": _datetime_to_str(end_dt),
                "Veredicto": _veredict_style(entry.get("veredicto", ""))["label"],
                "Observaciones": entry.get("nota", "") or "Sin observaciones",
                "Evidencias": len(evidence_map.get(pid, [])),
                "Duracion": _format_duration_minutes(entry.get("duracion_min", "")),
            }
        )

    return pd.DataFrame(timeline_rows), missing_dates, partial_dates


def _timeline_pdf_bytes(
    project: dict,
    filtered_ids: list[str],
    schedule_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
) -> bytes:
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        fig.patch.set_facecolor("#f4f7fb")
        ax.set_facecolor("#f4f7fb")
        ax.axis("off")
        ax.text(
            0.02,
            0.94,
            f"Cronograma filtrado · {project['central_name']}",
            fontsize=18,
            fontweight="bold",
            color="#102033",
            transform=ax.transAxes,
        )
        ax.text(
            0.02,
            0.89,
            f"Exportado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} · Registros: {len(schedule_df)}",
            fontsize=10,
            color="#64748b",
            transform=ax.transAxes,
        )
        preview_columns = [
            "Prueba",
            "Nombre",
            "Estado",
            "Veredicto",
            "Fecha inicio",
            "Fecha termino",
            "Duracion",
            "Evidencias",
        ]
        preview_df = schedule_df[preview_columns].head(16)
        table = ax.table(
            cellText=preview_df.values,
            colLabels=list(preview_df.columns),
            cellLoc="left",
            colLoc="left",
            bbox=[0.02, 0.08, 0.96, 0.74],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_facecolor("#e6f3f1")
                cell.set_text_props(color="#115e59", weight="bold")
            else:
                cell.set_facecolor("#ffffff")
                cell.set_text_props(color="#102033")
            cell.set_edgecolor("#d7e2ea")
        pdf.savefig(fig, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)

        if not timeline_df.empty:
            fig2, ax2 = plt.subplots(figsize=(11.69, max(6, len(timeline_df) * 0.33 + 1.8)))
            fig2.patch.set_facecolor("#f4f7fb")
            ax2.set_facecolor("#f4f7fb")
            y_pos = list(range(len(timeline_df)))
            colors = [STATUS_META.get(status, STATUS_META["Pendiente"])["color"] for status in timeline_df["Estado"]]
            starts = mdates.date2num(pd.to_datetime(timeline_df["Inicio"]))
            ends = mdates.date2num(pd.to_datetime(timeline_df["Fin"]))
            widths = ends - starts
            ax2.barh(y_pos, widths, left=starts, color=colors, height=0.55, alpha=0.9)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(timeline_df["Prueba"], fontsize=8, color="#102033")
            ax2.tick_params(axis="x", colors="#64748b", labelsize=8)
            ax2.tick_params(axis="y", length=0)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y %H:%M"))
            plt.setp(ax2.get_xticklabels(), rotation=25, ha="right")
            ax2.set_title("Linea de tiempo exportada", color="#102033", fontsize=14, pad=14)
            ax2.grid(True, axis="x", color="#d7e2ea", linewidth=0.8)
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)
            ax2.spines["left"].set_color("#d7e2ea")
            ax2.spines["bottom"].set_color("#d7e2ea")
            fig2.tight_layout()
            pdf.savefig(fig2, facecolor=fig2.get_facecolor(), bbox_inches="tight")
            plt.close(fig2)

    buffer.seek(0)
    return buffer.read()


def _render_schedule_export_toolbar(
    project: dict,
    filtered_ids: list[str],
    schedule: dict,
    evidence_map: dict[str, list[Path]],
) -> None:
    export_df = _build_schedule_export_df(filtered_ids, schedule, evidence_map)
    timeline_df, _, _ = _build_timeline_dataframe(filtered_ids, schedule, evidence_map)
    project_label = project_token(project["slug"])
    export_date = datetime.datetime.now().strftime("%Y%m%d")
    excel_name = artifact_filename(
        project_label,
        descriptor="cronograma",
        ext=".xlsx",
        date_label=export_date,
    )
    pdf_name = artifact_filename(
        project_label,
        descriptor="cronograma",
        ext=".pdf",
        date_label=export_date,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        xlsx_path = Path(tmpdir) / excel_name
        write_xlsx(export_df, xlsx_path, sheet_name="Cronograma")
        xlsx_bytes = xlsx_path.read_bytes()

    pdf_bytes = _timeline_pdf_bytes(project, filtered_ids, export_df, timeline_df)

    st.markdown('<div class="export-toolbar">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="export-toolbar-title">Exportar cronograma actual</div>
        <div class="export-toolbar-sub">Las descargas respetan el filtro, la busqueda y la seleccion visible en pantalla.</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.download_button(
            "Descargar Excel",
            data=xlsx_bytes,
            file_name=excel_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"dl_schedule_xlsx_{project['slug']}",
        )
    with c2:
        st.download_button(
            "Descargar PDF",
            data=pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf",
            use_container_width=True,
            key=f"dl_schedule_pdf_{project['slug']}",
        )
    with c3:
        st.caption(
            f"{len(export_df)} registro(s) incluidos. "
            f"{len(timeline_df)} con rango de fechas utilizable para la linea de tiempo."
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _status_style(status: str) -> dict:
    return STATUS_META.get(status, STATUS_META["Pendiente"])


def _veredict_style(veredict: str) -> dict:
    return VERDICT_META.get(veredict, VERDICT_META[""])


def _normalize_voltage_display(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return pd.to_numeric(series, errors="coerce")
    median = float(clean.abs().median())
    if 0.2 <= median <= 2.0 or median <= 1e-9:
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(series, errors="coerce") / median


def _apply_plotly_layout(fig: go.Figure, title: str, height: int = 460) -> go.Figure:
    fig.update_layout(
        title=title,
        height=height,
        template="plotly_white",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="#f8fbfd",
        margin=dict(l=24, r=24, t=70, b=24),
        font=dict(family="Inter, Arial, sans-serif", color="#102033"),
        title_font=dict(size=18, color="#102033"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0)",
            font=dict(color="#475569"),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d7e2ea", font_color="#102033"),
    )
    fig.update_xaxes(
        gridcolor="#e3ebf2",
        linecolor="#cbd8e3",
        tickfont=dict(color="#64748b"),
        title_font=dict(color="#475569"),
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor="#e3ebf2",
        linecolor="#cbd8e3",
        tickfont=dict(color="#64748b"),
        title_font=dict(color="#475569"),
        zeroline=False,
    )
    return fig


def _build_simple_interactive_figure(
    result,
    config,
    test_key: str,
    freq_color: str,
    power_color: str,
) -> go.Figure | None:
    df = getattr(result, "df", None)
    if df is None or df.empty:
        return None
    if result.test_id == "P28":
        return None

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    title = config.titulo()

    if result.test_id == "P12":
        voltage = _normalize_voltage_display(df["voltage"])
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=voltage,
                mode="lines",
                name="Tension",
                line=dict(color="#a855f7", width=2.2),
            )
        )
        fig.add_hrect(y0=0.90, y1=1.10, fillcolor="rgba(34,197,94,0.10)", line_width=0)
        fig.add_hline(y=0.90, line_dash="dash", line_color="#ef4444")
        fig.add_hline(y=1.10, line_dash="dash", line_color="#ef4444")
        fig.update_yaxes(title_text="Tension (pu)")
        fig.update_xaxes(title_text="Tiempo")
        return _apply_plotly_layout(fig, title)

    if result.test_id == "P13":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["reactive_power"],
                mode="lines",
                name="Potencia reactiva",
                line=dict(color="#f97316", width=2.2),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["power_factor"],
                mode="lines",
                name="Factor de potencia",
                line=dict(color="#14b8a6", width=2.2),
            ),
            secondary_y=True,
        )
        fig.add_trace(
            go.Scatter(
                x=[df["time"].min(), df["time"].max()],
                y=[0.95, 0.95],
                mode="lines",
                name="FP minimo",
                line=dict(color="#ef4444", width=1.4, dash="dash"),
            ),
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Potencia reactiva (MVAr)", secondary_y=False)
        fig.update_yaxes(title_text="Factor de potencia", range=[-1.05, 1.05], secondary_y=True)
        fig.update_xaxes(title_text="Tiempo")
        return _apply_plotly_layout(fig, title)

    if result.test_id == "P26":
        label_map = {
            "thd_voltage": "THD tension",
            "thd_current": "THD corriente",
            "unbalance": "Desbalance",
            "power_factor": "Factor de potencia",
            "current": "Corriente",
        }
        signal_columns = [column for column in df.columns if column != "time"]
        fig = make_subplots(
            rows=len(signal_columns),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=[label_map.get(column, column) for column in signal_columns],
        )
        palette = ["#4f46e5", "#0891b2", "#b45309", "#2563eb", "#0f766e"]
        for idx, column in enumerate(signal_columns, start=1):
            fig.add_trace(
                go.Scatter(
                    x=df["time"],
                    y=df[column],
                    mode="lines",
                    name=label_map.get(column, column),
                    line=dict(color=palette[(idx - 1) % len(palette)], width=1.9),
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )
            fig.update_yaxes(title_text=label_map.get(column, column), row=idx, col=1)
        fig.update_xaxes(title_text="Tiempo", row=len(signal_columns), col=1)
        return _apply_plotly_layout(fig, title, height=260 * len(signal_columns) + 110)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["frequency"],
            mode="lines",
            name="Frecuencia",
            line=dict(color=freq_color, width=2.3),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["active_power"],
            mode="lines",
            name="Potencia activa",
            line=dict(color=power_color, width=2.3),
        ),
        secondary_y=True,
    )
    if "aux" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["aux"],
                mode="lines",
                name="Setpoint / Referencia",
                line=dict(color="#f59e0b", width=1.8, dash="dash"),
            ),
            secondary_y=True,
        )
    fig.update_yaxes(title_text="Frecuencia (Hz)", secondary_y=False)
    fig.update_yaxes(title_text=f"Potencia activa ({config.power_unit})", secondary_y=True)
    fig.update_xaxes(title_text="Tiempo")
    return _apply_plotly_layout(fig, title)


def _build_multi_case_interactive_figure(
    case_result,
    config,
    freq_color: str,
    power_color: str,
) -> go.Figure | None:
    df = getattr(case_result, "df", None)
    if df is None or df.empty:
        return None

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["frequency"],
            mode="lines",
            name="Frecuencia",
            line=dict(color=freq_color, width=2.3),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["active_power"],
            mode="lines",
            name="Potencia activa",
            line=dict(color=power_color, width=2.3),
        ),
        secondary_y=True,
    )

    fig.update_yaxes(title_text="Frecuencia (Hz)", secondary_y=False)
    fig.update_yaxes(title_text=f"Potencia activa ({config.power_unit})", secondary_y=True)
    fig.update_xaxes(title_text="Tiempo")
    return _apply_plotly_layout(fig, config.titulo(case_result.caso))


def _build_multi_compare_figure(ok_cases: list) -> go.Figure | None:
    available = [case for case in ok_cases if getattr(case, "df", None) is not None]
    if not available:
        return None

    palette = ["#38bdf8", "#22c55e", "#f59e0b", "#a855f7", "#fb7185"]
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=["Frecuencia por caso", "Potencia activa por caso"],
    )
    for idx, case in enumerate(available):
        df = case.df.copy()
        df["time"] = pd.to_datetime(df["time"])
        elapsed = (df["time"] - df["time"].iloc[0]).dt.total_seconds() / 60.0
        color = palette[idx % len(palette)]
        fig.add_trace(
            go.Scatter(
                x=elapsed,
                y=df["frequency"],
                mode="lines",
                name=f"{case.caso} · Frecuencia",
                line=dict(color=color, width=2.1),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=elapsed,
                y=df["active_power"],
                mode="lines",
                name=f"{case.caso} · Potencia",
                line=dict(color=color, width=2.1, dash="dot"),
            ),
            row=2,
            col=1,
        )
    fig.update_yaxes(title_text="Frecuencia (Hz)", row=1, col=1)
    fig.update_yaxes(title_text="Potencia activa", row=2, col=1)
    fig.update_xaxes(title_text="Tiempo transcurrido (min)", row=2, col=1)
    return _apply_plotly_layout(fig, "Comparativo interactivo por caso", height=720)


def _build_p25_interactive_figures(result) -> list[tuple[str, go.Figure]]:
    frames = getattr(result, "frames", None) or {}
    merged = frames.get("merged")
    daily = frames.get("daily")
    if merged is None or daily is None or merged.empty:
        return []

    merged = merged.copy()
    merged["time"] = pd.to_datetime(merged["time"])
    figures: list[tuple[str, go.Figure]] = []

    fig_net = go.Figure()
    fig_net.add_trace(
        go.Scatter(x=merged["time"], y=merged["generation_mw"], mode="lines", name="P_generacion", line=dict(color="#22c55e", width=2.1))
    )
    fig_net.add_trace(
        go.Scatter(x=merged["time"], y=merged["load_mw"], mode="lines", name="P_carga", line=dict(color="#f59e0b", width=2.1))
    )
    fig_net.add_trace(
        go.Scatter(x=merged["time"], y=merged["net_injection_mw"], mode="lines", name="P_neta = P_gen - P_carga", line=dict(color="#e5e7eb", width=3.0))
    )
    fig_net.add_hline(y=0, line_dash="dash", line_color="#6b7280", line_width=1.3, annotation_text="0 MW", annotation_position="bottom right")
    fig_net.update_yaxes(title_text="Potencia (MW)")
    fig_net.update_xaxes(title_text="Tiempo")
    figures.append(("Inyeccion neta", _apply_plotly_layout(fig_net, "Inyección neta en el POI – 15 días")))

    fig_compliance = go.Figure()
    fig_compliance.add_trace(
        go.Scatter(
            x=merged["time"],
            y=merged["net_injection_mw"],
            mode="lines",
            name="P_neta = P_gen - P_carga",
            line=dict(color="#111827", width=2.6),
        )
    )
    fig_compliance.add_hline(
        y=0,
        line_dash="dash",
        line_color="#ef4444",
        line_width=1.6,
        annotation_text="0 MW",
        annotation_position="bottom right",
    )
    positive = merged[merged["net_injection_mw"] > 0]
    if not positive.empty:
        fig_compliance.add_trace(
            go.Scatter(
                x=positive["time"],
                y=positive["net_injection_mw"],
                mode="markers",
                name="Eventos > 0 MW",
                marker=dict(color="#dc2626", size=5),
            )
        )
    net_min = float(merged["net_injection_mw"].min())
    net_max = float(merged["net_injection_mw"].max())
    net_span = max(net_max - net_min, 0.01)
    y0 = min(net_min - net_span * 0.18, 0.0)
    y1 = max(net_max + net_span * 0.18, 0.05)
    fig_compliance.add_hrect(y0=y0, y1=0, fillcolor="rgba(34,197,94,0.16)", line_width=0)
    fig_compliance.add_hrect(y0=0, y1=y1, fillcolor="rgba(239,68,68,0.18)", line_width=0)
    fig_compliance.update_yaxes(title_text="Potencia neta (MW)", range=[y0, y1])
    fig_compliance.update_xaxes(title_text="Tiempo")
    figures.append(("Cumplimiento no inyeccion", _apply_plotly_layout(fig_compliance, "Cumplimiento de no inyección – P_neta ≤ 0 MW")))

    fig_freq = go.Figure()
    fig_freq.add_trace(
        go.Scatter(x=merged["time"], y=merged["frequency"], mode="lines", name="f_poi", line=dict(color="#2563eb", width=2.1))
    )
    fig_freq.add_hrect(y0=59.5, y1=60.5, fillcolor="rgba(209,213,219,0.18)", line_width=0)
    fig_freq.add_hrect(y0=59.97, y1=60.03, fillcolor="rgba(203,213,225,0.34)", line_width=0)
    fig_freq.add_hline(y=59.5, line_dash="dash", line_color="#ef4444")
    fig_freq.add_hline(y=60.5, line_dash="dash", line_color="#ef4444")
    fig_freq.add_hline(y=59.97, line_dash="dot", line_color="#f59e0b")
    fig_freq.add_hline(y=60.03, line_dash="dot", line_color="#f59e0b")
    out_deadband = merged[(merged["frequency"] < 59.97) | (merged["frequency"] > 60.03)]
    if not out_deadband.empty:
        fig_freq.add_trace(
            go.Scatter(
                x=out_deadband["time"],
                y=out_deadband["frequency"],
                mode="markers",
                name="Fuera de banda muerta",
                marker=dict(color="#ef4444", size=5),
            )
        )
    freq_values = pd.Series([*merged["frequency"].dropna(), 59.97, 60.03])
    freq_min = float(freq_values.min())
    freq_max = float(freq_values.max())
    span = max(freq_max - freq_min, 0.01)
    pad = max(span * 0.20, 0.005)
    fig_freq.update_yaxes(title_text="Frecuencia (Hz)", range=[freq_min - pad, freq_max + pad])
    fig_freq.update_xaxes(title_text="Tiempo")
    figures.append(("Frecuencia", _apply_plotly_layout(fig_freq, "Frecuencia en el POI – 15 días (Código de Red 2.0)")))

    fig_voltage = go.Figure()
    fig_voltage.add_trace(
        go.Scatter(x=merged["time"], y=merged["voltage_pu"], mode="lines", name="V_pu", line=dict(color="#2563eb", width=2.1))
    )
    fig_voltage.add_hrect(y0=0.95, y1=1.05, fillcolor="rgba(209,213,219,0.18)", line_width=0)
    fig_voltage.add_hline(y=0.95, line_dash="dash", line_color="#ef4444")
    fig_voltage.add_hline(y=1.05, line_dash="dash", line_color="#ef4444")
    out_voltage_band = merged[(merged["voltage_pu"] < 0.95) | (merged["voltage_pu"] > 1.05)]
    if not out_voltage_band.empty:
        fig_voltage.add_trace(
            go.Scatter(
                x=out_voltage_band["time"],
                y=out_voltage_band["voltage_pu"],
                mode="markers",
                name="Fuera de banda",
                marker=dict(color="#ef4444", size=5),
            )
        )
    voltage_values = pd.Series([*merged["voltage_pu"].dropna(), 0.95, 1.05])
    voltage_min = float(voltage_values.min())
    voltage_max = float(voltage_values.max())
    voltage_span = max(voltage_max - voltage_min, 0.01)
    voltage_pad = max(voltage_span * 0.15, 0.003)
    fig_voltage.update_yaxes(title_text="Voltaje (p.u.)", range=[voltage_min - voltage_pad, voltage_max + voltage_pad])
    fig_voltage.update_xaxes(title_text="Tiempo")
    figures.append(("Voltaje", _apply_plotly_layout(fig_voltage, "Voltaje en el POI – 15 días (0.95–1.05 p.u.)")))

    fig_daily = make_subplots(specs=[[{"secondary_y": True}]])
    fig_daily.add_trace(
        go.Bar(x=daily["day_label"], y=daily["energia_generada_mwh"], name="Energia generada", marker_color="#22c55e"),
        secondary_y=False,
    )
    fig_daily.add_trace(
        go.Bar(x=daily["day_label"], y=daily["energia_carga_mwh"], name="Energia carga", marker_color="#f59e0b"),
        secondary_y=False,
    )
    fig_daily.add_trace(
        go.Scatter(x=daily["day_label"], y=daily["horas_operacion_h"], mode="lines+markers", name="Horas operacion", line=dict(color="#2563eb", width=2.2)),
        secondary_y=True,
    )
    fig_daily.update_yaxes(title_text="Energia (MWh/dia)", secondary_y=False)
    fig_daily.update_yaxes(title_text="Horas operacion (h/dia)", secondary_y=True)
    fig_daily.update_xaxes(title_text="Dia")
    figures.append(("Indicadores diarios", _apply_plotly_layout(fig_daily, "Energía y disponibilidad diaria – 15 días", height=520)))

    # ── Capacidad Instalada Neta: escalas separadas para no confundir el límite 0 MW ──
    _w = 5
    net_smooth = merged["net_injection_mw"].rolling(window=_w, center=True, min_periods=1).mean()
    gen_smooth = merged["generation_mw"].rolling(window=_w, center=True, min_periods=1).mean()

    fig_cap = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.58, 0.42],
    )
    fig_cap.add_trace(
        go.Scatter(
            x=merged["time"],
            y=net_smooth,
            mode="lines",
            name="P_neta = P_gen - P_carga",
            line=dict(color="#111827", width=2.2),
        ),
        row=1,
        col=1,
    )
    fig_cap.add_hline(y=0, line_dash="dash", line_color="#ef4444", line_width=1.5, row=1, col=1, annotation_text="0 MW", annotation_position="bottom right")
    fig_cap.add_trace(
        go.Scatter(
            x=merged["time"],
            y=gen_smooth,
            mode="lines",
            name="P_generacion (MW)",
            line=dict(color="#22c55e", width=2.2),
        ),
        row=2,
        col=1,
    )
    net_min = float(net_smooth.min())
    net_max = float(net_smooth.max())
    net_span = max(net_max - net_min, 0.01)
    net_y0 = min(net_min - net_span * 0.18, 0.0)
    net_y1 = max(net_max + net_span * 0.18, 0.05)
    fig_cap.add_hrect(y0=net_y0, y1=0, fillcolor="rgba(34,197,94,0.14)", line_width=0, row=1, col=1)
    fig_cap.add_hrect(y0=0, y1=net_y1, fillcolor="rgba(239,68,68,0.18)", line_width=0, row=1, col=1)
    fig_cap.update_yaxes(title_text="Potencia neta (MW)", range=[net_y0, net_y1], row=1, col=1, title_font=dict(color="#111827"), tickfont=dict(color="#374151"))
    fig_cap.update_yaxes(title_text="Potencia de generacion (MW)", row=2, col=1, title_font=dict(color="#22c55e"), tickfont=dict(color="#22c55e"))
    fig_cap.update_xaxes(title_text="Tiempo", row=2, col=1)
    figures.append(("Capacidad Instalada Neta", _apply_plotly_layout(fig_cap, "Capacidad Instalada Neta – P25 (Centrales Asíncronas)", height=720)))

    return figures



def _build_p25_deadband_response_figure(result) -> go.Figure | None:
    frames = getattr(result, "frames", None) or {}
    merged = frames.get("merged")
    if merged is None or merged.empty or "poi_active_power_mw" not in merged.columns:
        return None

    merged = merged.copy()
    merged["time"] = pd.to_datetime(merged["time"])
    out_deadband = merged[(merged["frequency"] < 59.97) | (merged["frequency"] > 60.03)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=merged["time"],
            y=merged["frequency"],
            mode="lines",
            name="f_poi",
            line=dict(color="#2563eb", width=2.0),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=merged["time"],
            y=merged["generation_mw"],
            mode="lines",
            name="P_gen",
            line=dict(color="#22c55e", width=2.1),
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=merged["time"],
            y=merged["poi_active_power_mw"],
            mode="lines",
            name="P_poi",
            line=dict(color="#e5e7eb", width=2.1),
        ),
        secondary_y=True,
    )
    fig.add_hrect(y0=59.97, y1=60.03, fillcolor="rgba(203,213,225,0.25)", line_width=0, yref="y")
    fig.add_hline(y=59.97, line_dash="dot", line_color="#f59e0b")
    fig.add_hline(y=60.03, line_dash="dot", line_color="#f59e0b")

    if not out_deadband.empty:
        fig.add_trace(
            go.Scatter(
                x=out_deadband["time"],
                y=out_deadband["frequency"],
                mode="markers",
                name="Fuera banda muerta",
                marker=dict(color="#ef4444", size=6),
            ),
            secondary_y=False,
        )

    freq_values = pd.Series([*merged["frequency"].dropna(), 59.97, 60.03])
    freq_min = float(freq_values.min())
    freq_max = float(freq_values.max())
    span = max(freq_max - freq_min, 0.01)
    pad = max(span * 0.20, 0.005)
    fig.update_yaxes(title_text="Frecuencia (Hz)", range=[freq_min - pad, freq_max + pad], secondary_y=False)
    fig.update_yaxes(title_text="Potencia activa (MW)", secondary_y=True)
    fig.update_xaxes(title_text="Tiempo")
    return _apply_plotly_layout(fig, "Respuesta de potencia activa en GEN y POI ante salidas de banda muerta", height=560)


def _summarize_p25_deadband_events(result) -> pd.DataFrame | None:
    frames = getattr(result, "frames", None) or {}
    merged = frames.get("merged")
    if merged is None or merged.empty or "poi_active_power_mw" not in merged.columns:
        return None

    data = merged.copy().sort_values("time").reset_index(drop=True)
    data["time"] = pd.to_datetime(data["time"])
    data["out_deadband"] = (data["frequency"] < 59.97) | (data["frequency"] > 60.03)
    flagged = data[data["out_deadband"]].copy()
    if flagged.empty:
        return None

    groups = flagged["time"].diff().gt(pd.Timedelta(minutes=15)).cumsum()
    rows: list[dict[str, object]] = []
    for _, event in flagged.groupby(groups):
        first = event.iloc[0]
        last = event.iloc[-1]
        duration_min = (last["time"] - first["time"]).total_seconds() / 60.0 + 5.0
        rows.append(
            {
                "Inicio": first["time"].strftime("%Y-%m-%d %H:%M"),
                "Fin": last["time"].strftime("%Y-%m-%d %H:%M"),
                "Duracion min": round(duration_min, 1),
                "f min": round(float(event["frequency"].min()), 4),
                "f max": round(float(event["frequency"].max()), 4),
                "P_gen inicio": round(float(first["generation_mw"]), 3),
                "P_gen fin": round(float(last["generation_mw"]), 3),
                "P_poi inicio": round(float(first["poi_active_power_mw"]), 3),
                "P_poi fin": round(float(last["poi_active_power_mw"]), 3),
            }
        )
    return pd.DataFrame(rows)


def _render_evidence_gallery(
    project: dict,
    source_test_ids: list[str],
    schedule: dict,
    evidence_map: dict[str, list[Path]],
) -> None:
    with st.container():
        st.markdown('<div class="gallery-toolbar">', unsafe_allow_html=True)
        gallery_tests = [pid for pid in source_test_ids if evidence_map.get(pid)]
        test_options = ["Todas las pruebas", *gallery_tests]
        col1, col2, col3 = st.columns([1.8, 1.5, 1.5])
        with col1:
            selected_test = st.selectbox(
                "Prueba",
                test_options,
                format_func=lambda value: (
                    "Todas las pruebas con evidencia"
                    if value == "Todas las pruebas"
                    else _test_label(value)
                ),
                key=f"gallery_test_{project['slug']}",
            )
        with col2:
            selected_states = st.multiselect(
                "Estado",
                list(STATUS_META.keys()),
                default=list(STATUS_META.keys()),
                key=f"gallery_status_{project['slug']}",
            )
        with col3:
            gallery_search = st.text_input(
                "Buscar evidencia",
                placeholder="Nombre de prueba o archivo",
                key=f"gallery_search_{project['slug']}",
            ).strip().lower()
        st.markdown('</div>', unsafe_allow_html=True)

    evidence_items: list[dict] = []
    target_ids = gallery_tests if selected_test == "Todas las pruebas" else [selected_test]
    for pid in target_ids:
        entry = schedule.get(pid, _default_schedule_for_tests([pid])[pid])
        if selected_states and entry.get("estado") not in selected_states:
            continue
        test_info = _get_catalog_test(pid)
        for evidence_path in evidence_map.get(pid, []):
            if gallery_search and gallery_search not in (
                f"{test_info['nombre']} {evidence_path.name}".lower()
            ):
                continue
            evidence_items.append(
                {
                    "pid": pid,
                    "test": test_info,
                    "path": evidence_path,
                    "entry": entry,
                    "mtime": _path_mtime(evidence_path),
                }
            )

    evidence_items.sort(key=lambda item: item["mtime"], reverse=True)
    st.markdown(
        f'<div class="gallery-grid-note">{len(evidence_items)} evidencia(s) visibles con los filtros actuales.</div>',
        unsafe_allow_html=True,
    )
    if not evidence_items:
        st.info("No hay evidencias que coincidan con los filtros actuales.")
        return

    gallery_cols = st.columns(3)
    for idx, item in enumerate(evidence_items):
        status_style = _status_style(item["entry"].get("estado", "Pendiente"))
        verdict_style = _veredict_style(item["entry"].get("veredicto", ""))
        with gallery_cols[idx % 3]:
            st.markdown('<div class="evidence-card">', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="crono-card-badge badge-{status_style['slug']}">{item['entry'].get('estado', 'Pendiente')}</div>
                <div class="evidence-card-title">P{item['test']['id']:02d} · {item['test']['nombre']}</div>
                <div class="evidence-card-meta">{item['path'].name}</div>
                <div class="veredicto-{verdict_style['slug']}">{verdict_style['label']}</div>
                """,
                unsafe_allow_html=True,
            )
            _render_evidence_file(item["path"], f"gallery_download_{project['slug']}_{idx}")
            st.caption(
                f"Actualizada: {datetime.datetime.fromtimestamp(item['mtime']).strftime('%d/%m/%Y %H:%M')}"
            )
            st.markdown('</div>', unsafe_allow_html=True)


def _render_interactive_timeline(
    project: dict,
    filtered_ids: list[str],
    schedule: dict,
    evidence_map: dict[str, list[Path]],
) -> None:
    timeline_df, missing_dates, partial_dates = _build_timeline_dataframe(
        filtered_ids,
        schedule,
        evidence_map,
    )

    summary_html = (
        f"<div class='timeline-summary'><strong>{len(timeline_df)}</strong> prueba(s) con rango visible en la linea de tiempo.<br>"
        f"<strong>{partial_dates}</strong> barra(s) usan ventana minima de un dia porque solo hay una fecha capturada.</div>"
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    if not timeline_df.empty:
        fig = px.timeline(
            timeline_df,
            x_start="Inicio",
            x_end="Fin",
            y="Prueba",
            color="Estado",
            color_discrete_map={status: meta["color"] for status, meta in STATUS_META.items()},
            custom_data=["InicioLabel", "FinLabel", "Duracion", "Veredicto", "Evidencias", "Observaciones"],
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Inicio: %{customdata[0]}<br>"
                "Fin: %{customdata[1]}<br>"
                "Duracion: %{customdata[2]}<br>"
                "Veredicto: %{customdata[3]}<br>"
                "Evidencias: %{customdata[4]}<br>"
                "%{customdata[5]}<extra></extra>"
            )
        )
        _apply_plotly_layout(fig, "Linea de tiempo interactiva del cronograma", height=max(420, len(timeline_df) * 42 + 180))
        fig.update_layout(dragmode="pan")
        st.plotly_chart(fig, use_container_width=True, key=f"timeline_plot_{project['slug']}")
    else:
        st.info("Aun no hay fechas suficientes para construir la linea de tiempo.")

    if missing_dates:
        with st.expander(f"Ver {len(missing_dates)} prueba(s) sin fechas registradas", expanded=False):
            for label in missing_dates:
                st.markdown(f"- {label}")


def module_cronograma(project: dict | None):

    if not project:
        st.info("Selecciona o crea una central para comenzar.")
        return

    applicable_tests = project.get("applicable_tests", [])
    if not applicable_tests:
        st.warning("Esta central no tiene pruebas aplicables seleccionadas.")
        return

    project_slug = project["slug"]
    schedule = _load_schedule(project)
    evidence_map: dict[str, list[Path]] = {}
    evidence_highlights: list[dict] = []
    for pid in applicable_tests:
        test_info = _get_catalog_test(pid)
        evidence_files = sorted(
            _find_test_evidence(project, test_info["id"]),
            key=_path_mtime,
            reverse=True,
        )
        evidence_map[pid] = evidence_files
        if evidence_files:
            evidence_highlights.append(
                {
                    "pid": pid,
                    "test": test_info,
                    "path": evidence_files[0],
                    "count": len(evidence_files),
                    "mtime": _path_mtime(evidence_files[0]),
                }
            )
    evidence_highlights.sort(key=lambda item: item["mtime"], reverse=True)

    # ── KPI - Avance (Basado en Evidencias) ──────────────────────────────────
    search_str = st.text_input(
        "Buscar Prueba",
        value=st.session_state.get("crono_search", ""),
        placeholder="Buscar por nombre...",
        label_visibility="collapsed",
    ).lower()
    st.session_state.crono_search = search_str

    total = len(applicable_tests)
    tests_with_evidence = sum(1 for evidence_files in evidence_map.values() if evidence_files)
    pct = int((tests_with_evidence / total) * 100) if total else 0

    st.markdown(
        f"""
    <div style="width:100%; background:var(--line); border-radius:8px; height:6px; margin:12px 0; overflow:hidden;">
        <div style="width:{pct}%; background:linear-gradient(90deg, var(--primary), var(--secondary)); height:100%; border-radius:8px;"></div>
    </div>
    <p style="text-align:center; color:#64748b; font-size:0.85rem; margin:0 0 12px 0; font-weight:600;">{tests_with_evidence} de {total} pruebas con evidencia registrada ({pct}%)</p>
    """,
        unsafe_allow_html=True,
    )

    if evidence_highlights:
        st.caption(f"{len(evidence_highlights)} prueba(s) ya cuentan con evidencia.")

    # ── Registro Visual ──────────────────────────────────────────────────────
    st.markdown("<h5>Registro Visual de Análisis</h5>", unsafe_allow_html=True)
    st.caption("Resumen automático de las pruebas analizadas y sus tiempos extraídos de las gráficas.")

    table_rows = []
    filtered_ids = []
    for pid in applicable_tests:
        test_info = _get_catalog_test(pid)
        
        if search_str and search_str not in test_info["nombre"].lower():
            continue
            
        filtered_ids.append(pid)
        entry = schedule.get(pid, {})
        eff_ini, eff_ter = _effective_schedule_labels(entry)
        duracion = _format_duration_minutes(entry.get("duracion_min", ""))
        
        table_rows.append({
            "Prueba": f"P{test_info['id']:02d} — {test_info['nombre']}",
            "Inicio": eff_ini if eff_ini else "—",
            "Fin": eff_ter if eff_ter else "—",
            "Duración": duracion if duracion else "—",
            "Evidencias": len(evidence_map.get(pid, [])),
        })

    if table_rows:
        import pandas as pd
        df_schedule = pd.DataFrame(table_rows)

        _render_lab_table(df_schedule, caption="Registro visual de analisis")
    else:
        st.info("Ninguna prueba coincide con la búsqueda.")
        
    _render_schedule_export_toolbar(project, filtered_ids, schedule, evidence_map)


# ─── Análisis ──────────────────────────────────────────────────────────────────
def _colors():
    preset = st.session_state.get("graph_color_preset", "Operativo")
    if preset != "Personalizado":
        colors = GRAPH_COLOR_PRESETS.get(preset, GRAPH_COLOR_PRESETS["Operativo"])
        return colors["freq_color"], colors["power_color"]

    defaults = GRAPH_COLOR_PRESETS["Operativo"]
    return (
        st.session_state.get("graph_freq_color", defaults["freq_color"]),
        st.session_state.get("graph_power_color", defaults["power_color"]),
    )


def _active_visual_palette() -> dict:
    palette_name = st.session_state.get("visual_palette", "Índigo Laboratorio")
    return VISUAL_COLOR_PALETTES.get(
        palette_name, VISUAL_COLOR_PALETTES["Índigo Laboratorio"]
    )


def _active_series_palette() -> list[str]:
    freq_color, power_color = _colors()
    visual = _active_visual_palette()
    return [
        visual["primary"],
        visual["secondary"],
        freq_color,
        power_color,
        visual["ok"],
        visual["warning"],
        visual["danger"],
    ]


def _render_graph_style_panel() -> None:
    preset_options = [*GRAPH_COLOR_PRESETS.keys(), "Personalizado"]
    current_preset = st.session_state.get("graph_color_preset", "Operativo")
    if current_preset not in preset_options:
        current_preset = "Operativo"
    st.session_state["graph_color_preset"] = current_preset

    if current_preset != "Personalizado":
        colors = GRAPH_COLOR_PRESETS[current_preset]
        st.session_state["graph_freq_color"] = colors["freq_color"]
        st.session_state["graph_power_color"] = colors["power_color"]
    else:
        defaults = GRAPH_COLOR_PRESETS["Operativo"]
        st.session_state.setdefault("graph_freq_color", defaults["freq_color"])
        st.session_state.setdefault("graph_power_color", defaults["power_color"])

    st.markdown('<div class="advanced-shell">', unsafe_allow_html=True)
    with st.expander("Opciones avanzadas de visualizacion", expanded=False):
        selected_preset = st.radio(
            "Preset visual",
            preset_options,
            index=preset_options.index(current_preset),
            horizontal=True,
            key="graph_color_preset_radio",
        )
        if selected_preset != st.session_state.get("graph_color_preset"):
            st.session_state["graph_color_preset"] = selected_preset
            if selected_preset != "Personalizado":
                colors = GRAPH_COLOR_PRESETS[selected_preset]
                st.session_state["graph_freq_color"] = colors["freq_color"]
                st.session_state["graph_power_color"] = colors["power_color"]
            st.rerun()

        freq_color, power_color = _colors()
        description = (
            "Define manualmente los colores para frecuencia y potencia activa."
            if selected_preset == "Personalizado"
            else GRAPH_COLOR_PRESETS[selected_preset]["description"]
        )
        st.caption(description)
        st.markdown(
            f"""
            <div class="style-preview">
                <div class="style-chip"><span class="style-swatch" style="background:{freq_color};"></span>Frecuencia</div>
                <div class="style-chip"><span class="style-swatch" style="background:{power_color};"></span>Potencia activa</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.session_state["graph_freq_color"] = st.color_picker(
                "Frecuencia",
                st.session_state.get("graph_freq_color", GRAPH_COLOR_PRESETS["Operativo"]["freq_color"]),
                disabled=selected_preset != "Personalizado",
            )
        with c2:
            st.session_state["graph_power_color"] = st.color_picker(
                "Potencia activa",
                st.session_state.get("graph_power_color", GRAPH_COLOR_PRESETS["Operativo"]["power_color"]),
                disabled=selected_preset != "Personalizado",
            )
    st.markdown("</div>", unsafe_allow_html=True)


def _show_manual_analysis_template(project: dict, test_key: str) -> None:
    test_info = _get_catalog_test(test_key)
    graph_profile = _graph_profile(test_key)
    output_dir = _project_output_dir(project)
    cache_key = f"{project['slug']}_{test_key}"

    template_rows = [
        {"Campo": "Tipo de gráfica", "Valor": graph_profile.get("grafica", graph_profile.get("title", "—"))},
        {"Campo": "Uso de gráfica", "Valor": "Sí" if graph_profile.get("usar_grafica", True) else "No obligatoria"},
        {"Campo": "Eje X", "Valor": graph_profile.get("x", "Tiempo")},
        {"Campo": "Eje Y1", "Valor": graph_profile.get("y1", "—")},
        {"Campo": "Eje Y2", "Valor": graph_profile.get("y2", "—")},
        {"Campo": "Señales requeridas", "Valor": ", ".join(graph_profile.get("senales", [])) or "No aplica"},
        {"Campo": "Criterio visual", "Valor": graph_profile.get("criterio_visual", "—")},
    ]

    st.markdown('<h4>Archivos de entrada</h4>', unsafe_allow_html=True)
    upload_col1, upload_col2 = st.columns(2, gap="large")
    with upload_col1:
        source_file = st.file_uploader(
            "Archivo de mediciones",
            type=["csv", "xlsx", "xls"],
            key=f"sincrona_source_{project['slug']}_{test_key}",
        )
    with upload_col2:
        uploaded_evidence = st.file_uploader(
            "Evidencia complementaria",
            type=["csv", "xlsx", "xls", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key=f"manual_evidence_{project['slug']}_{test_key}",
        )

    source_path = None
    selected_time_col = None
    selected_signal_cols: list[str] = []
    if source_file:
        source_path = save_upload(source_file)
        try:
            raw = load_table(source_path)
            columns = [str(col) for col in raw.columns]
            detected_time = detect_time_column(columns)
            time_index = columns.index(detected_time) if detected_time in columns else 0

            c1, c2 = st.columns(2, gap="large")
            with c1:
                selected_time_col = st.selectbox(
                    "Columna de tiempo",
                    columns,
                    index=time_index,
                    key=f"sincrona_time_{project['slug']}_{test_key}",
                )

            used_cols: set[str] = {selected_time_col}
            default_signal_cols: list[str] = []
            for signal in graph_profile.get("senales", []):
                detected_col = _detect_signal_column(columns, signal, used_cols)
                if detected_col:
                    default_signal_cols.append(detected_col)
                    used_cols.add(detected_col)

            selectable_signal_cols = [col for col in columns if col != selected_time_col]
            default_signal_cols = [col for col in default_signal_cols if col in selectable_signal_cols]
            with c2:
                selected_signal_cols = st.multiselect(
                    "Columnas a graficar",
                    selectable_signal_cols,
                    default=default_signal_cols,
                    key=f"sincrona_signals_{project['slug']}_{test_key}",
                )

            with st.expander("Vista previa de datos", expanded=False):
                _render_lab_table(raw, caption="Primeros registros del archivo", max_rows=30)
        except Exception as exc:
            _show_exception("Error al leer el archivo de entrada", exc)

    btn_col, _ = st.columns([1, 3])
    run_key = f"run_sincrona_{project['slug']}_{test_key}"
    with btn_col:
        run_sync = st.button(
            f"Generar P{test_info['id']}",
            type="primary",
            use_container_width=True,
            key=run_key,
        )

    if run_sync:
        if not source_file or source_path is None:
            st.warning("Proporciona el archivo de mediciones antes de ejecutar.")
            return
        if selected_time_col is None or not selected_signal_cols:
            st.warning("Selecciona una columna de tiempo y al menos una señal para graficar.")
            return
        with st.spinner("Generando gráfica de la prueba síncrona..."):
            try:
                result = _run_sincrona_analysis(
                    project,
                    test_key,
                    source_path,
                    selected_time_col,
                    selected_signal_cols,
                )
                _autosync_schedule_from_result(project, test_key, result)
                st.session_state.setdefault("analysis_cache", {})
                st.session_state["analysis_cache"][cache_key] = {
                    "result": result,
                    "test_key": test_key,
                }
                st.success("Gráfica generada y cronograma actualizado.")
            except Exception as exc:
                _show_exception("Error al generar la gráfica", exc)

    st.markdown('<h4>Salida</h4>', unsafe_allow_html=True)
    cached = st.session_state.get("analysis_cache", {}).get(cache_key)
    if cached:
        _show_sincrona_result(cached["result"], test_key)
    else:
        st.info("La gráfica generada aparecerá aquí.")

    st.markdown('<h5>Evidencia complementaria</h5>', unsafe_allow_html=True)
    btn_col, _ = st.columns([1, 3])
    with btn_col:
        save_evidence = st.button(
            "Guardar evidencia",
            type="secondary",
            use_container_width=True,
            key=f"save_manual_evidence_{project['slug']}_{test_key}",
        )
    if save_evidence:
        if not uploaded_evidence:
            st.warning("Selecciona al menos un archivo de evidencia.")
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_paths: list[Path] = []
            for idx, uploaded_file in enumerate(uploaded_evidence, start=1):
                ext = Path(uploaded_file.name).suffix.lower()
                if ext not in EVIDENCE_EXTENSIONS:
                    st.warning(f"Se omitio {uploaded_file.name}: formato no permitido.")
                    continue
                name_token = _slugify(Path(uploaded_file.name).stem)
                evidence_path = output_dir / f"P{test_info['id']}_manual_{timestamp}_{idx}_{name_token}{ext}"
                evidence_path.write_bytes(uploaded_file.getbuffer())
                saved_paths.append(evidence_path)
            if saved_paths:
                st.success(f"Se guardaron {len(saved_paths)} archivo(s) de evidencia.")

    current_evidence = sorted(
        _find_test_evidence(project, test_info["id"]),
        key=_path_mtime,
        reverse=True,
    )
    if current_evidence:
        with st.expander(f"Ver {len(current_evidence)} evidencia(s) guardada(s)", expanded=False):
            for idx, evidence_path in enumerate(current_evidence):
                st.caption(evidence_path.name)
                _render_evidence_file(
                    evidence_path,
                    f"manual_download_{project['slug']}_{test_key}_{idx}",
                )

    with st.expander("Lineamientos de gráfica", expanded=False):
        _render_lab_table(pd.DataFrame(template_rows), caption="Lineamientos de grafica")

    st.markdown('<div class="section-label">Opciones de visualizacion</div>', unsafe_allow_html=True)
    _render_graph_style_panel()


def module_analisis(project: dict | None):

    if not project:
        st.info("Selecciona o crea una central para comenzar.")
        return

    analysis_tests = _analysis_templates_for_project(project)
    if not project.get("applicable_tests", []):
        st.warning("Esta central no tiene pruebas aplicables seleccionadas.")
        return
    if not analysis_tests:
        st.warning(
            "Este modulo aun no tiene una plantilla de ejecucion disponible para las pruebas aplicables de esta central."
        )
        return

    project_slug = project["slug"]
    output_dir = _project_output_dir(project)
    freq_color, power_color = _colors()

    # Initialize cache for analysis results
    if "analysis_cache" not in st.session_state:
        st.session_state["analysis_cache"] = {}

    options = {_test_label(test_key): test_key for test_key in analysis_tests}
    selected_label = st.selectbox(
        "Prueba a analizar",
        list(options.keys()),
        key=f"analysis_test_{project_slug}",
    )
    selected_test_key = options[selected_label]
    test_info = _get_catalog_test(selected_test_key)
    test_id = test_info.get("implemented_code")
    st.divider()
    if test_id not in REGISTRY:
        _show_manual_analysis_template(project, selected_test_key)
        return

    config = REGISTRY[test_id]

    # Cache key for this test
    cache_key = f"{project_slug}_{test_id}"

    # ── Prueba SIMPLE ──────────────────────────────────────────────────────────
    if config.tipo == "simple" and config.id == "P28":
        st.info("P28 se genera a partir de las evidencias existentes de P1, P2, P3, P8 y P9.")

        # Show cached result if exists
        if cache_key in st.session_state["analysis_cache"]:
            cached = st.session_state["analysis_cache"][cache_key]
            _show_simple_result(
                cached["result"],
                cached["config"],
                selected_test_key,
                cached["freq_color"],
                cached["power_color"],
            )
            st.info("Mostrando resultado guardado. Ejecuta de nuevo para actualizar.")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run_p28_btn = st.button(
                "Generar P28",
                type="primary",
                use_container_width=True,
            )

        if run_p28_btn:
            with st.spinner("Construyendo resumen visual de control de frecuencia…"):
                try:
                    result = run_p28_summary(config, output_dir)
                    _autosync_schedule_from_result(project, selected_test_key, result)
                    _show_simple_result(
                        result,
                        config,
                        selected_test_key,
                        freq_color,
                        power_color,
                    )
                    # Save to cache
                    st.session_state["analysis_cache"][cache_key] = {
                        "result": result,
                        "config": config,
                        "freq_color": freq_color,
                        "power_color": power_color,
                    }
                except Exception as e:
                    _show_exception("Error", e)

    elif config.tipo == "simple" and config.id == "P25":
        st.markdown('<h4>Archivos de entrada</h4>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3, gap="large")
        with c1:
            poi_file = st.file_uploader(
                "Archivo POI",
                type=["csv", "xlsx", "xls"],
                key=f"poi_p25_{project_slug}",
            )
        with c2:
            gen_file = st.file_uploader(
                "Archivo Generación",
                type=["csv", "xlsx", "xls"],
                key=f"gen_p25_{project_slug}",
            )
        with c3:
            load_file = st.file_uploader(
                "Archivo Carga",
                type=["csv", "xlsx", "xls"],
                key=f"load_p25_{project_slug}",
            )

        # Show cached result if exists
        if cache_key in st.session_state["analysis_cache"]:
            cached = st.session_state["analysis_cache"][cache_key]
            _show_p25_result(cached["result"], cached["config"], selected_test_key)
            st.info("Mostrando resultado guardado. Ejecuta de nuevo para actualizar.")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run_p25_btn = st.button(
                "Generar P25",
                type="primary",
                use_container_width=True,
            )

        if run_p25_btn:
            if not poi_file or not gen_file or not load_file:
                st.warning("Proporciona los tres archivos antes de ejecutar P25.")
                return
            poi_path = save_upload(poi_file)
            gen_path = save_upload(gen_file)
            load_path = save_upload(load_file)
            with st.spinner("Alineando POI, generación y carga para generar las 5 gráficas..."):
                try:
                    result = run_p25(config, poi_path, gen_path, load_path, output_dir)
                    _autosync_schedule_from_result(project, selected_test_key, result)
                    _show_p25_result(result, config, selected_test_key)
                    # Save to cache
                    st.session_state["analysis_cache"][cache_key] = {
                        "result": result,
                        "config": config,
                    }
                except Exception as e:
                    _show_exception("Error", e)

    elif config.tipo == "simple":
        st.markdown('<h4>Archivos de entrada</h4>', unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="large")
        with c1:
            poi_file = st.file_uploader(
                "Archivo POI / FREC",
                type=["csv", "xlsx", "xls"],
                key=f"poi_simple_{project_slug}_{test_id}",
            )
        with c2:
            gen_file = st.file_uploader(
                "Archivo GEN",
                type=["xlsx", "xls"],
                key=f"gen_simple_{project_slug}_{test_id}",
            )

        # Show cached result if exists
        if cache_key in st.session_state["analysis_cache"]:
            cached = st.session_state["analysis_cache"][cache_key]
            _show_simple_result(
                cached["result"],
                cached["config"],
                selected_test_key,
                cached["freq_color"],
                cached["power_color"],
            )
            st.info("Mostrando resultado guardado. Ejecuta de nuevo para actualizar.")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run = st.button(
                f"Generar {test_id}", type="primary", use_container_width=True
            )

        if run:
            if not poi_file or not gen_file:
                st.warning("Proporciona ambos archivos antes de ejecutar.")
                return
            poi_path = save_upload(poi_file)
            gen_path = save_upload(gen_file)
            with st.spinner("Empatando tiempos y generando gráfica…"):
                try:
                    result = run_simple(
                        config,
                        poi_path,
                        gen_path,
                        output_dir,
                        test_info["id"],
                        freq_color,
                        power_color,
                    )
                    _autosync_schedule_from_result(project, selected_test_key, result)
                    _show_simple_result(
                        result,
                        config,
                        selected_test_key,
                        freq_color,
                        power_color,
                    )
                    # Save to cache
                    st.session_state["analysis_cache"][cache_key] = {
                        "result": result,
                        "config": config,
                        "freq_color": freq_color,
                        "power_color": power_color,
                    }
                except Exception as e:
                    _show_exception("Error", e)

    # ── Prueba MULTI ───────────────────────────────────────────────────────────
    else:
        st.markdown(
            f"""
        <div style="background:#eef4f8; border:1px solid #d7e2ea;
                    border-radius:8px; padding:10px 12px; margin-bottom:12px; color:#475569;">
            {len(config.casos)} caso(s): {", ".join(config.casos)}
        </div>
        """,
            unsafe_allow_html=True,
        )

        file_pairs_raw: list[tuple[str, object, object]] = []
        for caso in config.casos:
            safe = caso.replace("%", "pct")
            st.markdown(
                f"""
            <div class="caso-block">
                <div class="caso-label">
                    <span class="caso-badge">{caso}</span> Caso {caso}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
            cc1, cc2 = st.columns(2, gap="large")
            with cc1:
                f_frec = st.file_uploader(
                    f"FREC · {caso}",
                    type=["csv", "xlsx", "xls"],
                    key=f"frec_{project_slug}_{test_id}_{safe}",
                )
            with cc2:
                f_gen = st.file_uploader(
                    f"GEN · {caso}",
                    type=["xlsx", "xls"],
                    key=f"gen_{project_slug}_{test_id}_{safe}",
                )
            file_pairs_raw.append((caso, f_frec, f_gen))

         
        # Show cached result if exists
        if cache_key in st.session_state["analysis_cache"]:
            cached = st.session_state["analysis_cache"][cache_key]
            is_zones_cached = cached["config"].id.endswith("Z")
            if is_zones_cached:
                _show_zones_result(
                    cached["result"],
                    cached["config"],
                    selected_test_key,
                )
            else:
                _show_multi_result(
                    cached["result"],
                    cached["config"],
                    selected_test_key,
                    cached["freq_color"],
                    cached["power_color"],
                )
            st.info("Mostrando resultado guardado. Ejecuta de nuevo para actualizar.")
         
        btn_col2, _ = st.columns([1, 3])
        with btn_col2:
            run_m = st.button(
                f"Generar {test_id}", type="primary", use_container_width=True
            )

        if run_m:
            ready = [(c, f, g) for c, f, g in file_pairs_raw if f and g]
            if not ready:
                st.warning("Carga al menos un par de archivos FREC y GEN.")
                return
            pairs = [(c, save_upload(f), save_upload(g)) for c, f, g in ready]
            with st.spinner(f"Procesando {len(pairs)} caso(s)…"):
                try:
                    is_zones = config.id.endswith("Z")
                    if is_zones:
                        result = run_zones_multi(
                            config.id, pairs, output_dir, freq_color, power_color
                        )
                    else:
                        result = run_multi(
                            config, pairs, output_dir, freq_color, power_color
                        )
                    if result.successful:
                        _autosync_schedule_from_result(project, selected_test_key, result)
                    if is_zones:
                        _show_zones_result(
                            result,
                            config,
                            selected_test_key,
                        )
                    else:
                        _show_multi_result(
                            result,
                            config,
                            selected_test_key,
                            freq_color,
                            power_color,
                        )
                except Exception as e:
                    _show_exception("Error", e)

    st.markdown('<div class="section-label">Opciones de visualizacion</div>', unsafe_allow_html=True)
    _render_graph_style_panel()


def _show_p25_result(result, config, test_key: str):
    st.success(f"P25 procesada · {result.row_count:,} registros alineados")
    st.divider()

    figures = _build_p25_interactive_figures(result)
    if figures:
        chart_tabs = st.tabs([label for label, _ in figures])
        for idx, (label, fig) in enumerate(figures):
            with chart_tabs[idx]:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"plotly_p25_{idx}",
                )
    else:
        st.info("No fue posible construir las vistas interactivas de P25.")

    image_paths = getattr(result, "output_paths", None) or []
    deadband_fig = _build_p25_deadband_response_figure(result)
    deadband_table = _summarize_p25_deadband_events(result)

    if deadband_fig is not None:
        with st.expander("Respuesta GEN/POI ante banda muerta", expanded=False):
            st.plotly_chart(deadband_fig, use_container_width=True, key="plotly_p25_deadband_response")
            if deadband_table is not None and not deadband_table.empty:
                _render_lab_table(deadband_table, caption="Eventos fuera de banda muerta")

    if image_paths:
        merged_frame = (getattr(result, "frames", None) or {}).get("merged")
        zip_name = artifact_filename(
            image_paths[0],
            descriptor="graficas_15_dias",
            ext=".zip",
            test_id=config.id,
            date_label=dataframe_date_label(merged_frame),
        )
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for image_path in image_paths:
                if image_path.exists():
                    zf.write(image_path, image_path.name)
        zip_buf.seek(0)
        st.download_button(
            "Descargar ZIP",
            data=zip_buf.read(),
            file_name=zip_name,
            mime="application/zip",
            key="dl_p25_zip",
        )

    with st.expander("Ver PNG exportados", expanded=False):
        png_cols = st.columns(2)
        for idx, image_path in enumerate(image_paths):
            with png_cols[idx % 2]:
                if image_path.exists():
                    st.image(str(image_path), use_container_width=True, caption=image_path.name)

    with st.expander("Ver resumen tecnico", expanded=False):
        st.markdown(
            _technical_summary_html(
                test_key,
                config.conclusion,
                "Alcance de la corrida",
                "Se generaron 5 gráficas para 15 días usando POI, generación y carga alineados por timestamp.",
            ),
            unsafe_allow_html=True,
        )


def _show_simple_result(result, config, test_key: str, freq_color: str, power_color: str):
    st.success(f"Gráfica generada · {result.row_count:,} registros procesados")
    st.divider()

    fig = _build_simple_interactive_figure(
        result,
        config,
        test_key,
        freq_color,
        power_color,
    )
    if fig is not None:
        st.markdown('<div class="plot-panel">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, key=f"plotly_simple_{config.id}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No fue posible construir la vista interactiva para esta corrida.")

    if result.output_path.exists():
        with open(result.output_path, "rb") as fh:
            st.download_button(
                "Descargar PNG",
                data=fh.read(),
                file_name=result.output_path.name,
                mime="image/png",
                key="dl_simple",
            )

    with st.expander("Ver PNG exportado", expanded=False):
        if result.output_path.exists():
            st.image(str(result.output_path), use_container_width=True)

    extra_paths = [
        path
        for path in (getattr(result, "output_paths", None) or [])
        if path != result.output_path
    ]
    if extra_paths:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if result.output_path.exists():
                zf.write(result.output_path, result.output_path.name)
            for image_path in extra_paths:
                if image_path.exists():
                    zf.write(image_path, image_path.name)
        zip_buf.seek(0)
        st.download_button(
            "Descargar evidencias P28",
            data=zip_buf.read(),
            file_name=f"{config.id}_evidencias_control_frecuencia.zip",
            mime="application/zip",
            key=f"dl_simple_extra_{config.id}",
        )

        with st.expander("Comparativos de estatismos P28", expanded=True):
            cols = st.columns(3)
            for idx, image_path in enumerate(extra_paths):
                with cols[idx % 3]:
                    if image_path.exists():
                        st.image(str(image_path), use_container_width=True, caption=image_path.name)
                        with open(image_path, "rb") as fh:
                            st.download_button(
                                "Descargar PNG",
                                data=fh.read(),
                                file_name=image_path.name,
                                mime="image/png",
                                key=f"dl_p28_extra_{idx}",
                            )

    with st.expander("Ver resumen tecnico", expanded=False):
        st.markdown(
            _technical_summary_html(test_key, config.conclusion),
            unsafe_allow_html=True,
        )


def _show_multi_result(result, config, test_key: str, freq_color: str, power_color: str):
    if result.errors:
        for err in result.errors:
            st.error(err)

    ok = result.successful
    if not ok:
        st.error("No se generó ninguna gráfica.")
        return

    st.success(f"{len(ok)} gráfica(s) generada(s)")
    st.divider()

    compare_fig = _build_multi_compare_figure(ok)
    if compare_fig is not None:
        st.markdown('<div class="plot-panel">', unsafe_allow_html=True)
        st.plotly_chart(compare_fig, use_container_width=True, key=f"plotly_multi_compare_{config.id}")
        st.markdown('</div>', unsafe_allow_html=True)

    case_tabs = st.tabs([f"Caso {case_result.caso}" for case_result in ok])
    for idx, case_result in enumerate(ok):
        with case_tabs[idx]:
            fig = _build_multi_case_interactive_figure(
                case_result,
                config,
                freq_color,
                power_color,
            )
            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"plotly_multi_case_{config.id}_{case_result.caso}",
                )
            else:
                st.info(f"Sin datos interactivos disponibles para el caso {case_result.caso}.")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cr in ok:
            if cr.output_path.exists():
                zf.write(cr.output_path, cr.output_path.name)
        if result.summary_xlsx and result.summary_xlsx.exists():
            zf.write(result.summary_xlsx, result.summary_xlsx.name)
    zip_buf.seek(0)
    zip_name = artifact_filename(
        ok[0].output_path if ok else config.id,
        descriptor="resultados",
        ext=".zip",
        test_id=config.id,
        date_label=dataframe_date_label(ok[0].df if ok else None),
    )

    st.download_button(
        f"Descargar ZIP · {len(ok)} gráfica(s)",
        data=zip_buf.read(),
        file_name=zip_name,
        mime="application/zip",
        key="dl_multi_zip",
    )

    with st.expander("Ver PNG exportado", expanded=False):
        cols = st.columns(min(len(ok), 2))
        for i, case_result in enumerate(ok):
            with cols[i % 2]:
                if case_result.output_path.exists():
                    st.image(
                        str(case_result.output_path),
                        caption=f"Caso {case_result.caso}",
                        use_container_width=True,
                    )

    with st.expander("Ver resumen tecnico", expanded=False):
        if result.summary_xlsx and result.summary_xlsx.exists():
            st.markdown("#### Resumen de estados de frecuencia")
            try:
                df_sum = pd.read_excel(result.summary_xlsx)
                _render_lab_table(df_sum, caption="Resumen de estados de frecuencia", max_rows=60)
            except Exception:
                pass

        st.markdown(
            _technical_summary_html(test_key, config.conclusion),
            unsafe_allow_html=True,
        )


def _show_zones_result(result, config, test_key: str):
    """Muestra resultados de pruebas con zonas esperadas (P3Z, P8Z, P9Z)."""
    if result.errors:
        for err in result.errors:
            st.error(err)

    ok = result.successful
    if not ok:
        st.error("No se genero ninguna grafica con zonas.")
        return

    st.success(f"{len(ok)} grafica(s) con zonas generada(s)")
    st.divider()

    # Graficas PNG primero (visibles inmediatamente)
    st.markdown('<div class="section-label">Graficas con zonas esperadas</div>', unsafe_allow_html=True)
    cols = st.columns(min(len(ok), 3))
    for i, case in enumerate(ok):
        with cols[i % 3]:
            if case.output_path.exists():
                st.image(
                    str(case.output_path),
                    caption=f"{case.caso} (S={int(case.estatismo_pct*100)}%)",
                    use_container_width=True,
                )
                with open(case.output_path, "rb") as fh:
                    st.download_button(
                        "Descargar PNG",
                        data=fh.read(),
                        file_name=case.output_path.name,
                        mime="image/png",
                        key=f"dl_zone_png_{i}_{test_key}",
                    )

    # Tabla de evaluacion por caso
    st.markdown('<div class="section-label">Resumen de evaluacion por estatismo</div>', unsafe_allow_html=True)

    eval_rows = []
    for case in ok:
        eval_rows.append(
            {
                "Caso": case.caso,
                "Estatismo": f"{int(case.estatismo_pct * 100)}%",
                "P_op (MW)": case.p_op,
                "P_ref (MW)": case.p_ref,
                "Error promedio (%)": case.error_pct if case.error_pct else "N/A",
                "Semaforo": case.semaforo,
                "Registros": case.row_count,
            }
        )
    eval_df = pd.DataFrame(eval_rows)
    _render_lab_table(eval_df, caption="Evaluacion por estatismo")

    # Excel resumen
    if result.summary_xlsx and result.summary_xlsx.exists():
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for cr in ok:
                if cr.output_path.exists():
                    zf.write(cr.output_path, cr.output_path.name)
            zf.write(result.summary_xlsx, result.summary_xlsx.name)
        zip_buf.seek(0)
        zip_name = artifact_filename(
            ok[0].output_path if ok else config.id,
            descriptor="resultados_zonas",
            ext=".zip",
            test_id=config.id,
            date_label=dataframe_date_label(ok[0].df if ok else None),
        )
        st.download_button(
            f"Descargar ZIP · {len(ok)} gráfica(s)",
            data=zip_buf.read(),
            file_name=zip_name,
            mime="application/zip",
            key="dl_zones_zip",
        )

    with st.expander("Ver resumen tecnico", expanded=False):
        st.markdown(
            _technical_summary_html(test_key, config.conclusion),
            unsafe_allow_html=True,
        )


# ─── Depuracion
def module_depuracion(project: dict | None):

    if not project:
        st.info("Selecciona o crea una central para comenzar.")
        return

    project_slug = project["slug"]
    out_dir = _project_depur_dir(project)

    st.markdown('<h4>Archivos Fuente (Día Completo)</h4>', unsafe_allow_html=True)
    st.caption('Archivos fuente en Excel o CSV con columna de tiempo utilizable')
    c1, c2 = st.columns(2, gap="large")
    with c1:
        poi_day = st.file_uploader(
            "Archivo POI / PPC — Día completo",
            type=["xlsx", "xls", "csv", "cvs"],
            key=f"depur_poi_{project_slug}",
        )
        if poi_day:
            st.caption(f"Archivo seleccionado: {poi_day.name} · {poi_day.size / 1024 / 1024:.1f} MB")
    with c2:
        gen_day = st.file_uploader(
            "Archivo GEN — Día completo",
            type=["xlsx", "xls", "csv", "cvs"],
            key=f"depur_gen_{project_slug}",
        )
        if gen_day:
            st.caption(f"Archivo seleccionado: {gen_day.name} · {gen_day.size / 1024 / 1024:.1f} MB")
    st.divider()

    if poi_day and gen_day:
        st.markdown('<h4>Ventanas de Tiempo a Recortar</h4>', unsafe_allow_html=True)
        num_jobs = st.number_input(
            "Cantidad de recortes", min_value=1, max_value=30, value=1, step=1
        )

        jobs_raw = []
        for i in range(int(num_jobs)):
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#0284c7,#0ea5e9);color:white;font-size:0.72rem;font-weight:700;padding:3px 10px;border-radius:100px;display:inline-block;margin-bottom:10px;">Corte {i + 1}</div>',
                unsafe_allow_html=True,
            )
            j1, j2, j3 = st.columns([1.2, 1.5, 1.5], gap="medium")
            with j1:
                base = st.text_input(
                    "Prefijo de salida",
                    placeholder="P1_OVER_",
                    key=f"base_{project_slug}_{i}",
                )
            with j2:
                ini = st.text_input(
                    "Inicio (MM/DD/YYYY HH:MM:SS:ms)",
                    value="04/01/2026 12:43:01:536",
                    key=f"ini_{project_slug}_{i}",
                )
            with j3:
                fin = st.text_input(
                    "Fin   (MM/DD/YYYY HH:MM:SS:ms)",
                    value="04/01/2026 12:45:31:437",
                    key=f"fin_{project_slug}_{i}",
                )
            if base and ini and fin:
                jobs_raw.append(CutJob(base_name=base, start_text=ini, end_text=fin))

        btn_col3, _ = st.columns([1, 3])
        with btn_col3:
            run_d = st.button(
                "Depurar", type="primary", use_container_width=True
            )

        if run_d:
            if not jobs_raw:
                st.warning("Define al menos un corte con prefijo, inicio y fin.")
                return
            poi_path = save_upload(poi_day)
            gen_path = save_upload(gen_day)
            try:
                with st.spinner(
                    "Cargando archivos fuente (puede tardar unos instantes)…"
                ):
                    sources = load_sources(poi_path, gen_path)
                resultado_paths: list[Path] = []
                for job in jobs_raw:
                    with st.spinner(f"Procesando: {job.base_name}"):
                        paths = run_cut_job(job, sources, out_dir)
                        resultado_paths.extend(paths)
                st.success(
                    f"{len(resultado_paths)} archivo(s) exportado(s) en `projects/{project['slug']}/DEPUR/SALIDAS/`"
                )
                for p in resultado_paths:
                    st.markdown(f"- `{p.name}`")
                # Botón de descarga ZIP
                zip_buf2 = io.BytesIO()
                with zipfile.ZipFile(zip_buf2, "w", zipfile.ZIP_DEFLATED) as zf:
                    for p in resultado_paths:
                        if p.exists():
                            zf.write(p, p.name)
                zip_buf2.seek(0)
                st.download_button(
                    "Descargar ZIP recortes",
                    data=zip_buf2.read(),
                    file_name=artifact_filename(
                        out_dir,
                        descriptor="recortes_depurados",
                        ext=".zip",
                        date_label=datetime.datetime.now().strftime("%Y%m%d"),
                    ),
                    mime="application/zip",
                    key="dl_depur_zip",
                )
            except Exception as e:
                _show_exception("Error durante la depuración", e)


# ─── Top Panel ─────────────────────────────────────────────────────────────────
def render_brand_banner() -> None:
    return None


def _inject_visual_palette(palette_name: str) -> None:
    palette = VISUAL_COLOR_PALETTES.get(
        palette_name, VISUAL_COLOR_PALETTES["Índigo Laboratorio"]
    )
    st.markdown(
        f"""
        <style>
        :root {{
            --bg: {palette["bg"]};
            --surface: {palette["surface"]};
            --surface-soft: {palette["surface_soft"]};
            --surface-tint: {palette["surface_tint"]};
            --ink: {palette["ink"]};
            --muted: {palette["muted"]};
            --line: {palette["line"]};
            --line-strong: {palette["line_strong"]};
            --primary: {palette["primary"]};
            --primary-strong: {palette["primary_strong"]};
            --secondary: {palette["secondary"]};
            --warning: {palette["warning"]};
            --danger: {palette["danger"]};
            --ok: {palette["ok"]};
            --sidebar: {palette["sidebar"]};
            --sidebar-end: {palette["sidebar_end"]};
        }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {palette["sidebar"]} 0%, {palette["sidebar_end"]} 100%) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_panel() -> tuple[str, dict | None]:
    projects = _list_projects()
    project_map = {project["slug"]: project for project in projects}

    selected_palette = st.sidebar.selectbox(
        "Paleta visual",
        list(VISUAL_COLOR_PALETTES.keys()),
        index=list(VISUAL_COLOR_PALETTES.keys()).index(
            st.session_state.get("visual_palette", "Índigo Laboratorio")
        )
        if st.session_state.get("visual_palette", "Índigo Laboratorio")
        in VISUAL_COLOR_PALETTES
        else 0,
        key="visual_palette",
    )
    _inject_visual_palette(selected_palette)

    st.sidebar.markdown(
        """
        <div style="display:flex; align-items:center; gap:12px; margin-bottom: 24px;">
            <div style="width:36px; height:36px; background:var(--primary); border-radius:8px; display:flex; align-items:center; justify-content:center; color:#fff;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            </div>
            <div style="font-weight:800; font-size:1.15rem; color:#fff; line-height:1.2;">Código de Red<br><span style="font-size:0.8rem; color:#a9c3cf; font-weight:600;">Panel Técnico</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mode = st.sidebar.radio(
        "Navegación",
        ["Dashboard", "Cronograma", "Análisis de Pruebas", "Depuración"],
        key="top_mode_selector",
    )

    st.sidebar.divider()

    project_options = ["__new__", *project_map.keys()]
    active_slug = st.session_state.get("_active_project_slug", "__new__")
    if active_slug not in project_options:
        active_slug = "__new__"
        st.session_state["_active_project_slug"] = active_slug

    selected_slug = st.sidebar.selectbox(
        "Central",
        project_options,
        index=project_options.index(active_slug),
        format_func=lambda slug: (
            "Crear nueva central" if slug == "__new__" else _project_label(project_map[slug])
        ),
        key="sidebar_project_selector",
    )
    if selected_slug != st.session_state.get("_active_project_slug"):
        st.session_state["_active_project_slug"] = selected_slug
        st.rerun()

    active_slug = st.session_state.get("_active_project_slug", "__new__")
    active_project = project_map.get(active_slug)

    return mode, active_project


def module_dashboard(project_map: dict):
    st.markdown('<h4>Selección y Configuración de Central</h4>', unsafe_allow_html=True)

    project_options = ["__new__", *project_map.keys()]
    selected_project_slug = st.session_state.get("_active_project_slug", "__new__")
    if selected_project_slug not in project_options:
        selected_project_slug = "__new__"
        st.session_state["_active_project_slug"] = selected_project_slug

    project = project_map.get(selected_project_slug)
    is_new = selected_project_slug == "__new__"
    
    st.divider()

    if is_new:
        st.markdown('<h5>Crear Nueva Central</h5>', unsafe_allow_html=True)
        central_name_value = ""
        central_kind_value = "asincrona"
        central_class_value = "A"
    else:
        st.markdown(f'<h5>{_project_label(project)}</h5>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="display:flex; gap:16px; margin-bottom:16px;">
                <div style="background:#eef4f8; border:1px solid #d7e2ea; border-radius:8px; padding:10px 16px;">
                    <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700;">Familia</div>
                    <div style="font-size:1rem; color:#102033; font-weight:600;">{_project_family_label(project)}</div>
                </div>
                <div style="background:#eef4f8; border:1px solid #d7e2ea; border-radius:8px; padding:10px 16px;">
                    <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700;">Tipo</div>
                    <div style="font-size:1rem; color:#102033; font-weight:600;">Clase {project['central_class']}</div>
                </div>
                <div style="background:#eef4f8; border:1px solid #d7e2ea; border-radius:8px; padding:10px 16px;">
                    <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700;">Pruebas</div>
                    <div style="font-size:1rem; color:#102033; font-weight:600;">{len(project.get('applicable_tests', []))}</div>
                </div>
            </div>
            """, unsafe_allow_html=True
        )
        central_name_value = project.get("central_name", "")
        central_kind_value = project.get("central_kind", "asincrona")
        central_class_value = project.get("central_class", "A")

    central_kind_options = list(CENTRAL_CATALOGS)
    central_class_options = ["A", "B", "C", "D"]

    if is_new:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            central_name = st.text_input(
                "Nombre de la Central",
                value=central_name_value,
                key="cfg_central_name",
                placeholder="Ej. Solar Trane",
            )
        with c2:
            central_kind = st.selectbox(
                "Familia",
                central_kind_options,
                index=central_kind_options.index(central_kind_value),
                format_func=lambda item: CENTRAL_CATALOGS[item]["nombre"],
                key="cfg_central_kind",
            )
        with c3:
            central_class = st.selectbox(
                "Tipo",
                central_class_options,
                index=central_class_options.index(central_class_value) if central_class_value in central_class_options else 0,
                key="cfg_central_class",
            )
    else:
        central_name = project.get("central_name", "")
        central_kind = project.get("central_kind", "asincrona")
        central_class = project.get("central_class", "A")

    eligible_tests = _eligible_tests(central_kind, central_class)
    default_applicable = (
        _normalize_test_ids(project.get("applicable_tests", []), central_kind, central_class)
        if project else eligible_tests
    )
    
    num_assigned = len(default_applicable)
    num_total = len(eligible_tests)
    
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; border:1px solid #d7e2ea; border-radius:8px; padding:16px; margin-top:16px; margin-bottom:12px; box-shadow:0 8px 24px rgba(15,32,51,0.05);">
            <div>
                <div style="font-size:0.85rem; color:#64748b; font-weight:700; text-transform:uppercase;">Pruebas Activas</div>
                <div style="font-size:1.1rem; color:#102033; font-weight:600;">{num_assigned} de {num_total} pruebas seleccionadas</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:1.8rem; font-weight:800; color:var(--primary);">{num_assigned}</div>
            </div>
        </div>
        """, unsafe_allow_html=True
    )

    st.markdown("### Gestión de Pruebas")
    st.markdown("<p style='font-size:0.9rem; color:#64748b; margin-bottom:16px;'>Desmarca las pruebas que <strong style='color:#dc2626;'>NO</strong> aplican a esta central.</p>", unsafe_allow_html=True)
    
    NIVEL_LABELS = {"unidad": "Unidad", "central": "Central", "operacion_desempeno": "Operación / Desempeño"}
    NIVEL_ORDER = {"unidad": 0, "central": 1, "operacion_desempeno": 2}
    FAMILIA_LABELS = {
        "control_tension_avr": "Control de Tensión (AVR)",
        "control_velocidad_gobernador": "Control de Velocidad (Gobernador)",
        "frecuencia_potencia_activa": "Frecuencia / Potencia Activa",
        "tension_reactivos_poi": "Tensión / Reactivos (POI)",
        "restauracion_operacion_especial": "Restauración / Operación Especial",
        "administracion_sen": "Administración del SEN",
        "modelos_simulacion": "Modelos de Simulación",
        "desempeno_operativo": "Desempeño Operativo",
        "calidad_potencia": "Calidad de la Potencia",
    }
    FAMILIA_ORDER = {k: i for i, k in enumerate(FAMILIA_LABELS)}

    import pandas as pd
    test_rows = []
    for test_id in eligible_tests:
        parts = test_id.split(":", 1)
        test_num = int(parts[1]) if len(parts) > 1 else 0
        test_info = CATALOG_BY_KEY.get(central_kind, {}).get(test_id, {})
        name = test_info.get("nombre", test_id)
        nivel_raw = test_info.get("nivel", "")
        familia_raw = test_info.get("familia", "")
        nivel_label = NIVEL_LABELS.get(nivel_raw, nivel_raw)
        familia_label = FAMILIA_LABELS.get(familia_raw, familia_raw)
        is_active = test_id in default_applicable
        test_rows.append({
            "_test_id": test_id,
            "Activa": is_active,
            "Nivel": nivel_label,
            "Familia": familia_label,
            "Prueba": f"P{test_num:02d} · {name}",
            "Nombre": name,
            "_nivel_order": NIVEL_ORDER.get(nivel_raw, 99),
            "_familia_order": FAMILIA_ORDER.get(familia_raw, 99),
            "_test_num": test_num,
        })

    test_rows.sort(key=lambda r: (r["_nivel_order"], r["_familia_order"], r["_test_num"]))

    applicable_tests = []
    selector_scope = selected_project_slug if selected_project_slug != "__new__" else f"new_{central_kind}_{central_class}"
    grouped_rows: list[tuple[str, list[dict]]] = []
    for row in test_rows:
        group_label = f"{row['Nivel']} · {row['Familia']}" if row["Familia"] else row["Nivel"]
        if not grouped_rows or grouped_rows[-1][0] != group_label:
            grouped_rows.append((group_label, []))
        grouped_rows[-1][1].append(row)

    for group_label, rows in grouped_rows:
        st.markdown(
            f'<div class="test-selector-group">{_html_text(group_label)}</div>',
            unsafe_allow_html=True,
        )
        for start in range(0, len(rows), 2):
            pair = rows[start : start + 2]
            cols = st.columns(2, gap="medium")
            for col, row in zip(cols, pair):
                with col:
                    check_col, info_col = st.columns([0.22, 3.78], gap="small")
                    checkbox_key = f"test_active_{selector_scope}_{row['_test_id']}"
                    with check_col:
                        active = st.checkbox(
                            "Activa",
                            value=row["Activa"],
                            key=checkbox_key,
                            label_visibility="collapsed",
                        )
                    with info_col:
                        st.markdown(
                            f"""
                            <div class="test-row-shell">
                                <div class="test-row-title">{_html_text(row["Prueba"])}</div>
                                <div class="test-row-meta">{_html_text(row["Nivel"])} · {_html_text(row["Familia"])}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    if active:
                        applicable_tests.append(row["_test_id"])

    st.caption(f"{len(applicable_tests)} de {num_total} pruebas quedaran activas al guardar.")
    
    save_label = "Crear nueva central" if is_new else "Guardar cambios"
    if st.button(save_label, type="primary"):
        if is_new:
            clean_central_name = central_name.strip()
            if not clean_central_name:
                st.warning("Captura el nombre.")
                return
        else:
            clean_central_name = project.get("central_name", "")
            
        if not applicable_tests:
            st.warning("Selecciona al menos una prueba.")
            return
            
        slug = project["slug"] if project else _next_project_slug(_slugify(clean_central_name))
        saved_project = _save_project_metadata(slug, clean_central_name, central_kind, central_class, applicable_tests)
        st.session_state["_active_project_slug"] = saved_project["slug"]
        st.success("Guardado exitosamente.")
        st.rerun()

    if project_map:
        st.divider()
        st.markdown('<h5>Resumen de Centrales Registradas</h5>', unsafe_allow_html=True)
        import pandas as pd
        df_rows = []
        for slug, p in project_map.items():
            df_rows.append({
                "Nombre": p.get("central_name", slug),
                "Familia": _project_family_label(p),
                "Tipo": p.get("central_class", "N/A"),
                "Pruebas": len(p.get("applicable_tests", [])),
            })
        _render_lab_table(pd.DataFrame(df_rows), caption="Centrales registradas")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode, project = render_top_panel()
    projects = _list_projects()
    project_map = {p["slug"]: p for p in projects}

    _mode_svgs = {
        "Dashboard": '<svg style="vertical-align: middle; margin-right: 8px;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>',
        "Cronograma": '<svg style="vertical-align: middle; margin-right: 8px;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
        "Análisis de Pruebas": '<svg style="vertical-align: middle; margin-right: 8px;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>',
        "Depuración": '<svg style="vertical-align: middle; margin-right: 8px;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 9.36l-7.1 7.1a1 1 0 0 1-1.41-1.41l7.1-7.1a6 6 0 0 1 9.36-7.94l-3.77 3.77a1 1 0 0 0 0 1.41z"></path></svg>'
    }

    if project and mode != "Dashboard":
        st.markdown(
            f"""
            <div style="display:flex; align-items:flex-end; justify-content:space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #d7e2ea;">
                <h2 style="margin:0; font-size:1.8rem; font-weight:800; color:#102033; letter-spacing:0;">
                    {_mode_svgs.get(mode, '')}
                    {mode}
                </h2>
                <div style="text-align:right; font-size:0.95rem; color:#64748b; line-height:1.4;">
                    <strong style="color:#102033; font-size:1.1rem;">{_project_label(project)}</strong><br>
                    {_project_family_label(project)} · Tipo {project['central_class']}
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(f'<h2 style="margin:0 0 24px 0; font-size:1.8rem; font-weight:800; color:#102033; padding-bottom: 16px; border-bottom: 1px solid #d7e2ea;">{_mode_svgs.get(mode, "")} {mode}</h2>', unsafe_allow_html=True)
        if mode != "Dashboard" and not project:
            st.info("Selecciona una central en el sidebar o configura una nueva en el Dashboard para comenzar.")

    if mode == "Dashboard":
        module_dashboard(project_map)
    elif mode == "Cronograma":
        module_cronograma(project)
    elif mode == "Análisis de Pruebas":
        module_analisis(project)
    else:
        module_depuracion(project)


if __name__ == "__main__":
    main()
