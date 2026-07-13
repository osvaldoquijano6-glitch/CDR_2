---
name: generar-graficas
description: >-
  Genera la evidencia gráfica de pruebas del Código de Red con Plotly siguiendo
  las convenciones de visualización del proyecto (subgráficas apiladas o doble
  eje excitación/potencia, colores por entidad, límites normativos en rojo
  discontinuo, bandas permitidas en gris). Úsalo cuando el usuario pida crear
  gráficas de una prueba, graficar mediciones (frecuencia, tensión, potencia,
  armónicos, flicker, droop, ROCOF, huecos de tensión) o preparar figuras para
  informes/protocolos. Las gráficas se derivan de un TestResult evaluado, nunca
  inventan límites.
---

# Creación de gráficas de pruebas

Produce figuras Plotly de evidencia para una prueba, consistentes con lo que el
motor evaluó. Módulo: `gcv.visualization` (`plots.py`, `evidence.py`).

## Principio rector (lineamiento del proyecto)

La gráfica **refleja lo evaluado, no lo decora**. Las vistas derivadas (droop
teórico, serie ROCOF) se reconstruyen con las **mismas funciones puras** de capa
4 que usó el motor, parametrizadas desde `result.parametros_ejecucion` y los
valores medidos. **Nunca** dibujes un límite que no venga de la matriz normativa
(`result.required_limits`); si no hay criterio VALIDADO, la prueba es
`NO_EVALUABLE` y la figura solo muestra la medición.

## Convenciones de visualización (obligatorias)

- **Nunca doble eje Y arbitrario.** Señales de distinta magnitud van en
  **subgráficas apiladas** con eje X compartido (`stacked_timeseries`). El único
  doble eje permitido es la convención de reportes: **excitación escalonada**
  (f en Hz o V en pu) a la izquierda + **potencia activa** a la derecha
  (`dual_axis_timeseries`).
- **Colores por entidad, orden fijo** (`plots.SERIES`):
  medición = azul `#2a78d6` · teórica/referencia = ámbar `#eda100` (trazo
  discontinuo) · señal secundaria = aqua `#1baf7a`.
- **Límites normativos**: rojo crítico `#d03b3b` discontinuo (`hlines`).
- **Bandas permitidas**: gris translúcido `rgba(107,107,104,0.12)` (`bands`).
- Marcas de 2 px, retícula recesiva `#e8e7e4`, tooltip unificado (`x unified`).
- La misma paleta rige informes HTML y protocolos.

## Camino recomendado: evidencia automática por prueba

`evidence.build_figures(result, ds, estilo)` ya sabe qué figura corresponde a
cada `test_id` y aplica límites/bandas desde `result.required_limits`:

```python
from gcv.evaluation.registry import get_test
from gcv.visualization.evidence import build_figures

result = get_test("CE-F-03").run(ds)          # ds: NormalizedDataset
figs = build_figures(result, ds, estilo="doble_eje")  # o "apilado"
```

Cobertura actual de `build_figures` (test_id → vista):

| Prueba | Vista |
|---|---|
| CE-F-01 | f(t) + P(t), bandas de frecuencia |
| CE-F-02 | f(t) + ROCOF (ventana) + P(t), inmunidad ±Hz/s |
| CE-F-03/04/05 | droop: f + P medida vs P esperada; dispersión P(f) vs droop teórico |
| CE-V-01 | tensión POI en pu con bandas |
| CE-P-01 | potencia neta vs capacidad declarada |
| CC-04 | factor de potencia con FP mín |
| CE-Q-01/03 | desbalance / tensiones por fase |
| CE-Q-02 | Pst / Plt con límites |
| CE-Q-04/05 | THD/TDD y barras armónicos vs límite |

## Bloques base (`gcv.visualization.plots`) para vistas nuevas

- `stacked_timeseries(df, panels, title)` — paneles con eje X común. Cada panel:
  `{"series": [(col|Series, nombre, rol)], "y_title", "hlines": [(v, etiqueta)], "bands": [(y0, y1, etiqueta)]}`,
  `rol ∈ {"medida","teorica","secundaria"}`.
- `dual_axis_timeseries(df, excitacion, respuestas, title, ...)` — excitación
  escalonada + potencia; anota mesetas (`annotate_steps`) con valor de
  excitación y respuesta asentada.
- `limits_bar(measured, limits, title, y_title)` — medido vs límite (armónicos,
  flicker).
- `scatter_xy(x, y, title, x_title, y_title, curve=...)` — dispersión con curva
  teórica opcional.

## Persistir en el repositorio histórico

Guarda por central para trazabilidad (`projects/<central>/graficas/`):

```python
from gcv.reporting.repositorio import guardar_figuras
guardar_figuras("Central Solar Norte", "CE-F-03", figs, resultado=result.status)
```

Genera un `.html` autocontenible + `.json` por figura y actualiza `indice.json`
(nombres trazables `<CENTRAL>_<PRUEBA>_<AAAAmmdd_HHMMSS>_<n>`).

## Para informes

Las figuras alimentan `ReportContext.figuras[test_id]` y se exportan a
HTML/PDF/Word/Excel vía `gcv.reporting`. Convención de unidades: eje der. en MW
salvo que el título indique MVAr o pu.

## Verificación

- Confirma que todo límite/banda dibujado provenga de `result.required_limits`.
- Si `result.status == "NO_EVALUABLE"`, la figura no debe mostrar líneas de
  criterio: solo la medición.
- Revisa que no haya doble eje fuera de la convención excitación/potencia.
