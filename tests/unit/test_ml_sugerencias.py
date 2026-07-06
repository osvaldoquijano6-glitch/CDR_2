"""E5: módulo ML de apoyo — sugerencias con confianza, nunca dictamen."""

import pandas as pd

from gcv.ml.sugerencias import (
    clasificar_eventos,
    detectar_anomalias,
    pruebas_incompletas,
    sugerir_mapeos,
)
from gcv.models import MappingMethod

from tests.unit.helpers import ts


def test_sugerencia_de_mapeo_difuso():
    # "Frecuencia" con typo: el diccionario exacto no lo reconoce, el difuso sí
    sugerencias = sugerir_mapeos(["Frecuencia", "Frecuencia del sistema", "Frecuenca [Hz]"])
    # las dos primeras las resuelve el camino determinístico → no se sugieren
    assert all(s.columna_original == "Frecuenca [Hz]" for s in sugerencias)
    assert sugerencias and sugerencias[0].senal_canonica == "frequency"
    assert sugerencias[0].metodo == MappingMethod.AUTO_ML_SUGERIDO
    assert sugerencias[0].confianza < 1.0  # exige confirmación del usuario


def test_sugerencia_no_inventa_bajo_umbral():
    assert sugerir_mapeos(["Comentarios del operador"]) == []


def test_anomalias_outlier_plana_y_nan():
    n = 120
    valores = [50.0 + (i % 3) * 0.1 for i in range(n)]
    valores[40] = 500.0                      # outlier
    valores[60:100] = [51.0] * 40            # tramo plano
    valores[110] = None                      # pérdida
    df = pd.DataFrame({"timestamp": ts(n), "active_power": valores})
    tipos = {h.tipo for h in detectar_anomalias(df, ["active_power"])}
    assert {"outlier", "plana", "perdida_senal"} <= tipos


def test_clasificacion_de_eventos():
    n = 200
    df = pd.DataFrame({
        "timestamp": ts(n),
        "frequency": [60.0] * 100 + [60.5] * 100,
        "voltage": [230.0] * 150 + [180.0] * 10 + [230.0] * 40,
        "active_power": [50.0] * 170 + [0.0] * 10 + [50.0] * 20,
    })
    eventos = clasificar_eventos(df, v_base=230.0)
    tipos = {e.tipo for e in eventos}
    assert {"escalon", "hueco_tension", "desconexion"} <= tipos
    assert all(0 < e.confianza <= 1 for e in eventos)


def test_pruebas_incompletas_solo_informa():
    from gcv.evaluation.registry import get_test
    from tests.unit.helpers import make_dataset

    df = pd.DataFrame({"timestamp": ts(10), "frequency": [60.0] * 10})  # sin P
    r = get_test("CE-F-01").run(make_dataset(df), {})
    avisos = pruebas_incompletas([r])
    assert avisos and avisos[0].startswith("CE-F-01")
