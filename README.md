# CDR_2 — Verificación de Pruebas de Código de Red

Sistema en Python para verificar pruebas aplicables a Centrales Eléctricas y
Centros de Carga conforme al Código de Red, Manual INTER, Manual CONE y
POC/Anexo 5. Procesa Excel/CSV/COMTRADE, normaliza y depura datos con bitácora
trazable, evalúa criterios de aceptación de forma determinística y genera
evidencia e informes.

**Versión 2.0** — ver [docs/VERSION_2.md](docs/VERSION_2.md) (nuevas capacidades y
pendientes). Historial: [docs/VERSION_1.md](docs/VERSION_1.md).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura + matriz normativa ([docs/FASE1_ARQUITECTURA.md](docs/FASE1_ARQUITECTURA.md)) | ✅ |
| 2 | Paquete `src/gcv`: lectores, normalización, motor de reglas, unit tests | ✅ |
| 3 | Pruebas prioritarias: 13 evaluadores (frecuencia, ROCOF, droop, tensión, FP, capacidad, armónicos, flicker, desbalance, RVC) — ver [docs/FASE3_ESTADO_DISENO.md](docs/FASE3_ESTADO_DISENO.md) | ✅ |
| 4 | Gráficas Plotly, informes HTML/Excel/Word/PDF y interfaz Streamlit | ✅ |
| 5 | Módulo ML de apoyo (sugerencias, nunca dictamina) | ✅ |

Toda la funcionalidad vive en el paquete `src/gcv`. La aplicación Streamlit
anterior (`app.py`, `core/`, `components/` y sus scripts de campo) quedó
archivada en [`legacy/`](legacy/) y ya no forma parte del paquete ni de la
batería de pruebas; su mapa de reutilización está en FASE 1 §3.

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

## Interfaz

```bash
pip install -e .[reporting,ui]
./run_app.sh      # Streamlit: documentos → datos → pruebas → resultados → reportes → histórico
```

Exportadores disponibles: paquete documental de arranque (Checklist, Revisión
Anexo 5, Protocolo, Anexo de Revisiones y Plan de Trabajo CRE para Centros de
Carga), matriz de cumplimiento Excel, informe técnico HTML autocontenido
(gráficas Plotly interactivas), informe Word, **PDF directo** (Chromium headless
o weasyprint; `gcv.reporting.pdf_report.export_pdf`) y bitácora JSON. Las
corridas se guardan y reabren desde la barra lateral (`gcv.persistence`).

## Desarrollo

```bash
pip install -e .[dev]
pytest            # unit tests en tests/unit/
```
