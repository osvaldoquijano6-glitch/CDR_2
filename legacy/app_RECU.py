"""
Aplicación Profesional de Análisis de Pruebas — Código de Red / Anexo 5
Herramienta para análisis normativo de Centrales Eléctricas.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import traceback
import zipfile
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
from core.naming import artifact_filename, dataframe_date_label, project_token

PROJECTS_DIR = PROJECT_ROOT / "projects"
COMPANY_LOGO_PATH = PROJECT_ROOT / "LOGO.png"

GRAPH_COLOR_PRESETS = {
    "Operativo": {
        "freq_color": "#22c55e",
        "power_color": "#3b82f6",
        "description": "Balanceado para operacion diaria y lectura rapida.",
    },
    "Contraste": {
        "freq_color": "#f59e0b",
        "power_color": "#38bdf8",
        "description": "Mas separacion visual para eventos y escalones.",
    },
    "Reporte": {
        "freq_color": "#10b981",
        "power_color": "#8b5cf6",
        "description": "Acabado mas sobrio para evidencia y presentacion.",
    },
}

STATUS_META = {
    "Completada": {
        "slug": "completada",
        "icon": "✔",
        "color": "#4ade80",
        "soft": "rgba(74,222,128,0.12)",
        "border": "rgba(74,222,128,0.25)",
    },
    "En progreso": {
        "slug": "en-progreso",
        "icon": "●",
        "color": "#fbbf24",
        "soft": "rgba(251,191,36,0.12)",
        "border": "rgba(251,191,36,0.25)",
    },
    "Pendiente": {
        "slug": "pendiente",
        "icon": "○",
        "color": "#94a3b8",
        "soft": "rgba(51,65,85,0.50)",
        "border": "rgba(51,65,85,0.60)",
    },
    "Pendiente a documentación": {
        "slug": "doc",
        "icon": "◔",
        "color": "#38bdf8",
        "soft": "rgba(56,189,248,0.12)",
        "border": "rgba(56,189,248,0.30)",
    },
}

VERDICT_META = {
    "": {"slug": "none", "label": "—", "color": "#64748b"},
    "Cumple": {"slug": "cumple", "label": "✔ Cumple", "color": "#4ade80"},
    "No cumple": {
        "slug": "nocumple",
        "label": "✘ No cumple",
        "color": "#f87171",
    },
    "Pendiente a revisión": {
        "slug": "revision",
        "label": "◑ Pend. revisión",
        "color": "#fbbf24",
    },
    "Pendiente a documentación": {
        "slug": "doc",
        "label": "📄 Pend. docs",
        "color": "#38bdf8",
    },
    "Repetir prueba": {
        "slug": "repeat",
        "label": "↻ Repetir",
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
        "nombre": "Pruebas de Centrales Electricas Sincronas",
        "tests": [
            {
                "id": 1,
                "nombre": "Rango Operativo de Tension",
                "tipos": ["A", "B", "C", "D"],
            },
            {"id": 2, "nombre": "Escalon de Tension", "tipos": ["B", "C", "D"]},
            {"id": 3, "nombre": "Limitador V/Hz", "tipos": ["A", "B", "C", "D"]},
            {
                "id": 4,
                "nombre": "Secuencia Exc-Desexc. (auto y manual)",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 5,
                "nombre": "Seguidor auto. Entre canales y UCE's",
                "tipos": ["A", "B"],
            },
            {"id": 6, "nombre": "PSS", "tipos": ["C", "D"]},
            {
                "id": 7,
                "nombre": "Limitador de minima excitacion (MEL)",
                "tipos": ["C", "D"],
            },
            {
                "id": 8,
                "nombre": "Limitador de maxima excitacion (OEL)",
                "tipos": ["C", "D"],
            },
            {"id": 9, "nombre": "Compensador de MVAr", "tipos": ["B", "C", "D"]},
            {
                "id": 10,
                "nombre": "Apertura /Cierre elementos finales de control",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 11,
                "nombre": "Secuencia de Arranque",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 12,
                "nombre": "Variador de velocidad (65F)",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 13,
                "nombre": "Escalones de Velocidad",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 14,
                "nombre": "Proteccion por sobre velocidad",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 15,
                "nombre": "Variador de Carga (65P)",
                "tipos": ["A", "B", "C", "D"],
            },
            {
                "id": 16,
                "nombre": "Limitador de Carga (65L)",
                "tipos": ["A", "B", "C", "D"],
            },
            {"id": 17, "nombre": "Estatismo", "tipos": ["A", "B", "C", "D"]},
            {
                "id": 18,
                "nombre": "Escalones de potencia (10% de Pnom)",
                "tipos": ["A", "B", "C", "D"],
            },
            {"id": 19, "nombre": "Rechazo de Carga", "tipos": ["A", "B", "C", "D"]},
            {"id": 20, "nombre": "Operacion en isla", "tipos": ["A", "B", "C", "D"]},
            {
                "id": 21,
                "nombre": "Razon de cambio 2.5 Hz/s",
                "tipos": ["A", "B", "C", "D"],
            },
            {"id": 22, "nombre": "Rango de frecuencia", "tipos": ["A", "B", "C", "D"]},
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
        1: "Prueba 1 - Sección 3.2 - 50%≤V≤110%",
        2: "Prueba 2 - Sección 3.3 - t1≤0.7 s, t2≤1.0 s; t1≤0.5 s, t2≤2.0 s",
        3: "Prueba 3 - Sección 3.4 - 1.07–1.12 pu",
        4: "Prueba 4 - Sección 3 - Verificar secuencia",
        5: "Prueba 5 - Sección 3 - Error ≤1%",
        6: "Prueba 6 - Sección 2.3 - Amortiguamiento ≤30%",
        7: "Prueba 7 - Sección 3 - Límite mínimo de excitación",
        8: "Prueba 8 - Sección 3 - Límite máximo de excitación",
        9: "Prueba 9 - Sección 4.5 - ±12% MVAr",
        10: "Prueba 10 - Sección 2.2 - Verificar tiempos y carrera",
        11: "Prueba 11 - Sección 2.2 - Verificar secuencia",
        12: "Prueba 12 - Sección 2.1 - 57–63 Hz",
        13: "Prueba 13 - Sección 2.2 - t≤30 s",
        14: "Prueba 14 - Sección 2.1 - 110–112%",
        15: "Prueba 15 - Sección 2.2 - Desde mínima a máxima potencia",
        16: "Prueba 16 - Sección 2.2 - Cumplir límites de carga",
        17: "Prueba 17 - Sección 2.2.2 - Estatismo 3%–8%",
        18: "Prueba 18 - Sección 2.2 - Escalones 10% Pnom",
        19: "Prueba 19 - Sección 5.3 - Cambio automático a isla",
        20: "Prueba 20 - Sección 5.3 - Operación estable en isla",
        21: "Prueba 21 - Sección 2.2.1 - Permanecer conectada",
        22: "Prueba 22 - Sección 2.1 - 58.8≤f≤61.2 continuo y rangos extendidos",
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
    "sincrona": {
        1: "voltage_only",
        2: "voltage_reactive",
        3: "voltage_only",
        4: "sequence",
        5: "sequence",
        6: "freq_power",
        7: "voltage_reactive",
        8: "voltage_reactive",
        9: "voltage_reactive",
        10: "sequence",
        11: "sequence",
        12: "speed_load",
        13: "speed_load",
        14: "speed_load",
        15: "power_setpoint",
        16: "power_setpoint",
        17: "freq_power_ref",
        18: "power_setpoint",
        19: "island",
        20: "island",
        21: "rocof_power",
        22: "freq_power",
    },
}

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pruebas de Centrales · Código de Red",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS Premium ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --status-completed: #49c581;
    --status-progress: #d9a441;
    --status-pending: #8a97ab;
    --status-doc: #4aa8d8;
    --verdict-fail: #f87171;
    --verdict-repeat: #fb923c;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.block-container {
    padding-top: 0.85rem !important;
    padding-bottom: 2rem !important;
}

.stApp {
    background: linear-gradient(180deg, #0b1018 0%, #101722 48%, #121a26 100%);
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1220 0%, #0f172a 100%) !important;
    border-right: 1px solid #1f3147;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 10px 16px; border-radius: 10px; transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(56,189,248,0.1);
}

/* Header */
.app-header {
    background: linear-gradient(180deg, rgba(17,24,39,0.96) 0%, rgba(18,26,38,0.96) 100%);
    border-radius: 14px; padding: 22px 26px; margin-bottom: 18px;
    border: 1px solid rgba(96,165,250,0.10);
    box-shadow: 0 6px 18px rgba(0,0,0,0.18);
    position: relative; overflow: hidden;
}
.app-header::before {
    content: ''; position: absolute; left: 0; top: 0;
    width: 6px; height: 100%;
    background: linear-gradient(180deg, #60a5fa, #49c581);
    pointer-events: none;
}
.app-header h1 {
    font-family: 'Space Grotesk', sans-serif; font-size: 1.75rem;
    font-weight: 700; color: #f0f9ff; margin: 0 0 6px 0; letter-spacing: -0.5px;
}
.app-header p { color: #a5b4c8; font-size: 0.92rem; margin: 0; }
.header-badge {
    display: inline-block; background: rgba(15,23,42,0.82);
    border: 1px solid rgba(96,165,250,0.16); color: #93c5fd;
    font-size: 0.68rem; font-weight: 600; padding: 4px 11px; border-radius: 100px;
    letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px;
}

/* Cards */
.card {
    background: rgba(17,24,39,0.88); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 18px 20px; margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.14);
}
.card-title {
    font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem;
    font-weight: 600; color: #bae6fd; margin-bottom: 4px;
}
.card-sub { font-size: 0.82rem; color: #64748b; margin-bottom: 16px; }

/* Caso block */
.caso-block {
    background: rgba(15,23,42,0.6); border: 1px solid rgba(56,189,248,0.15);
    border-radius: 12px; padding: 18px 22px; margin-bottom: 14px;
}
.caso-label {
    font-family: 'Space Grotesk', sans-serif; font-size: 0.82rem; font-weight: 700;
    color: #7dd3fc; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 12px;
    display: flex; align-items: center; gap: 8px;
}
.caso-badge {
    background: linear-gradient(135deg, #0284c7, #0ea5e9);
    color: white; font-size: 0.7rem; font-weight: 700;
    padding: 2px 10px; border-radius: 100px;
}

/* Cronograma */
.sched-row {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(15,23,42,0.55); border-radius: 10px;
    border: 1px solid rgba(56,189,248,0.08); margin-bottom: 8px;
    transition: border-color 0.2s;
}
.sched-row:hover { border-color: rgba(56,189,248,0.25); }
.status-done  { color: var(--status-completed); font-size: 1.1rem; }
.status-prog  { color: var(--status-progress); font-size: 1.1rem; }
.status-pend  { color: var(--status-pending); font-size: 1.1rem; }
.progress-bar-wrap {
    background: rgba(30,41,59,0.8); border-radius: 100px;
    height: 8px; overflow: hidden; margin: 12px 0 20px;
}
.progress-bar-fill {
    height: 100%; border-radius: 100px;
    background: linear-gradient(90deg, var(--status-completed), var(--status-doc));
    transition: width 0.4s ease;
}

/* File uploader */
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(56,189,248,0.25) !important;
    border-radius: 12px !important;
    background: rgba(15,76,132,0.08) !important; transition: all 0.25s ease;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(56,189,248,0.55) !important;
    background: rgba(15,76,132,0.18) !important;
}
[data-testid="stFileUploader"] * { color: #cbd5e1 !important; }

/* Buttons */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    padding: 12px 28px !important; font-weight: 600 !important;
    font-size: 0.9rem !important; letter-spacing: 0.3px !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.28) !important; transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 18px rgba(37,99,235,0.35) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(30,41,59,0.9) !important; color: #e2e8f0 !important;
    border: 1px solid rgba(56,189,248,0.25) !important; border-radius: 10px !important;
}

/* Inputs */
.stSelectbox > div > div, .stNumberInput > div > div > input,
.stTextInput > div > div > input {
    background: rgba(15,23,42,0.8) !important;
    border: 1px solid rgba(56,189,248,0.2) !important;
    border-radius: 10px !important; color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
.stSelectbox > div > div:hover, .stTextInput > div > div > input:focus {
    border-color: rgba(56,189,248,0.5) !important;
}

/* Alerts */
.stInfo    { background: rgba(2,132,199,0.1) !important; border-color: #0284c7 !important; border-radius: 10px !important; }
.stSuccess { background: rgba(22,163,74,0.1) !important; border-color: #16a34a !important; border-radius: 10px !important; }
.stWarning { background: rgba(217,119,6,0.1) !important; border-radius: 10px !important; }
.stError   { background: rgba(220,38,38,0.1) !important; border-radius: 10px !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid rgba(56,189,248,0.15) !important; }
.stTabs [data-baseweb="tab"]       { color: #64748b !important; font-weight: 500 !important; }
.stTabs [aria-selected="true"]     { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }

hr { border-color: rgba(56,189,248,0.1) !important; }
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden; }
.stColorPicker label { color: #94a3b8 !important; font-size: 0.82rem !important; }

.sidebar-logo {
    font-family: 'Space Grotesk', sans-serif; font-size: 1.15rem; font-weight: 700;
    color: #f0f9ff; display: flex; align-items: center; gap: 10px; padding: 8px 0 20px 0;
}
.sidebar-version { font-size: 0.7rem; color: #475569; margin-top: 4px; }
.top-shell {
    background: rgba(17,24,39,0.86); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 14px; padding: 12px 14px 10px; margin-bottom: 12px;
}
.topbar {
    display: grid; grid-template-columns: 0.85fr 1.15fr 1.15fr; gap: 10px; align-items: end;
}
@media (max-width: 900px) {
    .topbar { grid-template-columns: 1fr; }
}
.top-brand {
    display: flex; align-items: center; gap: 10px;
}
.top-brand-mark {
    width: 34px; height: 34px; border-radius: 10px; background: #2563eb;
    display: flex; align-items: center; justify-content: center; color: white;
    font-family: 'Space Grotesk', sans-serif; font-size: 0.95rem; font-weight: 700;
}
.top-brand-text {
    line-height: 1.15;
}
.top-brand-name {
    font-family: 'Space Grotesk', sans-serif; color: #f8fafc; font-size: 0.96rem; font-weight: 700;
}
.top-brand-sub {
    color: #94a3b8; font-size: 0.74rem;
}
.top-inline-summary {
    margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(148,163,184,0.08);
    color: #94a3b8; font-size: 0.78rem;
}
.top-inline-summary strong { color: #e2e8f0; }
.settings-shell {
    background: rgba(17,24,39,0.72); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 10px 12px; margin: 10px 0 14px;
}
.test-selector-label {
    font-size: 0.74rem; font-weight: 600; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.9px; margin-bottom: 4px;
}
.project-summary {
    background: rgba(17,24,39,0.78);
    border: 1px solid rgba(148,163,184,0.08); border-radius: 12px;
    padding: 10px 12px; margin-bottom: 12px;
}
.project-summary-title {
    font-family: 'Space Grotesk', sans-serif; font-size: 0.92rem; font-weight: 600;
    color: #e0f2fe; margin-bottom: 4px;
}
.project-summary-meta {
    color: #94a3b8; font-size: 0.78rem; line-height: 1.45;
}
.project-summary-meta strong { color: #f8fafc; }
.project-metrics-grid {
    display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px;
    margin-top: 14px;
}
.project-metric {
    background: rgba(2, 6, 23, 0.55); border: 1px solid rgba(56,189,248,0.08);
    border-radius: 10px; padding: 10px 12px;
}
.project-metric-label {
    color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.8px;
}
.project-metric-value {
    color: #e2e8f0; font-size: 0.98rem; font-weight: 600; margin-top: 4px;
}
.schedule-test-title {
    display: flex; gap: 12px; align-items: flex-start; margin: 18px 0 10px;
}
.schedule-test-id {
    min-width: 56px; text-align: center; padding: 6px 10px; border-radius: 999px;
    background: linear-gradient(135deg, #0284c7, #0ea5e9); color: white;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px;
}
.schedule-test-name {
    font-family: 'Space Grotesk', sans-serif; font-size: 1rem; font-weight: 600;
    color: #e2e8f0; line-height: 1.35;
}
.schedule-test-meta {
    color: #64748b; font-size: 0.8rem; margin: 3px 0 0;
}

/* Cronograma Dashboard */
.kpi-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin-bottom: 10px;
}
@media (max-width: 900px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
    .kpi-grid { grid-template-columns: 1fr; }
}
.kpi-card {
    background: rgba(17,24,39,0.84); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 12px 14px; text-align: left;
    box-shadow: none;
}
.kpi-label {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px;
    font-weight: 600; margin-bottom: 8px;
}
.kpi-value {
    font-size: 1.6rem; font-weight: 700; line-height: 1;
    font-family: 'Space Grotesk', sans-serif;
}
.kpi-sub { font-size: 0.72rem; color: #64748b; margin-top: 4px; }
.kpi-total   .kpi-label { color: #7dd3fc; }
.kpi-done    .kpi-label { color: var(--status-completed); }
.kpi-prog    .kpi-label { color: var(--status-progress); }
.kpi-pend    .kpi-label { color: var(--status-pending); }
.kpi-total   .kpi-value { color: #7dd3fc; }
.kpi-done    .kpi-value { color: var(--status-completed); }
.kpi-prog    .kpi-value { color: var(--status-progress); }
.kpi-pend    .kpi-value { color: var(--status-pending); }

.section-label {
    font-size: 0.74rem; text-transform: uppercase; letter-spacing: 1px;
    color: #7dd3fc; font-weight: 700; margin: 18px 0 10px;
}
.compact-info-bar {
    display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px;
    margin: 8px 0 14px;
}
@media (max-width: 900px) {
    .compact-info-bar { grid-template-columns: 1fr; }
}
.compact-info-card {
    background: rgba(17,24,39,0.78); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 12px 14px;
}
.compact-info-label {
    color: #94a3b8; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.9px;
    font-weight: 700;
}
.compact-info-value {
    color: #e2e8f0; font-size: 0.88rem; line-height: 1.5; margin-top: 6px;
}
.evidence-card {
    background: rgba(15,23,42,0.78); border: 1px solid rgba(56,189,248,0.12);
    border-radius: 14px; padding: 12px; margin-bottom: 14px;
}
.evidence-card-title {
    font-family: 'Space Grotesk', sans-serif; color: #e2e8f0; font-size: 0.92rem;
    font-weight: 600; line-height: 1.35; margin-bottom: 4px;
}
.evidence-card-meta {
    color: #93c5fd; font-size: 0.74rem; margin-bottom: 10px;
}
.gallery-toolbar {
    background: rgba(15,23,42,0.76); border: 1px solid rgba(56,189,248,0.10);
    border-radius: 14px; padding: 14px 16px; margin-bottom: 16px;
}
.gallery-grid-note {
    color: #93c5fd; font-size: 0.80rem; margin: 4px 0 14px;
}
.export-toolbar {
    background: rgba(17,24,39,0.82); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 10px 12px; margin-bottom: 10px;
}
.export-toolbar-title {
    font-family: 'Space Grotesk', sans-serif; color: #dbeafe; font-weight: 600; margin-bottom: 2px;
}
.export-toolbar-sub {
    color: #94a3b8; font-size: 0.76rem; margin-bottom: 8px;
}
.timeline-summary {
    background: rgba(15,23,42,0.76); border: 1px solid rgba(56,189,248,0.10);
    border-radius: 12px; padding: 10px 12px; margin: 8px 0 10px;
}
.timeline-summary strong { color: #e2e8f0; }
.plot-panel {
    background: rgba(17,24,39,0.82); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 10px 12px 4px; margin-bottom: 10px;
}
.plot-panel-title {
    font-family: 'Space Grotesk', sans-serif; color: #e0f2fe; font-weight: 600; margin-bottom: 4px;
}
.plot-panel-sub {
    color: #93c5fd; font-size: 0.80rem; margin-bottom: 10px;
}
.advanced-shell {
    background: rgba(17,24,39,0.72); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 10px 12px; margin-bottom: 14px;
}

.analysis-style-panel {
    background: linear-gradient(180deg, rgba(15,23,42,0.92), rgba(17,24,39,0.92));
    border: 1px solid rgba(56,189,248,0.12); border-radius: 14px;
    padding: 16px 18px 10px; margin-bottom: 18px;
}
.analysis-style-title {
    font-family: 'Space Grotesk', sans-serif; color: #e0f2fe; font-weight: 600;
    margin-bottom: 4px;
}
.analysis-style-sub {
    color: #93c5fd; font-size: 0.82rem; margin-bottom: 12px;
}
.style-preview {
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 8px 0 10px;
}
.style-chip {
    display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px;
    border-radius: 999px; background: rgba(2,6,23,0.5);
    border: 1px solid rgba(56,189,248,0.12); color: #e2e8f0; font-size: 0.78rem;
    font-weight: 600;
}
.style-swatch {
    width: 12px; height: 12px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.28);
}

.crono-controls {
    background: rgba(15,23,42,0.8); border: 1px solid rgba(56,189,248,0.1);
    border-radius: 14px; padding: 14px 18px; margin-bottom: 18px;
    display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
}
.crono-controls .filter-pill {
    display: inline-flex; align-items: center; padding: 6px 16px;
    border-radius: 999px; font-size: 0.8rem; font-weight: 600;
    cursor: pointer; border: 1px solid rgba(56,189,248,0.2);
    color: #64748b; background: transparent; transition: all 0.2s;
}
.crono-controls .filter-pill:hover { border-color: rgba(56,189,248,0.5); color: #7dd3fc; }
.crono-controls .filter-pill.active {
    background: rgba(56,189,248,0.15); border-color: #38bdf8; color: #38bdf8;
}
.crono-controls .view-toggle {
    display: flex; border: 1px solid rgba(56,189,248,0.2); border-radius: 999px;
    overflow: hidden; margin-left: auto;
}
.crono-controls .view-btn {
    padding: 6px 16px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; border: none; background: transparent; color: #64748b;
    transition: all 0.2s;
}
.crono-controls .view-btn:hover { color: #7dd3fc; }
.crono-controls .view-btn.active { background: rgba(56,189,248,0.15); color: #38bdf8; }

.crono-card {
    background: rgba(17,24,39,0.78); border: 1px solid rgba(148,163,184,0.08);
    border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
    box-shadow: none; transition: border-color 0.2s;
}
.crono-card:hover { border-color: rgba(148,163,184,0.16); }
.crono-card-header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
}
.crono-card-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 999px; font-size: 0.7rem; font-weight: 700;
}
.badge-completada { background: rgba(74,222,128,0.12); color: var(--status-completed); border: 1px solid rgba(74,222,128,0.25); }
.badge-en-progreso { background: rgba(251,191,36,0.12); color: var(--status-progress); border: 1px solid rgba(251,191,36,0.25); }
.badge-pendiente  { background: rgba(51,65,85,0.5); color: var(--status-pending); border: 1px solid rgba(51,65,85,0.6); }
.badge-doc  { background: rgba(56,189,248,0.12); color: var(--status-doc); border: 1px solid rgba(56,189,248,0.3); }

.crono-card-id {
    min-width: 46px; text-align: center; padding: 4px 8px; border-radius: 999px;
    background: linear-gradient(135deg, #0284c7, #0ea5e9); color: white;
    font-size: 0.72rem; font-weight: 700;
}
.crono-card-name {
    font-family: 'Space Grotesk', sans-serif; font-size: 0.95rem; font-weight: 600;
    color: #e2e8f0; flex: 1;
}
.crono-card-meta {
    display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 8px 0 10px;
}
.crono-card-meta-item {
    font-size: 0.72rem; color: #64748b;
}
.crono-card-meta-item span { color: #93c5fd; font-weight: 600; }
.crono-card-footer {
    display: flex; align-items: center; gap: 10px; margin-top: 8px;
}
.crono-thumb-wrap {
    margin-left: auto; border-radius: 8px; overflow: hidden;
    border: 1px solid rgba(56,189,248,0.1); max-width: 160px;
}
.crono-thumb { width: 100%; height: 80px; object-fit: cover; display: block; }
.crono-card-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.crono-table-wrap table {
    width: 100%; border-collapse: collapse; font-size: 0.82rem;
}
.crono-table-wrap th {
    color: #7dd3fc; font-weight: 600; text-align: left; padding: 8px 12px;
    border-bottom: 1px solid rgba(56,189,248,0.15); text-transform: uppercase;
    letter-spacing: 0.5px; font-size: 0.72rem;
}
.crono-table-wrap td {
    padding: 10px 12px; border-bottom: 1px solid rgba(56,189,248,0.06);
    color: #cbd5e1; vertical-align: middle;
}
.crono-table-wrap tr:hover td { background: rgba(56,189,248,0.04); }
.crono-table-wrap tr:last-child td { border-bottom: none; }

.timeline-wrap { margin-top: 8px; }

/* Veredicto badges */
.veredicto-cumple   { background: rgba(74,222,128,0.15); color: var(--status-completed); border: 1px solid rgba(74,222,128,0.3); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }
.veredicto-nocumple { background: rgba(248,113,113,0.15); color: var(--verdict-fail); border: 1px solid rgba(248,113,113,0.3); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }
.veredicto-revision  { background: rgba(251,191,36,0.15); color: var(--status-progress); border: 1px solid rgba(251,191,36,0.3); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }
.veredicto-doc      { background: rgba(56,189,248,0.15); color: var(--status-doc); border: 1px solid rgba(56,189,248,0.3); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }
.veredicto-repeat   { background: rgba(251,146,60,0.15); color: var(--verdict-repeat); border: 1px solid rgba(251,146,60,0.3); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }
.veredicto-none     { background: rgba(51,65,85,0.4); color: #64748b; border: 1px solid rgba(51,65,85,0.5); padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; }

/* Scroll horizontal para multi-casos */
.graph-scroll {
    display: flex; gap: 8px; overflow-x: auto; padding-bottom: 6px;
    scrollbar-width: thin; scrollbar-color: rgba(56,189,248,0.3) transparent;
}
.graph-scroll::-webkit-scrollbar { height: 4px; }
.graph-scroll::-webkit-scrollbar-thumb { background: rgba(56,189,248,0.3); border-radius: 2px; }
.graph-scroll-img {
    height: 120px; width: auto; border-radius: 8px; flex-shrink: 0;
    border: 1px solid rgba(56,189,248,0.12); object-fit: cover;
}

/* Footer Código Red - full width, pie de página */
.crono-footer {
    background: rgba(56,189,248,0.05); border: 1px solid rgba(56,189,248,0.1);
    border-radius: 10px; padding: 14px 18px; margin-top: 10px;
    width: 100%; box-sizing: border-box;
}
.crono-footer-title {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1.2px;
    font-weight: 700; color: #38bdf8; margin-bottom: 8px;
}
.crono-footer-text {
    font-size: 0.78rem; color: #94a3b8; line-height: 1.7; text-align: justify;
}
.crono-footer-ref {
    font-size: 0.72rem; color: #475569; margin-top: 6px;
}
.crono-footer-ref strong { color: #7dd3fc; }

/* Acciones rápidas en tarjeta */
.card-actions-row {
    display: flex; align-items: center; gap: 8px; margin: 8px 0 6px;
    flex-wrap: wrap;
}

/* Fecha row en tarjeta */
.crono-dates-row {
    display: flex; gap: 12px; align-items: center; margin-top: 4px;
}

/* Inline veredicto en tarjeta */
.crono-veredicto-row {
    display: flex; align-items: center; gap: 10px; margin-top: 6px;
    flex-wrap: wrap;
}
.crono-veredicto-label {
    font-size: 0.72rem; color: #64748b; white-space: nowrap;
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


def render_header(title: str, subtitle: str, icon: str = "⚡"):
    st.markdown(
        f"""
    <div class="app-header">
        <div class="header-badge">{icon} Evaluacion tecnica · Codigo de Red 2.0</div>
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
    template_key = TEST_GRAPH_PROFILES.get(test["central_kind"], {}).get(
        test["id"],
        "freq_power",
    )
    return GRAPH_TEMPLATES[template_key]


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


def _implemented_tests_for_project(project: dict) -> list[str]:
    implemented_tests: list[str] = []
    for test_key in project.get("applicable_tests", []):
        implemented_code = _get_catalog_test(test_key).get("implemented_code")
        if implemented_code in REGISTRY:
            implemented_tests.append(test_key)
    return implemented_tests


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


def _find_test_thumbnails(project: dict, test_id: int) -> list[Path]:
    out_dir = _project_output_dir(project)
    if not out_dir.exists():
        return []
    return sorted(out_dir.rglob(f"P{test_id}_*.png"))


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
                "Tipo de grafica": graph_profile["title"],
                "Seccion": graph_profile.get("section", "—"),
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
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#0f172a")
        ax.axis("off")
        ax.text(
            0.02,
            0.94,
            f"Cronograma filtrado · {project['central_name']}",
            fontsize=18,
            fontweight="bold",
            color="#f8fafc",
            transform=ax.transAxes,
        )
        ax.text(
            0.02,
            0.89,
            f"Exportado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} · Registros: {len(schedule_df)}",
            fontsize=10,
            color="#94a3b8",
            transform=ax.transAxes,
        )
        preview_df = schedule_df[[
            "Prueba",
            "Nombre",
            "Estado",
            "Veredicto",
            "Fecha inicio",
            "Fecha termino",
            "Duracion",
            "Evidencias",
        ]].head(16)
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
                cell.set_facecolor("#1e293b")
                cell.set_text_props(color="#dbeafe", weight="bold")
            else:
                cell.set_facecolor("#111827")
                cell.set_text_props(color="#e2e8f0")
            cell.set_edgecolor("#334155")
        pdf.savefig(fig, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)

        if not timeline_df.empty:
            fig2, ax2 = plt.subplots(figsize=(11.69, max(6, len(timeline_df) * 0.33 + 1.8)))
            fig2.patch.set_facecolor("#0f172a")
            ax2.set_facecolor("#0f172a")
            y_pos = list(range(len(timeline_df)))
            colors = [STATUS_META.get(status, STATUS_META["Pendiente"])["color"] for status in timeline_df["Estado"]]
            starts = mdates.date2num(pd.to_datetime(timeline_df["Inicio"]))
            ends = mdates.date2num(pd.to_datetime(timeline_df["Fin"]))
            widths = ends - starts
            ax2.barh(y_pos, widths, left=starts, color=colors, height=0.55, alpha=0.9)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(timeline_df["Prueba"], fontsize=8, color="#e2e8f0")
            ax2.tick_params(axis="x", colors="#94a3b8", labelsize=8)
            ax2.tick_params(axis="y", length=0)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y %H:%M"))
            plt.setp(ax2.get_xticklabels(), rotation=25, ha="right")
            ax2.set_title("Linea de tiempo exportada", color="#f8fafc", fontsize=14, pad=14)
            ax2.grid(True, axis="x", color="#334155", linewidth=0.8)
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)
            ax2.spines["left"].set_color("#334155")
            ax2.spines["bottom"].set_color("#334155")
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
        template="plotly_dark",
        paper_bgcolor="rgba(15,23,42,0.0)",
        plot_bgcolor="rgba(15,23,42,0.60)",
        margin=dict(l=24, r=24, t=70, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.12)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.12)", zeroline=False)
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
        palette = ["#a855f7", "#14b8a6", "#f97316", "#3b82f6", "#22c55e"]
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
        for image_path in evidence_map.get(pid, []):
            if gallery_search and gallery_search not in (
                f"{test_info['nombre']} {image_path.name}".lower()
            ):
                continue
            evidence_items.append(
                {
                    "pid": pid,
                    "test": test_info,
                    "path": image_path,
                    "entry": entry,
                    "mtime": _path_mtime(image_path),
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
            st.image(str(item["path"]), use_container_width=True)
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
    render_header(
        "Cronograma de Pruebas",
        "Registra el avance operativo de las pruebas aplicables de la central.",
        "📅",
    )
    _render_active_project(project)

    if not project:
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
        thumbs = sorted(
            _find_test_thumbnails(project, test_info["id"]),
            key=_path_mtime,
            reverse=True,
        )
        evidence_map[pid] = thumbs
        if thumbs:
            evidence_highlights.append(
                {
                    "pid": pid,
                    "test": test_info,
                    "path": thumbs[0],
                    "count": len(thumbs),
                    "mtime": _path_mtime(thumbs[0]),
                }
            )
    evidence_highlights.sort(key=lambda item: item["mtime"], reverse=True)

    if "crono_view" not in st.session_state:
        st.session_state.crono_view = "timeline"
    if "crono_filter" not in st.session_state:
        st.session_state.crono_filter = "Todas"
    if "crono_search" not in st.session_state:
        st.session_state.crono_search = ""

    estado_options = list(STATUS_META.keys())
    veredicto_options = list(VERDICT_META.keys())

    def _estado_index(e):
        try:
            return estado_options.index(e)
        except ValueError:
            return 0

    def _veredicto_index(v):
        try:
            return veredicto_options.index(v)
        except ValueError:
            return 0

    # ── Block 1: KPI Summary ─────────────────────────────────────────────────
    done = sum(1 for v in schedule.values() if v["estado"] == "Completada")
    prog = sum(1 for v in schedule.values() if v["estado"] == "En progreso")
    pend = sum(1 for v in schedule.values() if v["estado"] == "Pendiente")
    doc = sum(
        1 for v in schedule.values() if v["estado"] == "Pendiente a documentación"
    )
    total = len(applicable_tests)
    pct = int(done / total * 100) if total else 0
    tests_with_evidence = sum(1 for thumbs in evidence_map.values() if thumbs)
    evidence_total = sum(len(thumbs) for thumbs in evidence_map.values())
    evidence_coverage = int(tests_with_evidence / total * 100) if total else 0

    st.markdown(
        f"""
    <div class="kpi-grid">
        <div class="kpi-card kpi-done">
            <div class="kpi-label">Avance</div>
            <div class="kpi-value">{pct}%</div>
            <div class="kpi-sub">{done} de {total} pruebas completadas</div>
        </div>
        <div class="kpi-card kpi-prog">
            <div class="kpi-label">En progreso</div>
            <div class="kpi-value">{prog}</div>
            <div class="kpi-sub">pruebas activas en seguimiento</div>
        </div>
        <div class="kpi-card kpi-total">
            <div class="kpi-label">Cobertura visual</div>
            <div class="kpi-value">{evidence_coverage}%</div>
            <div class="kpi-sub">{tests_with_evidence} prueba(s) con evidencia · {evidence_total} archivos</div>
        </div>
    </div>
    <div class="progress-bar-wrap">
        <div class="progress-bar-fill" style="width:{pct}%"></div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if evidence_highlights:
        st.caption(f"{len(evidence_highlights)} prueba(s) ya cuentan con evidencia reciente.")

    # ── Block 2: Controls ────────────────────────────────────────────────────
    filter_opts = ["Todas", "Completadas", "En progreso", "Pendientes", "Documentación"]
    view_opts = ["cards", "table", "timeline"]
    view_labels = {"cards": "Tarjetas", "table": "Tabla", "timeline": "Línea de tiempo"}

    _cf, _cs, _cv = st.columns([3, 2.5, 4.5])
    with _cf:
        _cur = st.session_state.get("crono_filter", "Todas")
        _idx = filter_opts.index(_cur) if _cur in filter_opts else 0
        selected_filter = st.radio(
            "Filtro",
            filter_opts,
            index=_idx,
            horizontal=True,
            label_visibility="collapsed",
            key="crono_filter_radio",
        )
        if selected_filter != st.session_state.get("crono_filter", "Todas"):
            st.session_state.crono_filter = selected_filter
            st.rerun()

    with _cs:
        search_val = st.text_input(
            "Buscar",
            value=st.session_state.crono_search,
            placeholder="Nombre de la prueba...",
            label_visibility="collapsed",
            key="crono_search_input",
        )
        if search_val != st.session_state.crono_search:
            st.session_state.crono_search = search_val

    with _cv:
        st.markdown('<div class="view-toggle">', unsafe_allow_html=True)
        btn_cols = st.columns(len(view_opts))
        for i, v in enumerate(view_opts):
            active = "active" if st.session_state.crono_view == v else ""
            with btn_cols[i]:
                if st.button(view_labels[v], key=f"view_{v}", use_container_width=True):
                    st.session_state.crono_view = v
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Apply filters
    _filter_map = {
        "Completadas": "Completada",
        "En progreso": "En progreso",
        "Pendientes": "Pendiente",
        "Documentación": "Pendiente a documentación",
    }
    _target_estado = _filter_map.get(st.session_state.crono_filter)
    filtered_ids = []
    for pid in applicable_tests:
        entry = schedule.get(
            pid,
            {
                "estado": "Pendiente",
                "fecha_inicio": "",
                "fecha_termino": "",
                "nota": "",
                "veredicto": "",
            },
        )
        if _target_estado and entry["estado"] != _target_estado:
            continue
        if st.session_state.crono_search:
            test_info = _get_catalog_test(pid)
            if st.session_state.crono_search.lower() not in test_info["nombre"].lower():
                continue
        filtered_ids.append(pid)

    if not filtered_ids:
        st.info("Ninguna prueba coincide con los filtros activos.")
        return

    _render_schedule_export_toolbar(project, filtered_ids, schedule, evidence_map)

    # ── Block 3: Active View ─────────────────────────────────────────────────
    current_view = st.session_state.crono_view

    # ─── CARDS VIEW ───────────────────────────────────────────────────────────
    if current_view == "cards":
        cols = st.columns(2)
        for idx, pid in enumerate(filtered_ids):
            test_info = _get_catalog_test(pid)
            implemented_code = test_info.get("implemented_code")
            cfg = REGISTRY.get(implemented_code) if implemented_code else None
            entry = schedule.get(
                pid,
                {
                    "estado": "Pendiente",
                    "fecha_inicio": "",
                    "fecha_termino": "",
                    "fecha_inicio_auto": "",
                    "fecha_termino_auto": "",
                    "duracion_min": "",
                    "origen_tiempo": "",
                    "nota": "",
                    "veredicto": "",
                },
            )
            status_style = _status_style(entry.get("estado", "Pendiente"))
            graph_profile = _graph_profile(pid)
            criterion = _codigo_red_criterio(pid)
            thumb_paths = evidence_map.get(pid, [])
            _fecha_ini, _fecha_ter = _effective_schedule_labels(entry)
            verdict_style = _veredict_style(entry.get("veredicto", ""))

            with cols[idx % 2]:
                # ── 1. HEADER: badge + ID + nombre ─────────────────────────────
                st.markdown(
                    f"""
                    <div class="crono-card">
                        <div class="crono-card-header">
                            <div class="crono-card-badge badge-{status_style['slug']}">
                                <span>{status_style['icon']}</span>{entry.get("estado", "Pendiente")}
                            </div>
                            <div class="crono-card-id">P{test_info["id"]:02d}</div>
                            <div class="crono-card-name">{test_info["nombre"]}</div>
                        </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"""
                    <div class="crono-card-meta">
                        <div class="crono-card-meta-item"><span>Inicio</span> {_fecha_ini or '—'}</div>
                        <div class="crono-card-meta-item"><span>Termino</span> {_fecha_ter or '—'}</div>
                        <div class="crono-card-meta-item"><span>Duracion</span> {_format_duration_minutes(entry.get('duracion_min', ''))}</div>
                        <div class="crono-card-meta-item"><span>Evidencias</span> {len(thumb_paths)}</div>
                    </div>
                    <div class="crono-veredicto-row">
                        <div class="crono-veredicto-label">Veredicto actual</div>
                        <div class="veredicto-{verdict_style['slug']}">{verdict_style['label']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                with st.expander("Ficha tecnica", expanded=False):
                    st.markdown(
                        f"""
                        <div class="crono-footer" style="margin-top: 6px; margin-bottom: 12px;">
                            <div class="crono-footer-title">Código de Red 2.0 — Criterio de aceptación</div>
                            <div class="crono-footer-text">{criterion}</div>
                            <div class="crono-footer-ref">
                                <strong>Sección:</strong> {graph_profile.get("section", "—")}
                                &nbsp;&nbsp;|&nbsp;&nbsp;
                                <strong>Tipo de gráfica:</strong> {graph_profile["title"]}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # ── 4. GRÁFICAS ─────────────────────────────────────────────────
                if thumb_paths:
                    st.image(
                        str(thumb_paths[0]),
                        use_container_width=True,
                        caption=f"Evidencia principal · {thumb_paths[0].name}",
                    )
                    if len(thumb_paths) > 1:
                        with st.expander(
                            f"Ver {len(thumb_paths) - 1} evidencia(s) adicional(es)",
                            expanded=False,
                        ):
                            extra_cols = st.columns(2)
                            for extra_idx, tp in enumerate(thumb_paths[1:]):
                                with extra_cols[extra_idx % 2]:
                                    st.image(
                                        str(tp),
                                        use_container_width=True,
                                        caption=tp.name,
                                    )
                elif cfg:
                    st.caption("Sin gráfica generada")
                else:
                    st.caption("Sin análisis automatizado")

                with st.expander("Editar", expanded=False):
                    ctrl1, ctrl2 = st.columns([1.1, 1.3])
                    ctrl1.selectbox(
                        "Estado",
                        estado_options,
                        index=_estado_index(entry.get("estado", "Pendiente")),
                        key=f"estado_{project_slug}_{pid}",
                    )
                    ctrl2.selectbox(
                        "Veredicto",
                        veredicto_options,
                        index=_veredicto_index(entry.get("veredicto", "")),
                        key=f"veredicto_{project_slug}_{pid}",
                    )

                    _ini_raw = _parse_date(_fecha_ini)
                    _ter_raw = _parse_date(_fecha_ter)
                    date1, date2 = st.columns(2)
                    date1.date_input(
                        "Fecha inicio",
                        value=_ini_raw,
                        key=f"fecha_inicio_{project_slug}_{pid}",
                    )
                    date2.date_input(
                        "Fecha término",
                        value=_ter_raw,
                        key=f"fecha_termino_{project_slug}_{pid}",
                    )
                    st.text_area(
                        "Observaciones",
                        value=entry.get("nota", ""),
                        key=f"nota_{project_slug}_{pid}",
                        height=80,
                        label_visibility="collapsed",
                    )

                st.markdown("</div>", unsafe_allow_html=True)

    # ─── TABLE VIEW ────────────────────────────────────────────────────────────
    elif current_view == "table":
        table_rows = []
        for pid in filtered_ids:
            test_info = _get_catalog_test(pid)
            entry = schedule.get(
                pid,
                {
                    "estado": "Pendiente",
                    "fecha_inicio": "",
                    "fecha_termino": "",
                    "nota": "",
                    "veredicto": "",
                },
            )
            status_style = _status_style(entry.get("estado", "Pendiente"))
            graph_profile = _graph_profile(pid)
            verdict_style = _veredict_style(entry.get("veredicto", ""))
            table_rows.append(
                {
                    "#": test_info["id"],
                    "Prueba": test_info["nombre"],
                    "Estado": f"{status_style['icon']} {entry['estado']}",
                    "Veredicto": verdict_style["label"],
                    "Sección": graph_profile.get("section", "—"),
                    "Gráfica": graph_profile["title"],
                    "Inicio": _effective_schedule_labels(entry)[0],
                    "Término": _effective_schedule_labels(entry)[1],
                    "Duración": _format_duration_minutes(entry.get("duracion_min", "")),
                }
            )

        if table_rows:
            df_table = pd.DataFrame(table_rows)
            st.markdown(
                f"""
                <div class="crono-table-wrap">
                    {df_table.to_html(index=False, escape=False, classes="")}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.expander("Editar prueba", expanded=False):
            edit_col1, edit_col2 = st.columns([3, 3])
            with edit_col1:
                edit_opts = [
                    f"P{_get_catalog_test(pid)['id']:02d} — {_get_catalog_test(pid)['nombre']}"
                    for pid in filtered_ids
                ]
                edit_selected = st.selectbox(
                    "Selecciona prueba", edit_opts, key="crono_edit_select"
                )
                edit_pid = filtered_ids[edit_opts.index(edit_selected)]
                edit_entry = schedule.get(
                    edit_pid,
                    {
                        "estado": "Pendiente",
                        "fecha_inicio": "",
                        "fecha_termino": "",
                        "nota": "",
                        "veredicto": "",
                    },
                )
                new_nota = st.text_area(
                    "Obs",
                    value=edit_entry.get("nota", ""),
                    key=f"nota_edit_{project_slug}",
                    height=80,
                    label_visibility="collapsed",
                )

            with edit_col2:
                ce1, ce2 = st.columns(2)
                with ce1:
                    new_estado = st.selectbox(
                        "Estado",
                        estado_options,
                        index=_estado_index(edit_entry.get("estado", "Pendiente")),
                        key=f"estado_edit_{project_slug}",
                        label_visibility="collapsed",
                    )
                with ce2:
                    new_veredicto = st.selectbox(
                        "Veredicto",
                        veredicto_options,
                        index=_veredicto_index(edit_entry.get("veredicto", "")),
                        key=f"veredicto_edit_{project_slug}",
                        label_visibility="collapsed",
                    )
                cd1, cd2 = st.columns(2)
                with cd1:
                    st.date_input(
                        "Fecha inicio",
                        value=_parse_date(edit_entry.get("fecha_inicio", "")),
                        key=f"fecha_inicio_edit_{project_slug}",
                        label_visibility="collapsed",
                    )
                with cd2:
                    st.date_input(
                        "Fecha término",
                        value=_parse_date(edit_entry.get("fecha_termino", "")),
                        key=f"fecha_termino_edit_{project_slug}",
                        label_visibility="collapsed",
                    )

    # ─── TIMELINE VIEW ─────────────────────────────────────────────────────────
    elif current_view == "timeline":
        _render_interactive_timeline(project, filtered_ids, schedule, evidence_map)

        with st.expander("Editar prueba", expanded=False):
            tline_edit_opts = [
                f"P{_get_catalog_test(pid)['id']:02d} — {_get_catalog_test(pid)['nombre']}"
                for pid in filtered_ids
            ]
            tline_selected = st.selectbox(
                "Selecciona prueba", tline_edit_opts, key="crono_tline_edit"
            )
            tline_pid = filtered_ids[tline_edit_opts.index(tline_selected)]
            tline_entry = schedule.get(
                tline_pid,
                {
                    "estado": "Pendiente",
                    "fecha_inicio": "",
                    "fecha_termino": "",
                    "nota": "",
                    "veredicto": "",
                },
            )
            te1, te2, te3, te4 = st.columns([1.5, 1.2, 1.2, 2.1])
            with te1:
                new_estado = st.selectbox(
                    "Estado",
                    estado_options,
                    index=_estado_index(tline_entry.get("estado", "Pendiente")),
                    key=f"estado_tline_{project_slug}",
                    label_visibility="collapsed",
                )
            with te2:
                st.date_input(
                    "Fecha inicio",
                    value=_parse_date(tline_entry.get("fecha_inicio", "")),
                    key=f"fecha_inicio_tline_{project_slug}",
                    label_visibility="collapsed",
                )
            with te3:
                st.date_input(
                    "Fecha término",
                    value=_parse_date(tline_entry.get("fecha_termino", "")),
                    key=f"fecha_termino_tline_{project_slug}",
                    label_visibility="collapsed",
                )
            with te4:
                new_veredicto = st.selectbox(
                    "Veredicto",
                    veredicto_options,
                    index=_veredicto_index(tline_entry.get("veredicto", "")),
                    key=f"veredicto_tline_{project_slug}",
                    label_visibility="collapsed",
                )
            new_nota = st.text_area(
                "Obs",
                value=tline_entry.get("nota", ""),
                key=f"nota_tline_{project_slug}",
                height=80,
                label_visibility="collapsed",
            )

    with st.expander("Abrir galeria de evidencias", expanded=False):
        _render_evidence_gallery(project, filtered_ids, schedule, evidence_map)

    # ── Persist any edits ─────────────────────────────────────────────────────
    active_pid: str | None = None

    if current_view == "table":
        active_pid = edit_pid
    elif current_view == "timeline":
        active_pid = tline_pid
    elif current_view == "cards":
        active_pid = filtered_ids[-1] if filtered_ids else None

    updated = False
    if active_pid:

        def _read_card_entry(pid: str) -> dict:
            return schedule.get(
                pid,
                {
                    "estado": "Pendiente",
                    "fecha_inicio": "",
                    "fecha_termino": "",
                    "nota": "",
                    "veredicto": "",
                },
            )

        if current_view == "cards":
            for pid in filtered_ids:
                e = _read_card_entry(pid)
                ke = st.session_state.get(f"estado_{project_slug}_{pid}", e["estado"])
                ki = _date_to_str(
                    st.session_state.get(f"fecha_inicio_{project_slug}_{pid}", None)
                )
                kt = _date_to_str(
                    st.session_state.get(f"fecha_termino_{project_slug}_{pid}", None)
                )
                kn = st.session_state.get(f"nota_{project_slug}_{pid}", e["nota"])
                kv = st.session_state.get(
                    f"veredicto_{project_slug}_{pid}", e["veredicto"]
                )
                if (
                    ke != e["estado"]
                    or ki != e["fecha_inicio"]
                    or kt != e["fecha_termino"]
                    or kn != e["nota"]
                    or kv != e["veredicto"]
                ):
                    schedule[pid] = {
                        **e,
                        "estado": ke,
                        "fecha_inicio": ki,
                        "fecha_termino": kt,
                        "nota": kn,
                        "veredicto": kv,
                    }
                    updated = True
        elif current_view == "table":
            e = _read_card_entry(active_pid)
            ke = st.session_state.get(f"estado_edit_{project_slug}", e["estado"])
            ki = _date_to_str(
                st.session_state.get(f"fecha_inicio_edit_{project_slug}", None)
            )
            kt = _date_to_str(
                st.session_state.get(f"fecha_termino_edit_{project_slug}", None)
            )
            kv = st.session_state.get(f"veredicto_edit_{project_slug}", e["veredicto"])
            kn = st.session_state.get(f"nota_edit_{project_slug}", e["nota"])
            if (
                ke != e["estado"]
                or ki != e["fecha_inicio"]
                or kt != e["fecha_termino"]
                or kv != e["veredicto"]
                or kn != e["nota"]
            ):
                schedule[active_pid] = {
                    **e,
                    "estado": ke,
                    "fecha_inicio": ki,
                    "fecha_termino": kt,
                    "nota": kn,
                    "veredicto": kv,
                }
                updated = True
        elif current_view == "timeline":
            e = _read_card_entry(active_pid)
            ke = st.session_state.get(f"estado_tline_{project_slug}", e["estado"])
            ki = _date_to_str(
                st.session_state.get(f"fecha_inicio_tline_{project_slug}", None)
            )
            kt = _date_to_str(
                st.session_state.get(f"fecha_termino_tline_{project_slug}", None)
            )
            kv = st.session_state.get(f"veredicto_tline_{project_slug}", e["veredicto"])
            kn = st.session_state.get(f"nota_tline_{project_slug}", e["nota"])
            if (
                ke != e["estado"]
                or ki != e["fecha_inicio"]
                or kt != e["fecha_termino"]
                or kv != e["veredicto"]
                or kn != e["nota"]
            ):
                schedule[active_pid] = {
                    **e,
                    "estado": ke,
                    "fecha_inicio": ki,
                    "fecha_termino": kt,
                    "nota": kn,
                    "veredicto": kv,
                }
                updated = True

    if updated:
        _save_schedule(project, schedule)
        st.toast("✅ Cronograma guardado", icon="💾")


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


def module_analisis(project: dict | None):
    render_header(
        "Análisis de Pruebas",
        "Genera evidencia grafica, revisa criterios tecnicos y prepara el dictamen de cumplimiento.",
        "📈",
    )
    _render_active_project(project)

    if not project:
        return

    implemented_tests = _implemented_tests_for_project(project)
    if not project.get("applicable_tests", []):
        st.warning("Esta central no tiene pruebas aplicables seleccionadas.")
        return
    if not implemented_tests:
        st.warning(
            "Este modulo aun no tiene una plantilla de ejecucion disponible para las pruebas aplicables de esta central."
        )
        return

    project_slug = project["slug"]
    output_dir = _project_output_dir(project)
    freq_color, power_color = _colors()

    options = {_test_label(test_key): test_key for test_key in implemented_tests}
    selected_label = st.selectbox(
        "Prueba",
        list(options.keys()),
        label_visibility="collapsed",
        key=f"analysis_test_{project_slug}",
    )
    selected_test_key = options[selected_label]
    test_info = _get_catalog_test(selected_test_key)
    test_id = test_info["implemented_code"]
    config = REGISTRY[test_id]

    st.divider()

    # ── Prueba SIMPLE ──────────────────────────────────────────────────────────
    if config.tipo == "simple" and config.id == "P28":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="card-title">Evidencias base</div>
            <p style="color:#cbd5e1; line-height:1.65; margin:0;">
                P28 se genera a partir de las evidencias existentes de P1, P2, P3, P8 y P9.
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run_p28_btn = st.button(
                "▶  Generar P28",
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
                except Exception as e:
                    _show_exception("Error", e)

    elif config.tipo == "simple" and config.id == "P25":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-title">Archivos de entrada</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown("</div>", unsafe_allow_html=True)

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run_p25_btn = st.button(
                "▶  Ejecutar P25",
                type="primary",
                use_container_width=True,
            )

        if run_p25_btn:
            if not poi_file or not gen_file or not load_file:
                st.warning("⚠️ Proporciona los tres archivos antes de ejecutar P25.")
                return
            poi_path = save_upload(poi_file)
            gen_path = save_upload(gen_file)
            load_path = save_upload(load_file)
            with st.spinner("Alineando POI, generación y carga para generar las 5 gráficas..."):
                try:
                    result = run_p25(config, poi_path, gen_path, load_path, output_dir)
                    _autosync_schedule_from_result(project, selected_test_key, result)
                    _show_p25_result(result, config, selected_test_key)
                except Exception as e:
                    _show_exception("Error", e)

    elif config.tipo == "simple":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-title">Archivos de entrada</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown("</div>", unsafe_allow_html=True)

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run = st.button(
                f"▶  Ejecutar {test_id}", type="primary", use_container_width=True
            )

        if run:
            if not poi_file or not gen_file:
                st.warning("⚠️ Proporciona ambos archivos antes de ejecutar.")
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
                except Exception as e:
                    _show_exception("Error", e)

    # ── Prueba MULTI ───────────────────────────────────────────────────────────
    else:
        st.markdown(
            f"""
        <div style="background:rgba(17,24,39,0.72); border:1px solid rgba(148,163,184,0.08);
                    border-radius:10px; padding:10px 12px; margin-bottom:12px; color:#cbd5e1;">
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

        btn_col2, _ = st.columns([1, 3])
        with btn_col2:
            run_m = st.button(
                f"▶  Ejecutar {test_id}", type="primary", use_container_width=True
            )

        if run_m:
            ready = [(c, f, g) for c, f, g in file_pairs_raw if f and g]
            if not ready:
                st.warning("⚠️ Carga al menos un par de archivos (FREC + GEN).")
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
    st.success(f"✅ P25 procesada · {result.row_count:,} registros alineados")
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
                st.dataframe(deadband_table, use_container_width=True)

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
            "⬇️  Descargar ZIP con las 5 gráficas",
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
            f"""
        <div class="card">
            <div class="card-title">📊 Alcance de la corrida</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">Se generaron 5 gráficas para 15 días usando POI, generación y carga alineados por timestamp.</p>
            <div class="card-title">📏 Criterio de aceptación</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_codigo_red_criterio(test_key)}</p>
            <div class="card-title">📝 Conclusión normativa</div>
            <p style="color:#e2e8f0; line-height:1.7; margin:0;">{config.conclusion}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )


def _show_simple_result(result, config, test_key: str, freq_color: str, power_color: str):
    st.success(f"✅ Gráfica generada · {result.row_count:,} registros procesados")
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
                "⬇️  Descargar gráfica PNG",
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
            "⬇️  Descargar evidencias P28",
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
            f"""
        <div class="card">
            <div class="card-title">📊 Tipo de gráfica</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_graph_profile(test_key)["title"]}</p>
            <div class="card-title">📏 Criterio de aceptación</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_codigo_red_criterio(test_key)}</p>
            <div class="card-title">📝 Conclusión normativa</div>
            <p style="color:#e2e8f0; line-height:1.7; margin:0;">{config.conclusion}</p>
        </div>
        """,
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

    st.success(f"✅ {len(ok)} gráfica(s) generada(s)")
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
        f"⬇️  Descargar ZIP ({len(ok)} gráfica(s) + resumen Excel)",
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
            st.markdown("#### 📊 Resumen de estados de frecuencia")
            try:
                df_sum = pd.read_excel(result.summary_xlsx)
                st.dataframe(df_sum.head(60), use_container_width=True)
            except Exception:
                pass

        st.markdown(
            f"""
        <div class="card">
            <div class="card-title">📊 Tipo de gráfica</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_graph_profile(test_key)["title"]}</p>
            <div class="card-title">📏 Criterio de aceptación</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_codigo_red_criterio(test_key)}</p>
            <div class="card-title">📝 Conclusión normativa</div>
            <p style="color:#e2e8f0; line-height:1.7; margin:0;">{config.conclusion}</p>
        </div>
        """,
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

    st.success(f"✅ {len(ok)} grafica(s) con zonas generada(s)")
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
    st.dataframe(eval_df, use_container_width=True)

    # Colores para semaforo (pandas 3.x usa map, no applymap)
    def _semaforo_color(s):
        if s == "verde":
            return "background-color: #dcfce7; color: #166534"
        if s == "amarillo":
            return "background-color: #fef9c3; color: #854d0e"
        if s == "rojo":
            return "background-color: #fee2e2; color: #991b1b"
        return ""

    try:
        st.dataframe(eval_df.style.map(_semaforo_color, subset=["Semaforo"]), use_container_width=True)
    except Exception:
        st.dataframe(eval_df.style.apply(_semaforo_color, subset=["Semaforo"]), use_container_width=True)

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
            f"⬇️  Descargar ZIP con zonas ({len(ok)} grafica(s) + evaluacion Excel)",
            data=zip_buf.read(),
            file_name=zip_name,
            mime="application/zip",
            key="dl_zones_zip",
        )

    with st.expander("Ver resumen tecnico", expanded=False):
        st.markdown(
            f"""
        <div class="card">
            <div class="card-title">📊 Tipo de grafica</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_graph_profile(test_key)["title"]}</p>
            <div class="card-title">📏 Criterio de aceptacion</div>
            <p style="color:#cbd5e1; line-height:1.7; margin:0 0 14px 0;">{_codigo_red_criterio(test_key)}</p>
            <div class="card-title">📝 Conclusion normativa</div>
            <p style="color:#e2e8f0; line-height:1.7; margin:0;">{config.conclusion}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )


# ─── Depuracion
def module_depuracion(project: dict | None):
    render_header(
        "Depuración de Datos",
        "Recorta archivos de día completo en ventanas por prueba y exporta archivos listos para análisis.",
        "⚙️",
    )
    _render_active_project(project)

    if not project:
        return

    project_slug = project["slug"]
    out_dir = _project_depur_dir(project)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-title">📂 Archivos Fuente (Día Completo)</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="card-sub">Archivos fuente en Excel o CSV con columna de tiempo utilizable</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="large")
    with c1:
        poi_day = st.file_uploader(
            "Archivo POI / PPC — Día completo",
            type=["xlsx", "xls", "csv", "cvs"],
            key=f"depur_poi_{project_slug}",
        )
        if poi_day:
            st.caption(f"✔ {poi_day.name} · {poi_day.size / 1024 / 1024:.1f} MB")
    with c2:
        gen_day = st.file_uploader(
            "Archivo GEN — Día completo",
            type=["xlsx", "xls", "csv", "cvs"],
            key=f"depur_gen_{project_slug}",
        )
        if gen_day:
            st.caption(f"✔ {gen_day.name} · {gen_day.size / 1024 / 1024:.1f} MB")
    st.markdown("</div>", unsafe_allow_html=True)

    if poi_day and gen_day:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-title">✂️ Ventanas de Tiempo a Recortar</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown("</div>", unsafe_allow_html=True)

        btn_col3, _ = st.columns([1, 3])
        with btn_col3:
            run_d = st.button(
                "⚙️  Depurar y exportar", type="primary", use_container_width=True
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
                    f"✅ {len(resultado_paths)} archivo(s) exportado(s) en `projects/{project['slug']}/DEPUR/SALIDAS/`"
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
                    "⬇️  Descargar todos los recortes (ZIP)",
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


def render_top_panel() -> tuple[str, dict | None]:
    projects = _list_projects()
    project_map = {project["slug"]: project for project in projects}
    project_options = ["__new__", *project_map.keys()]

    pending_project_slug = st.session_state.pop("_pending_project_slug", None)
    if pending_project_slug in project_options:
        st.session_state["project_selector_slug"] = pending_project_slug

    st.markdown('<div class="top-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="top-brand">
            <div class="top-brand-mark">⚡</div>
            <div class="top-brand-text">
                <div class="top-brand-name">Código de Red</div>
                <div class="top-brand-sub">Panel tecnico</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    row1 = st.columns([0.85, 1.2, 1.45], gap="medium")
    with row1[0]:
        mode = st.selectbox(
            "Modulo",
            ["Cronograma", "Análisis de Pruebas", "Depuración"],
            key="top_mode_selector",
        )
    with row1[1]:
        selected_project_slug = st.selectbox(
            "Central guardada",
            project_options,
            format_func=lambda slug: (
                "Crear nueva central"
                if slug == "__new__"
                else _project_label(project_map[slug])
            ),
            key="project_selector_slug",
        )

    active_project = (
        None
        if selected_project_slug == "__new__"
        else project_map[selected_project_slug]
    )
    central_name_value = (
        active_project.get("central_name", "") if active_project else ""
    )
    central_kind_value = (
        active_project.get("central_kind", "asincrona")
        if active_project
        else "asincrona"
    )
    central_class_value = (
        active_project.get("central_class", "A") if active_project else "A"
    )

    central_kind_options = list(CENTRAL_CATALOGS)
    central_class_options = ["A", "B", "C", "D"]

    with row1[2]:
        if active_project:
            st.markdown(
                f"""
                <div class="top-inline-summary">
                    <strong>{_project_label(active_project)}</strong><br>
                    {_project_family_label(active_project)} · Tipo {active_project['central_class']} · {len(active_project.get('applicable_tests', []))} prueba(s)
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="top-inline-summary">
                    <strong>Nueva central</strong><br>
                    Configura el proyecto solo si necesitas crearlo o editarlo.
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Configuracion de central", expanded=active_project is None):
        st.markdown('<div class="settings-shell">', unsafe_allow_html=True)
        cfg1, cfg2, cfg3 = st.columns([1.4, 1, 0.8], gap="medium")
        with cfg1:
            central_name = st.text_input(
                "Nombre de la central",
                value=central_name_value,
                key=f"central_name_{selected_project_slug}",
                placeholder="Central Solar Trane Norte",
            )
        with cfg2:
            central_kind = st.selectbox(
                "Familia",
                central_kind_options,
                index=central_kind_options.index(central_kind_value),
                format_func=lambda item: CENTRAL_CATALOGS[item]["nombre"],
                key=f"central_kind_{selected_project_slug}",
            )
        with cfg3:
            central_class = st.selectbox(
                "Tipo",
                central_class_options,
                index=central_class_options.index(central_class_value)
                if central_class_value in central_class_options
                else 0,
                key=f"central_class_{selected_project_slug}",
            )

        eligible_tests = _eligible_tests(central_kind, central_class)
        default_applicable = (
            _normalize_test_ids(
                active_project.get("applicable_tests", []),
                central_kind,
                central_class,
            )
            if active_project
            else eligible_tests
        )
        applicable_tests = st.multiselect(
            "Pruebas aplicables",
            eligible_tests,
            default=default_applicable or eligible_tests,
            format_func=_test_label,
            key=f"project_tests_{selected_project_slug}_{central_kind}_{central_class}",
        )
        st.caption(f"{len(applicable_tests)} seleccionada(s) de {len(eligible_tests)} disponible(s)")
        st.markdown("</div>", unsafe_allow_html=True)

    save_label = "Crear central" if active_project is None else "Guardar cambios"
    if st.button(save_label, type="primary", use_container_width=False):
        clean_central_name = central_name.strip()

        if not clean_central_name:
            st.warning("Captura el nombre de la central.")
        elif not applicable_tests:
            st.warning("Selecciona al menos una prueba aplicable.")
        else:
            slug = (
                active_project["slug"]
                if active_project
                else _next_project_slug(_slugify(clean_central_name))
            )
            saved_project = _save_project_metadata(
                slug,
                clean_central_name,
                central_kind,
                central_class,
                applicable_tests,
            )
            st.session_state["_pending_project_slug"] = saved_project["slug"]
            st.rerun()

    if active_project:
        st.caption(f"Carpeta: `projects/{active_project['slug']}`")
    st.markdown("</div>", unsafe_allow_html=True)
    return mode, active_project


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode, project = render_top_panel()
    if mode == "Cronograma":
        module_cronograma(project)
    elif mode == "Análisis de Pruebas":
        module_analisis(project)
    else:
        module_depuracion(project)


if __name__ == "__main__":
    main()
