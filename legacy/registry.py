"""
tests/registry.py — Registro centralizado de las 12 pruebas del Anexo 5.

Reemplaza las 12 carpetas TEMPLATE_Pxx: toda la configuración de cada prueba
(tipo, casos, parámetros, conclusión normativa) vive aquí.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestConfig:
    """Configuración de una prueba del Anexo 5."""
    id: str                              # Clave corta: "P1", "P3", etc.
    nombre: str                          # Nombre completo
    tipo: str                            # "simple" | "multi"
    conclusion: str                      # Texto de conclusión normativa
    casos: list[str] = field(default_factory=list)   # Para tipo "multi": ["3%", "5%", "8%"]
    titulo_template: str = ""            # "{caso}" se reemplaza por el caso actual (multi)
    titulo_simple: str = ""             # Título directo para tipo simple
    power_unit: str = "MW"
    has_aux_col: bool = False            # Si hay columna de setpoint/referencia (P2, P4)

    def titulo(self, caso: str | None = None) -> str:
        if self.tipo == "simple":
            return self.titulo_simple or f"{self.id} – {self.nombre}"
        return self.titulo_template.format(caso=caso or "")


# ─── Catálogo de pruebas ──────────────────────────────────────────────────────
REGISTRY: dict[str, TestConfig] = {

    "P1": TestConfig(
        id="P1",
        nombre="Rango de frecuencia",
        tipo="simple",
        titulo_simple="P1 – Rango de frecuencia",
        conclusion=(
            "La central exhibe continuidad operativa dentro de la banda de frecuencias normada. "
            "La potencia activa se ajusta coherentemente sin desconexiones prematuras."
        ),
    ),

    "P2": TestConfig(
        id="P2",
        nombre="Razón de cambio 2.0 Hz/s (ROCOF)",
        tipo="simple",
        titulo_simple="P2 – Razón de cambio de frecuencia (ROCOF)",
        has_aux_col=True,
        conclusion=(
            "La tasa de cambio (ROCOF) fue calculada y evaluada. La central responde "
            "satisfactoriamente sin disparos de protección ante los eventos de ROCOF registrados."
        ),
    ),

    "P3": TestConfig(
        id="P3",
        nombre="Respuesta a alta frecuencia",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P3 – Respuesta a alta frecuencia · Estatismo {caso}",
        conclusion=(
            "Se detectó el umbral de alta frecuencia. La reducción de potencia activa es coherente "
            "con el estatismo configurado para la zona de sobre-frecuencia."
        ),
    ),

    "P4": TestConfig(
        id="P4",
        nombre="Potencia activa constante (alta frecuencia)",
        tipo="simple",
        titulo_simple="P4 – Potencia activa constante en alta frecuencia",
        has_aux_col=True,
        conclusion=(
            "La potencia activa permanece estable y dentro del margen de tolerancia establecido "
            "durante toda la ventana de alta frecuencia evaluada."
        ),
    ),

    "P6": TestConfig(
        id="P6",
        nombre="Reconexión automática",
        tipo="simple",
        titulo_simple="P6 – Reconexión automática",
        conclusion=(
            "Tras el evento de apertura, la central reconecta automáticamente y recupera la "
            "potencia de manera controlada dentro del tiempo de ramp-up configurado."
        ),
    ),

    "P8": TestConfig(
        id="P8",
        nombre="Respuesta a baja frecuencia",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P8 – Respuesta a baja frecuencia · Estatismo {caso}",
        conclusion=(
            "Se confirma el incremento de potencia activa ante la caída de frecuencia por debajo "
            "del umbral de baja frecuencia, conforme al estatismo declarado."
        ),
    ),

    "P9": TestConfig(
        id="P9",
        nombre="Control primario de frecuencia (CPF)",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P9 – Control primario de frecuencia · Estatismo {caso}",
        conclusion=(
            "El Control Primario de Frecuencia (CPF) está activo. La potencia se modula en "
            "respuesta inversa y proporcional a las variaciones rápidas de frecuencia del POI."
        ),
    ),

    "P12": TestConfig(
        id="P12",
        nombre="Rango de tensión en POI",
        tipo="simple",
        titulo_simple="P12 – Rango de tensión en el Punto de Interconexión",
        conclusion=(
            "Los valores de tensión en el POI se mantienen dentro de los límites declarados; "
            "la central opera sin interrupciones por sobretensión o subtensión transitoria."
        ),
    ),

    "P13": TestConfig(
        id="P13",
        nombre="Capacidad de potencia reactiva",
        tipo="simple",
        titulo_simple="P13 – Capacidad de potencia reactiva",
        conclusion=(
            "Se verifica el rango de suministro e inyección de potencia reactiva; el factor de "
            "potencia cumple con los valores declarados para los niveles de tensión evaluados."
        ),
    ),

    "P25": TestConfig(
        id="P25",
        nombre="Capacidad instalada neta",
        tipo="simple",
        titulo_simple="P25 – Capacidad instalada neta",
        conclusion=(
            "La potencia activa máxima registrada en el POI es representativa de la Capacidad "
            "Instalada Neta declarada para la central."
        ),
    ),

    "P26": TestConfig(
        id="P26",
        nombre="Calidad de la Potencia",
        tipo="simple",
        titulo_simple="P26 – Requerimientos de Calidad de la Potencia",
        conclusion=(
            "Los parámetros de calidad eléctrica evaluados durante la prueba se encuentran "
            "dentro de los límites establecidos por el Código de Red."
        ),
    ),

    "P28": TestConfig(
        id="P28",
        nombre="Control de frecuencia",
        tipo="simple",
        titulo_simple="P28 – Control de frecuencia",
        has_aux_col=True,
        conclusion=(
            "El sistema de control de frecuencia regula la potencia activa de manera proporcional "
            "a las desviaciones de frecuencia detectadas en el POI."
        ),
    ),

    "P3Z": TestConfig(
        id="P3Z",
        nombre="Respuesta a alta frecuencia (con zonas)",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P3Z – Alta frecuencia con zona esperada · Estatismo {caso}",
        conclusion=(
            "Se detecto el umbral de alta frecuencia. La reduccion de potencia activa se evalua "
            "contra la curva teorica de droop para la zona de sobre-frecuencia."
        ),
    ),

    "P8Z": TestConfig(
        id="P8Z",
        nombre="Respuesta a baja frecuencia (con zonas)",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P8Z – Baja frecuencia con zona esperada · Estatismo {caso}",
        conclusion=(
            "Se confirma el incremento de potencia activa ante la caida de frecuencia. "
            "La respuesta se compara contra la curva teorica de droop para zona de baja frecuencia."
        ),
    ),

    "P9Z": TestConfig(
        id="P9Z",
        nombre="Control primario de frecuencia (con zonas)",
        tipo="multi",
        casos=["3%", "5%", "8%"],
        titulo_template="P9Z – CPF con zona esperada · Estatismo {caso}",
        conclusion=(
            "El Control Primario de Frecuencia se evalua contra la curva teorica de droop. "
            "La respuesta en banda muerta y zonas de operacion se valida con semafaro de errores."
        ),
    ),
}

# Orden de display en la UI
DISPLAY_ORDER = ["P1", "P2", "P3", "P4", "P6", "P8", "P9", "P12", "P13", "P25", "P26", "P28", "P3Z", "P8Z", "P9Z"]

SIMPLE_TESTS = [k for k in DISPLAY_ORDER if REGISTRY[k].tipo == "simple"]
MULTI_TESTS  = [k for k in DISPLAY_ORDER if REGISTRY[k].tipo == "multi"]


def get_test(test_id: str) -> TestConfig:
    if test_id not in REGISTRY:
        raise KeyError(f"Prueba '{test_id}' no encontrada. Disponibles: {list(REGISTRY)}")
    return REGISTRY[test_id]


def display_name(test_id: str) -> str:
    cfg = get_test(test_id)
    return f"{cfg.id} – {cfg.nombre}"
