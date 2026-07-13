# CDR_2 — Protocolos y Verificación de Pruebas de Código de Red

Sistema en Python para generar protocolos de pruebas y verificar su
cumplimiento en Centrales Eléctricas y Centros de Carga conforme al Código de
Red 2.0, Manual INTE, Manual CONE y POC/Anexo 5. Genera los documentos del
proyecto **en el formato exacto de las plantillas del usuario**, procesa
Excel/CSV/COMTRADE con bitácora trazable, evalúa criterios de aceptación de
forma determinística y produce evidencia e informes.

**Versión 3.0** — ver [docs/VERSION_3.md](docs/VERSION_3.md) (reestructuración:
generación de protocolos fiel a plantillas + interfaz en 3 módulos).
Historial: [docs/VERSION_2.md](docs/VERSION_2.md) · [docs/VERSION_1.md](docs/VERSION_1.md).

## Interfaz — 3 módulos

```bash
pip install -e .[reporting,ui]
./run_app.sh
```

1. **Protocolos** — datos del proyecto + selección del universo de pruebas
   (Anexo 5, 1–45) → Protocolo por Central (.docx), Protocolo por Unidad
   (.docx), Checklist (.xlsx) y Anexo de Revisiones (.xlsx), todos por cirugía
   sobre las plantillas de `normative/plantillas_usuario/` (formato idéntico:
   solo se quita o pone información).
2. **Gráficas de pruebas** — carga de mediciones, ejecución de pruebas,
   veredicto con cita normativa, evidencia gráfica e informes
   (Excel/HTML/Word/PDF + bitácora JSON).
3. **Repositorio** — histórico de gráficas por central, manuales HTML de
   apoyo (tablas y datos de pruebas), figuras normativas oficiales y
   reapertura de proyectos guardados (`gcv.persistence`).

## Generación de protocolos (`gcv.protocolos`)

```python
from gcv.protocolos import ProyectoProtocolo, generar_protocolo, generar_checklist

proyecto = ProyectoProtocolo(
    nombre_central="Central Eléctrica Demo", codigo="DMO", tipo="B",
    tecnologia="SINCRONA", pruebas_aplican={1, 2, 3, 17, 21, 22, 26})
generar_protocolo("central", proyecto, "salida/")   # fiel a la plantilla
generar_protocolo("unidad", proyecto, "salida/")
generar_checklist("salida/checklist.xlsx", aplica={21: "SI", 28: "No Aplica"})
```

Los textos de todas las pruebas viven en
`normative/protocolos/catalogo_{central,unidad}.yaml` (editables); se
re-extraen de las plantillas con `python tools/extraer_catalogo_protocolos.py`.

## Motor de verificación (uso directo)

```python
from gcv.ingestion.base import read_file
from gcv.normalization.column_mapper import normalize
from gcv.evaluation.registry import get_test

raw = read_file("medicion_poi.csv")        # también .xlsx/.xlsm/.cfg COMTRADE
ds = normalize(raw)                         # columnas canónicas + bitácora
prueba = get_test("CE-F-01")                # Rango de frecuencia
resultado = prueba.run(ds)
print(resultado.status, resultado.conclusion)
```

Regla central: sin criterio normativo `VALIDADO` (con documento y numeral en
`normative/matriz_pruebas.yaml`) el motor reporta mediciones pero el resultado
es `NO_EVALUABLE` — nunca inventa límites.

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura + matriz normativa ([docs/FASE1_ARQUITECTURA.md](docs/FASE1_ARQUITECTURA.md)) | ✅ |
| 2 | Paquete `src/gcv`: lectores, normalización, motor de reglas, unit tests | ✅ |
| 3 | Pruebas prioritarias: 13 evaluadores — ver [docs/FASE3_ESTADO_DISENO.md](docs/FASE3_ESTADO_DISENO.md) | ✅ |
| 4 | Gráficas Plotly, informes HTML/Excel/Word/PDF e interfaz Streamlit | ✅ |
| 5 | Módulo ML de apoyo (sugerencias, nunca dictamina) | ✅ |
| 6 | Reestructuración v3: `gcv.protocolos` fiel a plantillas + interfaz en 3 módulos | ✅ |

El código legado de la primera app quedó archivado en [`legacy/`](legacy/).

## Desarrollo

```bash
pip install -e .[dev]
pytest            # unit tests en tests/unit/
```
