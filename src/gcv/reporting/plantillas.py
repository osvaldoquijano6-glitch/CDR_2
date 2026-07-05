"""Plantillas de texto por prueba (objetivo y conclusión de cumplimiento).

Textos tomados de los catálogos validados (01/02/03 *.md), que a su vez citan
el Manual INTE [1] y el POC/Anexo 5 [2]. Placeholders estilo {{NOMBRE_CE}}.
Regla del catálogo: nunca incluir nombres de clientes, empresas o marcas.

La conclusión de plantilla SOLO se usa cuando el resultado es CUMPLE; en
NO_CUMPLE / NO_EVALUABLE se conserva la conclusión generada por el motor
(que enumera los criterios fallidos o la causa).
"""

from __future__ import annotations

import re

from gcv.evaluation.result import TestResult, TestStatus

OBJETIVOS: dict[str, str] = {
    "CE-F-01": ("Verificar que la Central Eléctrica {{NOMBRE_CE}} permanezca interconectada y en "
                "operación dentro de los rangos de frecuencia y tiempos de permanencia establecidos "
                "en la Sección 2.1 del Manual Regulatorio [1], conforme a la Prueba No. 1 del Anexo 5 [2]."),
    "CE-F-02": ("Verificar que la Central Eléctrica {{NOMBRE_CE}} se mantenga interconectada ante "
                "razones de cambio de frecuencia de hasta 2.5 Hz/s medidas en ventana de 200 ms, "
                "conforme a la Sección 2.2.1 [1] y la Prueba No. 2 del Anexo 5 [2]."),
    "CE-F-03": ("Verificar la reducción de potencia activa de la Central Eléctrica {{NOMBRE_CE}} ante "
                "alta frecuencia, con característica de regulación seleccionable, conforme a las "
                "Secciones 2.2.2 a 2.2.4 [1] y la Prueba No. 3 del Anexo 5 [2]."),
    "CE-F-04": ("Verificar el incremento de potencia activa de la Central Eléctrica {{NOMBRE_CE}} ante "
                "baja frecuencia, conforme a la Sección 2.2.4 [1] y la Prueba No. 8 del Anexo 5 [2]."),
    "CE-F-05": ("Verificar el Control Primario de Frecuencia de la Central Eléctrica {{NOMBRE_CE}} "
                "(estatismo, banda muerta y tiempos de respuesta de la Tabla 2.2.2.A [1]), conforme "
                "a la Prueba No. 9 del Anexo 5 [2]."),
    "CE-F-08": ("Verificar la limitación total/parcial de potencia activa de la Central Eléctrica "
                "{{NOMBRE_CE}} ante instrucción, conforme a las Secciones 2.2.5 y 2.2.6 [1]."),
    "CE-F-10": ("Verificar la reconexión automática de la Central Eléctrica {{NOMBRE_CE}} y la rampa "
                "de toma de carga, conforme a la Sección 2.2.8 [1] y la Prueba No. 6 del Anexo 5 [2]."),
    "CE-V-01": ("Verificar que la Central Eléctrica {{NOMBRE_CE}} opere dentro de los rangos de "
                "tensión del Punto de Interconexión de la Tabla 3.1.1 [1], conforme a las Pruebas "
                "11/12 del Anexo 5 [2]."),
    "CE-V-04": ("Verificar el modo de control de tensión de la Central Eléctrica {{NOMBRE_CE}} "
                "(t90 ≤ 3 s, estabilización ≤ 5 s, error ≤ 0.5 %), conforme a la Sección 3.5.3 [1]."),
    "CE-V-05": ("Verificar el modo de control de potencia reactiva de la Central Eléctrica "
                "{{NOMBRE_CE}}, conforme a la Sección 3.5.3 [1]."),
    "CE-V-06": ("Verificar el modo de control de factor de potencia de la Central Eléctrica "
                "{{NOMBRE_CE}}, conforme a la Sección 3.5.3 [1]."),
    "CE-V-07": ("Verificar el comportamiento de la Central Eléctrica {{NOMBRE_CE}} ante huecos de "
                "tensión, permaneciendo dentro de la Zona A del Capítulo 4 [1], conforme a la "
                "Prueba No. 20 del Anexo 5 [2]."),
    "CE-P-01": ("Verificar la Capacidad Instalada Neta comprometida de la Central Eléctrica "
                "{{NOMBRE_CE}} mediante operación acumulada conforme a la Prueba No. 25 del Anexo 5 [2]."),
    "CE-Q-01": ("Verificar el desbalance máximo de tensión en el Punto de Interconexión de "
                "{{NOMBRE_CE}}, conforme a la Sección 7.1 [1] y la Prueba No. 26 del Anexo 5 [2]."),
    "CE-Q-02": ("Verificar la severidad del parpadeo (Pst/Plt) en el Punto de Interconexión de "
                "{{NOMBRE_CE}}, conforme a la Sección 7.2 [1]."),
    "CE-Q-03": ("Verificar las variaciones rápidas de tensión en el Punto de Interconexión de "
                "{{NOMBRE_CE}}, conforme a la Sección 7.3 [1]."),
    "CE-Q-04": ("Verificar la distorsión armónica de tensión (THD e individuales) en el Punto de "
                "Interconexión de {{NOMBRE_CE}}, conforme a la Sección 7.4 [1]."),
    "CE-Q-05": ("Verificar la distorsión armónica de corriente (DATD e individuales, Tablas "
                "2.8.A/B/C) en el punto de conexión de {{NOMBRE_CE}}."),
    "CC-04": ("Confirmar que el Centro de Carga {{NOMBRE_CE}} mantiene el factor de potencia en el "
              "Punto de Conexión dentro del rango del Numeral 2.4 del Manual CONE, con medición "
              "cinco-minutal y cumplimiento mensual ≥ 95 % del tiempo."),
    "CC-08": ("Confirmar que el Centro de Carga {{NOMBRE_CE}} cumple los límites de calidad de la "
              "energía en el Punto de Conexión (Numeral 2.8 del Manual CONE), garantizando que su "
              "operación no genere perturbaciones a la Red Nacional de Transmisión."),
}

CONCLUSIONES_CUMPLE: dict[str, str] = {
    "CE-F-01": ("Ante las variaciones de frecuencia aplicadas, la central se mantiene en operación en "
                "todo momento, sin disparos ni desconexiones, con comportamiento estable en cada "
                "escalón evaluado, cumpliendo satisfactoriamente la prueba."),
    "CE-F-02": ("Al aplicar las rampas de frecuencia correspondientes, la central mantiene operación "
                "continua sin desconexiones ni actuación indebida de protecciones. Se concluye que la "
                "central cumple los criterios de permanencia ante cambios rápidos de frecuencia."),
    "CE-F-03": ("La potencia activa disminuye de manera progresiva y proporcional ante los incrementos "
                "de frecuencia, coherente con la lógica del control primario. La central mantiene "
                "operación continua, por lo que cumple los criterios de respuesta ante alta frecuencia."),
    "CE-F-04": ("La Central Eléctrica incrementa su potencia activa de forma progresiva conforme la "
                "frecuencia disminuye por debajo del umbral de activación, con pendiente conforme al "
                "estatismo configurado y sin disparos, cumpliendo los criterios de respuesta ante "
                "baja frecuencia."),
    "CE-F-05": ("La central responde de manera automática y proporcional ante desviaciones de "
                "frecuencia, siguiendo la pendiente del estatismo configurado, con operación estable "
                "y funcionamiento correcto de la banda muerta. Se valida el cumplimiento de los "
                "criterios de control primario de frecuencia."),
    "CE-F-10": ("Tras la condición de desconexión, la central restablece su operación al retornar las "
                "variables a condiciones normales, con rampa controlada por debajo del 10 % de la "
                "Capacidad Instalada Neta por minuto, confirmando el cumplimiento de los criterios de "
                "reconexión automática y control de rampa."),
    "CE-V-01": ("Ante las variaciones de tensión en el punto de interconexión, la central mantiene "
                "operación continua dentro del rango evaluado, sin desconexiones ni actuación indebida "
                "de protecciones. Se confirma el cumplimiento de los criterios de operación ante "
                "variaciones de tensión en el PI."),
    "CE-V-07": ("Los registros demuestran que la central permanece conectada dentro de la Zona A "
                "definida en el Capítulo 4 del Código de Red durante el evento evaluado, cumpliendo "
                "los criterios de comportamiento ante huecos de tensión."),
    "CE-Q-04": ("Los parámetros de distorsión armónica evaluados se mantuvieron dentro de los umbrales "
                "normativos durante el periodo de medición, por lo que se cumple con los "
                "Requerimientos de Calidad de la Potencia del Código de Red 2.0."),
    "CC-04": ("Las muestras cinco-minutales del periodo se mantuvieron dentro del criterio normativo "
              "de factor de potencia, superando el umbral de cumplimiento del 95 % mensual. En "
              "consecuencia, el Centro de Carga cumple satisfactoriamente con el Numeral 2.4 del "
              "Manual CONE durante el periodo evaluado."),
}

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _render(texto: str, valores: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: valores.get(m.group(1), m.group(0)), texto)


def objetivo(test_id: str, nombre_instalacion: str) -> str | None:
    plantilla = OBJETIVOS.get(test_id)
    return _render(plantilla, {"NOMBRE_CE": nombre_instalacion, "NOMBRE_CC": nombre_instalacion}) \
        if plantilla else None


def conclusion(result: TestResult, nombre_instalacion: str) -> str:
    """Conclusión de plantilla si CUMPLE y existe; si no, la generada por el motor."""
    if result.status == TestStatus.CUMPLE and result.test_id in CONCLUSIONES_CUMPLE:
        return _render(CONCLUSIONES_CUMPLE[result.test_id],
                       {"NOMBRE_CE": nombre_instalacion, "NOMBRE_CC": nombre_instalacion})
    return result.conclusion
