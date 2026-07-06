# CDR_2 — Verificación de Pruebas de Código de Red

Sistema en Python para verificar pruebas aplicables a Centrales Eléctricas y
Centros de Carga conforme al Código de Red, Manual INTER, Manual CONE y
POC/Anexo 5. Procesa Excel/CSV/COMTRADE, normaliza y depura datos con bitácora
trazable, evalúa criterios de aceptación de forma determinística y genera
evidencia e informes.

**Versión 1.0** — ver [docs/VERSION_1.md](docs/VERSION_1.md) (alcance, pendientes urgentes y mejoras futuras).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura + matriz normativa ([docs/FASE1_ARQUITECTURA.md](docs/FASE1_ARQUITECTURA.md)) | ✅ |
| 2 | Paquete `src/gcv`: lectores, normalización, motor de reglas, unit tests | ✅ |
| 3 | Pruebas prioritarias: 13 evaluadores (frecuencia, ROCOF, droop, tensión, FP, capacidad, armónicos, flicker, desbalance, RVC) — ver [docs/FASE3_ESTADO_DISENO.md](docs/FASE3_ESTADO_DISENO.md) | ✅ |
| 4 | Gráficas Plotly, informes HTML/Excel/Word y borrador de interfaz Streamlit | ✅ |
| 5 | Módulo ML de apoyo (sugerencias, nunca dictamina) | ✅ |

La aplicación Streamlit anterior (`app.py`, `core/`, `tests/*.py` de campo)
permanece operable como referencia mientras la nueva arquitectura alcanza
paridad; su mapa de reutilización está en FASE 1 §3.

## Uso rápido (FASE 2)

```python
from gcv.ingestion.base import read_file
from gcv.normalization.column_mapper import normalize
from gcv.evaluation.registry import get_test

raw = read_file("medicion_poi.csv")        # también .xlsx/.xlsm/.cfg COMTRADE
ds = normalize(raw)                         # columnas canónicas + bitácora
print(ds.log.to_json())                     # toda transformación registrada

prueba = get_test("CE-F-01")                # Rango de frecuencia
resultado = prueba.run(ds)
print(resultado.status, resultado.conclusion)
```

Regla central: sin criterio normativo `VALIDADO` (con documento y numeral en
`normative/matriz_pruebas.yaml`) el motor reporta mediciones pero el resultado
es `NO_EVALUABLE` — nunca inventa límites.

## Interfaz (borrador FASE 4)

```bash
pip install -e .[reporting,ui]
./run_app.sh      # Streamlit: datos → pruebas → resultados → reportes
```

Exportadores disponibles: matriz de cumplimiento Excel, informe técnico HTML
autocontenido (gráficas Plotly interactivas), informe Word y bitácora JSON.
PDF vía weasyprint en entornos con sus librerías de sistema
(`gcv.reporting.html_report.export_pdf`).

## Desarrollo

```bash
pip install -e .[dev]
pytest            # unit tests en tests/unit/
```
