# Entregable de revisión — Estado del diseño al cierre de FASE 3

Propósito: punto de control para reajustar el diseño antes de FASE 4
(reportes/gráficas). Resume qué está construido, qué decisiones de diseño se
tomaron durante la implementación (y en qué difieren de FASE 1), y qué
decisiones quedan abiertas para el usuario.

---

## 1. Qué está construido y probado (79 unit tests en verde)

### Pruebas implementadas en el motor (13 de 35 de la matriz)

| ID | Prueba | Cálculo | Evaluación cuando se valide el numeral |
|---|---|---|---|
| CE-F-01 | Rango de frecuencia | estadísticos de f, permanencia por banda | permanencia ≥ exigida por banda; no-desconexión |
| CE-F-02 | ROCOF | df/dt ventana configurable, pico, episodios de desconexión | severidad del evento ≥ inmunidad y continuidad operativa |
| CE-F-03 | Respuesta alta frecuencia | droop piecewise, P_op derivado, error vs curva teórica | % de muestras en zona activa dentro de tolerancia |
| CE-F-04 | Respuesta baja frecuencia | ídem, zona sub-frecuencia | ídem |
| CE-F-05 | Control primario (CPF) | droop ambas zonas + t1/t2 tras el mayor escalón | ídem + tiempos máximos de respuesta/establecimiento |
| CE-V-01 | Rango de tensión POI | conversión a pu con base explícita, permanencia por banda | permanencia por banda |
| CE-P-01 | Capacidad instalada neta | máxima potencia sostenida (promedio móvil) | sostenida ≥ declarada − tolerancia |
| CC-04 | Factor de potencia CC | FP directo o derivado de P/Q, % en rango | % de intervalos en rango ≥ mínimo |
| CE-Q-01 | Desbalance | NEMA, IEC aproximado (línea-línea) o señal del analizador | percentil ≤ límite con el método normado |
| CE-Q-02 | Flicker | percentiles de Pst/Plt precalculados | Pst/Plt ≤ límites |
| CE-Q-03 | Variaciones rápidas | detección de eventos ΔV/V vs estado estable | nº de eventos ≤ permitido |
| CE-Q-04 | Armónicos de tensión | percentil por armónico + THD | tabla individual + THD |
| CE-Q-05 | Armónicos de corriente | percentil por armónico + TDD | tabla individual + TDD |

### Infraestructura de señales (capa 4, funciones puras)

`signal_processing/`: derivadas (ROCOF), detección de escalones y t1/t2,
droop portado del legado (curva esperada, derivación de P_op en cascada,
error por zona activa), eventos (desconexión, pérdida de señal), estadísticos
(permanencia en bandas, máximos sostenidos). `quality_power/`: armónicos,
desbalance NEMA/IEC, RVC.

## 2. Decisiones de diseño tomadas en FASE 3 (revisables)

| # | Decisión | Alternativa descartada | Impacto si se reajusta |
|---|---|---|---|
| D1 | El criterio droop se evalúa como **% de muestras en zona activa dentro de ±tolerancia** (llaves `tolerancia_pct_pref` + `cumplimiento_minimo_pct`) | error máximo absoluto único | Bajo: es una llave de la matriz, no código; puede convivir con un criterio de error máximo si el numeral lo exige |
| D2 | ROCOF exige **dos criterios**: severidad alcanzada por el evento Y continuidad operativa | solo continuidad | Bajo: si el protocolo no exige demostrar la severidad, se elimina la llave `severidad_minima_hz_s` |
| D3 | t1 = primera entrada a banda objetivo; t2 = entrada definitiva (no vuelve a salir) | definiciones IEEE de rise/settling time sobre % del escalón | Medio: si el numeral define t1/t2 de otra forma, se ajusta `signal_processing/steps.py` (una función, con tests) |
| D4 | P_op se deriva de la cascada del legado (segmento estable → puntos ~60 Hz → mediana inicial), con override por parámetro `p_op_mw` | exigir siempre P_op declarado | Nulo: ya soporta ambos |
| D5 | La conversión a pu **siempre exige base explícita** (`v_base_v` como parámetro); sin base la prueba es NO_EVALUABLE | inferir base del valor típico | Nulo: es la postura conservadora correcta para auditoría |
| D6 | FP derivado de P/Q como **magnitud** cuando no hay señal de FP, con advertencia sobre convención de signos | rechazar si no hay señal FP | Bajo: la convención (inductivo/capacitivo) se fija al validar el numeral CONE |
| D7 | Armónicos exigidos por tabla pero **sin medición → check no evaluable con advertencia** (no bloquea el veredicto de los presentes) | degradar toda la prueba a NO_EVALUABLE | Medio: es política de dictamen; ver decisión abierta A2 |
| D8 | CE-F-03/04/05 comparten `DroopTestBase`; CE-Q-04/05 comparten `_ArmonicosBase` | clases independientes | Nulo: refactor interno |

### Desviaciones respecto a FASE 1

* `evaluation/` usa un módulo suelto `capacidad_instalada.py` para CE-P-01
  (FASE 1 no le asignaba subcarpeta). Si crecen las pruebas de potencia, se
  crea `evaluation/power/`.
* El paquete de pruebas se llama `evaluation/` y no `tests/` (previsto ya en
  FASE 1 para no chocar con pytest y con los motores legados).

## 3. Decisiones abiertas para el usuario (reajuste de diseño)

* **A1 — Criterio droop**: ¿el protocolo CENACE que usan evalúa la respuesta
  droop por banda de tolerancia sobre muestras (D1, como el semáforo del
  legado) o por error máximo puntual? Si es lo segundo, agrego la llave
  `error_max_pct_pref` y el check correspondiente.
* **A2 — Política ante evidencia parcial**: hoy un armónico exigido sin
  medición se excluye del veredicto con advertencia (D7). La alternativa
  estricta (prueba completa NO_EVALUABLE si falta cualquier armónico de la
  tabla) es un cambio de una línea. ¿Cuál es la política de dictamen?
* **A3 — Definición t1/t2**: confirmar contra el protocolo si las definiciones
  operativas de D3 coinciden con las usadas en campo.
* **A4 — Ventana ROCOF**: el df/dt usa 500 ms por defecto (informativo). El
  valor normado debe capturarse en `limites.ventana_rocof_ms` al validar
  CE-F-02.
* **A5 — Zonas del legado (P3Z/P8Z/P9Z)**: el legado tenía variantes "con
  zonas" con semáforo por regiones de la curva. La base droop actual calcula
  el error global en zona activa. ¿Se requiere reproducir el semáforo por
  regiones como salida adicional en FASE 4 (gráficas)?

## 4. Qué desbloquea cada dato normativo pendiente

Sin cambios respecto a FASE 1 §10: los 13 evaluadores están listos y
dictaminarán en cuanto cada prueba reciba documento + numeral + límites en
`normative/matriz_pruebas.yaml` (`estado_normativo: VALIDADO` + bloque
`limites:` con las llaves documentadas en el docstring de cada módulo de
`src/gcv/evaluation/`). No se requiere código nuevo para empezar a dictaminar
las 13 implementadas.

## 5. Pendientes de implementación (no bloquean FASE 4)

* CE-F-06..10 (CSF, P constante, limitación, rampas, reconexión), CE-V-02..07
  (reactivos y controles de tensión), CE-Q-06, documentales y resto de CC:
  siguen el mismo patrón; se agregan al validar sus numerales o al priorizarlas.
* Cálculo espectral desde COMTRADE (armónicos desde forma de onda) y Pst
  propio: condicionados a fs y librería validada (riesgos 3 y 5 de FASE 1).

## 6. Plan FASE 4 (siguiente)

Gráficas plotly por prueba (espec. visual = `core/plot.py` legado), reporte
técnico Word/PDF y ejecutivo, matriz de cumplimiento XLSX, bitácora exportada,
HTML interactivo. La estructura `TestResult` ya contiene todo lo que las
plantillas necesitan; no se anticipan cambios de modelo.
