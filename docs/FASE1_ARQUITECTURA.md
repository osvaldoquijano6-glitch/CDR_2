# FASE 1 — Arquitectura del Sistema de Verificación de Pruebas de Código de Red

Sistema de verificación automática de pruebas aplicables a Centrales Eléctricas y
Centros de Carga conforme a: Código de Red, Manual Regulatorio de Requerimientos
Técnicos para la Interconexión de Centrales Eléctricas (Manual INTER), Manual
Regulatorio de Requerimientos Técnicos para la Conexión de Centros de Carga
(Manual CONE), Procedimiento para la Declaración de Operación Comercial
(POC / Anexo 5) y protocolos de pruebas aprobados por CENACE.

Documento de diseño. No contiene código de producción; el código inicia en FASE 2.

---

## 1. Decisión de lenguaje: Python vs Java

Decisión: **Python**. Justificación técnica:

| Criterio | Python | Java |
|---|---|---|
| Ecosistema numérico/señales | numpy, scipy, pandas/polars — estándar de facto | Sin equivalente maduro (ND4J marginal) |
| Lectura COMTRADE | `comtrade` / `pycomtrade` disponibles | Implementación propia |
| Gráficas interactivas | plotly nativo | Wrappers inmaduros |
| Reportes Word/PDF/Excel | python-docx, jinja2, weasyprint, xlsxwriter | Apache POI (más verboso), sin plantillas HTML→PDF simples |
| ML de apoyo | scikit-learn, PyTorch | DL4J marginal |
| Base existente | El proyecto legado ya está en Python (≈15 k líneas) | Reescritura total |
| Velocidad de iteración con ingenieros de pruebas | Alta (Streamlit, notebooks) | Baja |

Java solo aventajaría en despliegue empresarial JVM y tipado estricto; ambos se
mitigan con `mypy` + `pydantic` y empaquetado con Docker. El costo de abandonar
la base legada y el ecosistema científico descarta Java.

## 2. Stack de librerías

| Capa | Librería | Uso |
|---|---|---|
| Tabular | **pandas** (base), **polars** opcional | Series de tiempo; polars solo si los registros de 50 ms superan memoria/CPU de pandas |
| Numérico/señales | **numpy**, **scipy** (`signal`, `stats`, `interpolate`) | df/dt, filtrado, detección de escalones, RMS, percentiles |
| Gráficas | **plotly** (evidencia interactiva HTML y estática vía kaleido) | Se sustituye matplotlib del legado; matplotlib se conserva solo mientras migran las 20+ funciones de `core/plot.py` |
| Excel | **openpyxl** (lectura), **xlsxwriter** (reportes) | Entrada .xlsx/.xlsm y matriz de cumplimiento |
| COMTRADE | **comtrade** (PyPI, IEEE C37.111 1991/1999/2013) | Lectura .cfg/.dat (ASCII y binario) |
| Reportes | **jinja2** (plantillas HTML), **weasyprint** (HTML→PDF), **python-docx** (Word) | Informe técnico y ejecutivo |
| Validación/config | **pydantic v2**, **PyYAML** | Modelos de datos, matriz normativa, mapeos manuales |
| ML opcional | **scikit-learn** (IsolationForest, DBSCAN, RandomForest), **rapidfuzz** (similitud de encabezados) | Solo apoyo; nunca dictamen. PyTorch queda fuera del núcleo: se justificaría únicamente si un clasificador de eventos supera a los métodos clásicos |
| Calidad | **pytest**, **ruff**, **mypy** | Unit tests, lint, tipado |
| UI prototipo | **streamlit** | Ya usado en el legado |
| UI profesional | **FastAPI + Dash** (o frontend separado) | Fase posterior |

## 3. Auditoría del proyecto legado y mapa de reutilización

El repositorio contiene la versión previa (commit "Add files via upload"):
`app.py` (5 657 líneas, monolito Streamlit), `app_RECU.py` y `app.py.backup`
(versiones muertas), `core/` (io, depur, droop, merge, annotate, plot, export,
naming), `tests/` (registry, simple, multi, multi_zones — motores de prueba, no
unit tests), `components/`, `projects/`.

### 3.1 Qué SÍ se reutiliza (con refactor)

| Módulo legado | Valor | Destino en nueva arquitectura |
|---|---|---|
| `core/io.py` — parsing robusto de fechas (AM/PM español, day-first vs month-first con función de score `_datetime_parse_score`), detección de separador CSV, lector XLSX por XML sin openpyxl, detección de columnas por tokens | **Alto**. El heurístico de desambiguación día/mes es trabajo real ya validado en campo | `src/gcv/ingestion/` + `src/gcv/normalization/timestamps.py` |
| `core/depur.py` — recorte de ventanas temporales sobre registros de día completo (CutJob), alineación de fecha | **Alto** | `src/gcv/signal_processing/windows.py` |
| `core/droop.py` — modelo droop piecewise, detección de segmentos estables, derivación de P_op, curva teórica, evaluación de error con semáforo | **Alto**. Es el embrión del motor de evaluación de P3/P8/P9 | `src/gcv/evaluation/frequency/droop.py`; los parámetros numéricos (59.49/59.97/60.03/62.70 Hz, estatismos 3/5/8 %, banda muerta 0.030 Hz) **salen del código** y pasan a la matriz normativa con su fuente documental |
| `core/merge.py` — fusión de series POI/GEN con tolerancia temporal, reescalado kW/MW | **Medio** | `src/gcv/normalization/merge.py` |
| `tests/registry.py` — catálogo de pruebas P1–P28 con conclusiones | **Medio**. La estructura (registro central declarativo) es correcta; el contenido migra a la matriz normativa YAML con campos de trazabilidad que hoy no tiene (numeral, fuente, criterio cuantitativo) | `normative/matriz_pruebas.yaml` + `src/gcv/evaluation/registry.py` |
| `tests/simple.py`, `multi.py`, `multi_zones.py` — lógica de casos por estatismo, SIGNAL_SPECS (alias de señales) | **Medio**. SIGNAL_SPECS es la semilla del diccionario de alias | `src/gcv/normalization/aliases.py` y clases de prueba en `src/gcv/evaluation/` |
| `core/naming.py` — nombres de artefactos trazables (proyecto_prueba_fecha) | **Medio** | `src/gcv/utils/naming.py` |
| `core/export.py` — escritura XLSX por XML, cálculo de potencia esperada con droop | **Bajo/Medio**. La escritura XML se reemplaza por xlsxwriter; `compute_expected_power_with_droop` migra a evaluation | `src/gcv/reporting/excel.py` |
| `projects/*/metadata.json`, `cronograma.json` | **Medio**. Esquema de proyecto ya en uso; se formaliza con pydantic | `src/gcv/app/project_store.py` |

### 3.2 Qué NO se reutiliza

| Elemento | Razón |
|---|---|
| `app.py` monolito | Mezcla UI, cálculo, criterio normativo y reporte en un archivo; se descompone. La UI nueva solo orquesta |
| `app_RECU.py`, `app.py.backup` | Versiones muertas → se archivan en `legacy/` y se eliminan del árbol activo |
| `core/plot.py` (matplotlib, 1 298 líneas) | Se migra a plotly por requerimiento; sirve como especificación visual de cada gráfica |
| Conclusiones de `tests/registry.py` tal cual | Son texto fijo que afirma cumplimiento sin cálculo. En el nuevo motor la conclusión se **genera** a partir del resultado y siempre cita numeral |
| `__pycache__/` versionado | Eliminado del control de versiones en esta fase |

### 3.3 Deudas detectadas en el legado (a resolver en FASE 2–3)

1. Los umbrales normativos están embebidos en código (`droop.py`, `app.py`) sin
   cita de numeral → van a la capa normativa.
2. No hay bitácora de limpieza: las transformaciones (dropna, dedup, reescala
   kW→MW) se aplican silenciosamente.
3. No hay unit tests (la carpeta `tests/` son motores de prueba de campo).
4. Sin soporte COMTRADE ni CSV de analizadores (Elspec/Hioki/SEL/PMU) con
   encabezados desplazados.
5. Resultado sin estados: el legado siempre "concluye"; falta
   `No evaluable` / `Pendiente documental`.

## 4. Arquitectura por capas y estructura de carpetas

```
CDR_2/
├── normative/                      # CAPA 1 · NORMATIVA (datos, no código)
│   ├── matriz_pruebas.yaml         #   matriz maestra de pruebas (fuente única de criterios)
│   ├── limites/                    #   tablas de límites por numeral (frecuencia, tensión, armónicos…)
│   └── fuentes/                    #   registro de documentos: título, versión, fecha DOF, hash
├── src/gcv/                        # paquete instalable (grid code verification)
│   ├── config/                     #   settings, carga/validación YAML (pydantic)
│   ├── ingestion/                  # CAPA 2 · LECTURA
│   │   ├── base.py                 #   Reader → RawDataset
│   │   ├── excel_reader.py         #   .xlsx/.xlsm, detección de hoja y encabezado desplazado
│   │   ├── csv_reader.py           #   separador, encoding, metadatos de analizadores
│   │   └── comtrade_reader.py      #   .cfg/.dat → canales analógicos/digitales
│   ├── normalization/              # CAPA 3 · NORMALIZACIÓN
│   │   ├── aliases.py              #   diccionario de alias de señales
│   │   ├── header_detect.py        #   detección de fila de encabezado
│   │   ├── column_mapper.py        #   mapeo columna origen → señal canónica
│   │   ├── units.py                #   homologación V/kV/pu, A/kA, W/kW/MW, var/kvar/MVAr, s/ms/min
│   │   ├── timestamps.py           #   parsing multi-formato, TZ, fecha+hora separadas
│   │   ├── sampling.py             #   fs detectada, huecos, saltos, no-monotonía
│   │   ├── cleaning.py             #   NaN, duplicados, outliers; correcciones desde YAML/JSON
│   │   └── audit.py                #   CleaningLog: bitácora de toda transformación
│   ├── signal_processing/          # CAPA 4 · CÁLCULO ELÉCTRICO
│   │   ├── windows.py              #   recorte por fecha/hora (hereda depur.py)
│   │   ├── steps.py                #   detección de escalones, t1/t2, tiempos de respuesta
│   │   ├── derivatives.py          #   df/dt (ROCOF) con ventana configurable
│   │   ├── ramps.py                #   MW/min, %Pn/min
│   │   ├── statistics.py           #   RMS, promedios por ventana, percentiles, permanencia en banda
│   │   └── events.py               #   desconexión, disparo, pérdida de señal, sag/swell
│   ├── quality_power/              #   armónicos, THD/TDD, desbalance, flicker Pst/Plt, RVC, DC
│   ├── evaluation/                 # CAPA 5 · MOTOR DE REGLAS (determinístico)
│   │   ├── result.py               #   TestResult, Verdict, Evidence
│   │   ├── base.py                 #   BaseTest: validate→preprocess→calculate→evaluate→outputs
│   │   ├── registry.py             #   carga matriz_pruebas.yaml, resuelve pruebas aplicables
│   │   ├── applicability.py        #   Tipo A/B/C/D, síncrona/asíncrona, CE/CC
│   │   ├── frequency/              #   rango f, ROCOF, alta/baja f, CPF, CSF, P constante, rampas
│   │   ├── voltage/                #   rango V, reactivos, P-Q, V-Q, control V/Q/FP, falla dinámica
│   │   ├── power_quality/          #   evaluadores que consumen quality_power/
│   │   ├── documental/             #   checklist: modelos, protecciones, ajustes, instrumentación
│   │   └── load_center/            #   pruebas de Centro de Carga (Manual CONE)
│   ├── visualization/              # CAPA 6 · GRÁFICAS (plotly; especificación visual del legado)
│   ├── reporting/                  # CAPA 7 · REPORTES (jinja2 → HTML/PDF, docx, xlsx)
│   ├── ml/                         # CAPA 8 · ML DE APOYO (nunca dictamina)
│   ├── validation/                 #   validadores transversales de calidad de datos
│   ├── utils/
│   └── app/                        # CAPA 9 · INTERFAZ
│       ├── streamlit/              #   prototipo (migración del app.py actual)
│       └── api/                    #   FastAPI (versión profesional, fase posterior)
├── tests/                          # unit tests pytest (espejo de src/gcv)
├── legacy/                         # proyecto anterior congelado como referencia
├── data/examples/                  # archivos de ejemplo anonimizados
├── projects/                       # proyectos de usuario (metadata, bitácoras, salidas)
└── docs/
```

Reglas de dependencia entre capas (se verifican con import-linter en CI):

- `normative/` son **datos**; solo `evaluation/registry.py` y `config/` los leen.
- `ingestion` no conoce señales canónicas; entrega crudo + metadatos.
- `normalization` no conoce pruebas; entrega `NormalizedDataset` + `CleaningLog`.
- `signal_processing` y `quality_power` son funciones puras sobre arrays/series,
  sin criterio de aceptación.
- `evaluation` es la única capa que compara contra límites y emite veredicto.
- `ml` puede leer todo, pero ninguna capa depende de `ml` para un veredicto.
- `reporting`/`visualization` solo consumen `TestResult`; no calculan.

## 5. Modelo de datos

Entidades (pydantic; persistencia inicial en JSON/YAML por proyecto, portable a SQLite):

```
Project              proyecto de verificación
 ├─ id, nombre, cliente, responsable, fecha
 ├─ installation: Installation
 ├─ sources: [DataSource]
 ├─ test_runs: [TestRun]
 └─ audit_trail: [AuditEvent]

Installation         instalación bajo prueba
 ├─ kind: CENTRAL_ELECTRICA | CENTRO_DE_CARGA
 ├─ tech: SINCRONA | ASINCRONA | MIXTA          (solo CE)
 ├─ category: A | B | C | D                     (según capacidad neta y área síncrona)
 ├─ area_sincrona: SIN | BCA | BCS | MULEGE
 ├─ capacidad_instalada_neta_mw, tension_poi_kv, f_nominal_hz = 60
 └─ punto_interconexion: str

DataSource           archivo cargado
 ├─ id, path, formato: XLSX|XLSM|CSV|COMTRADE, sha256, equipo_origen
 ├─ raw_meta: hojas, encabezados originales, unidades declaradas, tz
 └─ channel_map: [ChannelMapping]

ChannelMapping       trazabilidad columna → señal
 ├─ columna_original, unidad_original
 ├─ senal_canonica (ej. "frequency", "voltage_ab", "active_power")
 ├─ unidad_canonica, factor_conversion
 └─ metodo: AUTO_ALIAS | AUTO_ML_SUGERIDO | MANUAL   (si ML sugiere, usuario confirma)

NormalizedDataset    resultado de normalización
 ├─ df (índice datetime UTC-aware, columnas canónicas)
 ├─ fs_detectada_hz, huecos: [GapInfo], calidad: DataQualityReport
 └─ cleaning_log: CleaningLog                  (toda transformación: qué, por qué, cuántas filas)

TestSpec             fila de la matriz normativa (ver §6) — se carga, no se escribe en código

TestRun              ejecución de una prueba
 ├─ test_id, spec_version, inputs: [DataSource.id], ventanas, parámetros
 └─ result: TestResult

TestResult
 ├─ test_id, test_name, status: CUMPLE | NO_CUMPLE | NO_EVALUABLE | PENDIENTE_DOCUMENTAL
 ├─ measured_values: {nombre: valor+unidad}
 ├─ required_limits: {nombre: límite+unidad+numeral}
 ├─ pass_fail_details: [CriterionCheck]        (cada criterio individual con su comparación)
 ├─ warnings: [str]
 ├─ normative_reference: [NormRef(documento, numeral, versión)]
 ├─ plots: [Evidence], tables: [Evidence]
 └─ conclusion: str                            (generada desde el resultado, no texto fijo)
```

Invariante de trazabilidad: desde cualquier número del informe final se puede
recorrer `TestResult → TestRun → NormalizedDataset.cleaning_log →
ChannelMapping → DataSource.sha256` hasta el archivo y columna originales.

## 6. Matriz normativa maestra

Entregada en `normative/matriz_pruebas.yaml` (versión inicial, este mismo commit).
Campos por prueba: `id`, `nombre`, `aplica_a`, `categorias` (A/B/C/D),
`tecnologia` (síncrona/asíncrona/ambas), `manual_referencia`, `numeral`,
`fuente_documental`, `variables_requeridas`, `unidad_esperada`,
`fs_minima_sugerida_hz`, `duracion_minima`, `criterio_aceptacion`,
`formula_algoritmo`, `evidencia_requerida`, `tipo_salida`,
`resultados_posibles`, `estado_normativo`, `observaciones`.

Reglas de llenado aplicadas (y obligatorias hacia adelante):

1. **Ningún valor inventado.** Todo límite tiene `fuente_documental` o está
   marcado `estado_normativo: PENDIENTE_VALIDACION_NORMATIVA` con el campo
   `dato_requerido` describiendo exactamente qué numeral/valor falta capturar.
2. Los parámetros heredados del código legado (bandas de `droop.py`, casos de
   estatismo 3/5/8 %, ROCOF 2.0 Hz/s) se marcan
   `estado_normativo: HEREDADO_PROTOCOLO_SIN_CITA` — existen en protocolos ya
   usados en campo, pero deben confirmarse contra el numeral antes de
   considerarse validados.
3. El motor de reglas rehúsa emitir `CUMPLE/NO_CUMPLE` si la prueba tiene
   criterio en estado pendiente: el resultado forzado es `NO_EVALUABLE` con la
   causa "criterio normativo pendiente de validación".

## 7. Flujo de procesamiento

```
[1] Crear proyecto ─ tipo instalación, categoría A–D, tecnología, área síncrona
        │
[2] Cargar archivos ─ ingestion: sha256, formato, hojas, metadatos
        │
[3] Normalizar ─ detectar encabezado → mapear columnas (alias / ML sugiere /
        │        usuario confirma) → homologar unidades → parsear timestamps
        │        (TZ, fecha+hora separadas) → detectar fs, huecos, duplicados,
        │        outliers, no-monotonía → aplicar correcciones YAML del usuario
        │        → CleaningLog
        │
[4] Determinar pruebas aplicables ─ evaluation.applicability × matriz normativa
        │
[5] Configurar cada prueba ─ ventanas de tiempo, parámetros del protocolo
        │        (estatismo, P_ref, consignas), archivos asignados
        │
[6] Ejecutar motor de reglas ─ por prueba:
        │        validate_inputs → preprocess → calculate → evaluate →
        │        generate_outputs (TestResult con evidencia)
        │
[7] Revisar ─ UI muestra resultado, gráficas plotly, advertencias, trazabilidad
        │
[8] Reportar ─ ejecutivo, técnico completo, anexo de datos, bitácora,
                 matriz de cumplimiento XLSX, HTML interactivo, Word/PDF
```

Contrato del motor (formaliza el esqueleto solicitado; código en FASE 2):

```python
class BaseTest(ABC):
    spec: TestSpec                          # fila de la matriz normativa
    def validate_inputs(ds) -> list[InputIssue]   # señales, fs, duración mínimas
    def preprocess(ds) -> WorkingData             # ventanas, remuestreo declarado
    def calculate(wd) -> MeasuredValues           # solo números, sin juicio
    def evaluate(mv) -> list[CriterionCheck]      # comparación contra spec, cita numeral
    def generate_outputs(...) -> TestResult       # gráficas, tablas, conclusión generada
```

## 8. Módulo ML (alcance y frontera)

Usos permitidos: detección de anomalías en series (IsolationForest / reglas
estadísticas robustas), clasificación de eventos (escalón, hueco, desconexión,
ruido, saturación, pérdida de comunicación) con features determinísticas,
sugerencia de mapeo de columnas por similitud (rapidfuzz + embeddings ligeros),
recomendación de limpieza y detección de pruebas incompletas.

Frontera dura: la salida ML es siempre `sugerencia` con `confianza` y requiere
confirmación del usuario cuando altera datos o mapeos; jamás participa en
`evaluate()`. El informe distingue "anomalía detectada (apoyo ML)" de
"incumplimiento normativo (regla determinística)".

## 9. Riesgos técnicos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| 1 | Ambigüedad día/mes en timestamps (heurístico puede fallar en registros cortos) | Ventanas mal recortadas → veredicto erróneo | Score del legado + declaración explícita de formato por fuente en el proyecto; advertencia bloqueante si la confianza es baja |
| 2 | fs insuficiente para la prueba (ej. ROCOF con datos de 1 s) | Resultado inválido | `fs_minima_sugerida` en matriz; `validate_inputs` degrada a NO_EVALUABLE |
| 3 | Flicker Pst/Plt: cálculo IEC 61000-4-15 requiere forma de onda o Pst ya calculado por el analizador | No reproducible desde RMS lentos | Aceptar Pst/Plt pre-calculados del equipo (con trazabilidad) y calcular solo si hay muestreo suficiente |
| 4 | Volumen: registros de 50 ms de día completo (~1.7 M filas/canal) | Memoria/latencia en Streamlit | Lectura por chunks, pyarrow, downsampling solo para render (nunca para cálculo); polars si se confirma cuello |
| 5 | COMTRADE con .cfg inconsistente o binario no estándar | Fallo de ingesta | Validación de .cfg contra .dat, tests con archivos reales de SEL/registradores |
| 6 | Criterios normativos incompletos o versiones distintas de manuales | Dictamen indefendible | `estado_normativo` por prueba + registro de fuentes con versión/fecha DOF; motor bloquea veredicto sin cita |
| 7 | Mezcla de unidades no declarada (kW vs MW en la misma columna, pu sin base) | Errores de magnitud ×1000 | Homologación con detección de rango físico plausible + confirmación del usuario; bitácora registra el factor aplicado |
| 8 | Relojes distintos entre POI y GEN / TZ | Desalineación de series | Tolerancia de merge configurable (legado ya la tiene), reporte de offset detectado |
| 9 | Migración del monolito rompe flujo actual de usuarios | Pérdida de funcionalidad en transición | El legado queda congelado en `legacy/` y operable; la nueva app alcanza paridad por prueba antes de retirar la vieja |

## 10. Pendientes normativos a validar (por el usuario)

El sistema no puede darlos por buenos sin la cita exacta. Cada uno está
referenciado desde la matriz:

1. **Clasificación A/B/C/D**: umbrales de capacidad instalada neta por área
   síncrona (SIN, BCA, BCS, Mulegé) — numeral del Manual INTER.
2. **Rango de frecuencia**: bandas de operación continua y tiempos mínimos de
   permanencia por banda (tabla del Manual INTER / Código de Red) para cada
   categoría.
3. **ROCOF**: valor de inmunidad exigido (el protocolo legado usa 2.0 Hz/s) y
   ventana de medición del df/dt — numeral y método de cálculo.
4. **Alta/baja frecuencia**: umbrales de activación (legado: 60.20 / 59.80 Hz),
   bandas muertas permitidas, estatismos admisibles (legado: 3–8 %) y
   tolerancias de la respuesta — numeral.
5. **CPF**: tiempos de respuesta requeridos (t1, t2, establecimiento),
   tolerancia de potencia entregada vs teórica, banda muerta máxima.
6. **CSF**: aplicabilidad por categoría y requisitos (AGC) — numeral.
7. **Rango de tensión en POI**: tabla de bandas (pu) vs tiempos de permanencia
   por nivel de tensión — numeral.
8. **Capacidad de potencia reactiva**: forma exigida de la curva P-Q/Pmáx y
   V-Q/Pmáx por categoría y tecnología — numeral.
9. **Factor de potencia** (CE en POI y CC): rango obligatorio y base de medición
   (promedio, intervalo de demanda) — numeral del Manual CONE para CC.
10. **Armónicos**: tabla de límites individuales y THD/TDD por nivel de tensión
    y corriente de cortocircuito (Código de Red / referencia IEEE 519 si el
    manual la invoca) — confirmar tabla exacta aplicable.
11. **Flicker**: límites Pst/Plt y método (IEC 61000-4-15) — numeral.
12. **Desbalance**: definición exacta (componentes simétricas vs NEMA) y límite
    (%) — numeral.
13. **Variaciones rápidas de tensión**: límite (% y frecuencia de ocurrencia) —
    numeral.
14. **Inyección de CD**: límite (% de corriente nominal) y aplicabilidad — numeral.
15. **Hueco de tensión / comportamiento dinámico ante falla**: curva LVRT/HVRT
    (tensión vs tiempo) por categoría — numeral.
16. **Centros de Carga**: lista completa de requisitos del Manual CONE por
    nivel de tensión y demanda contratada (tensión, frecuencia, corto circuito,
    protecciones, control, intercambio de información, calidad, modelos, plan
    de trabajo) — numerales.
17. **POC/Anexo 5**: mapeo oficial P1…P28 → numerales del Manual INTER
    (el legado usa esos IDs sin cita).

Formato de captura: por cada punto, el usuario entrega documento + numeral +
valor; se registra en `normative/fuentes/` y la prueba pasa de
`PENDIENTE_VALIDACION_NORMATIVA` a `VALIDADO`.

## 11. Plan de fases

| Fase | Entregable | Estado |
|---|---|---|
| 1 | Este documento + matriz normativa inicial + limpieza de repo | **Entregada** |
| 2 | Esqueleto `src/gcv/`, modelos pydantic, lectores Excel/CSV/COMTRADE, normalizador de columnas y unidades, validador de timestamps, CleaningLog, motor de reglas base, unit tests | Pendiente |
| 3 | Pruebas prioritarias: rango f, ROCOF, alta/baja f, CPF, rango V, FP, capacidad reactiva, armónicos, flicker (si hay datos), variaciones rápidas, desbalance, capacidad instalada neta, calidad CC | Pendiente |
| 4 | Reportes (ejecutivo, técnico, anexos, bitácora, matriz XLSX), gráficas plotly, export Word/PDF/HTML | Pendiente |
| 5 | Módulo ML de apoyo + validación cruzada con reglas | Pendiente |
