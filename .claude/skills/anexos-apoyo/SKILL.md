---
name: anexos-apoyo
description: >-
  Gestiona y produce los anexos de apoyo del proyecto: manuales HTML consultables
  (tablas y datos de pruebas, referencias normativas), figuras normativas
  oficiales del Manual INTE / Código de Red, y el histórico de gráficas por
  central del repositorio. Úsalo cuando el usuario pida material de apoyo, anexos,
  manuales HTML, tablas de referencia, figuras normativas (huecos de tensión,
  perfiles V-Q, CPF) o consultar/organizar el repositorio de evidencias.
---

# Anexos de apoyo

Reúne el material de referencia y evidencia que respalda los protocolos y
gráficas. Todo anexo cita su **fuente documental** (documento + numeral +
versión) — la regla del proyecto: **nada se inventa**.

## 1. Manuales HTML de apoyo (`normative/fuentes/manuales/`)

Documentos consultables y descargables con tablas y datos de prueba. Se muestran
en el Módulo 3 (Repositorio) de la app vía `st.iframe(ruta, height=760)`.

| Archivo | Contenido |
|---|---|
| `01_manual_puesta_en_servicio.html` | Puesta en servicio de centrales — pruebas por unidad y central |
| `02_manual_operacion_desempeno.html` | Operación y desempeño (CPF, droop, huecos, calidad) |
| `03_manual_centro_de_carga.html` | Requisitos de conexión de centros de carga (CONE) |

Al crear o actualizar un manual: HTML autocontenible (CSS embebido, sin CDNs),
tablas con la fuente normativa al pie, y **fidelidad** a los datos del Manual
INTE / CONE / Anexo 5. No cambies cifras sin cita.

## 2. Figuras normativas oficiales (`gcv.reporting.figuras_normativas`)

Figuras del Manual INTE (CdR 2.0) en `normative/figuras/`, mapeadas por prueba y
tecnología. Se insertan en el Protocolo (.docx) y en el informe HTML como
referencia de la sección.

```python
from gcv.reporting.figuras_normativas import figuras_para, figura_b64
figs = figuras_para("CE-V-07", tecnologia="SINCRONA", tipo_ce="D")
# → [(título, ruta_png)]; la curva de huecos depende del tipo (B/C vs D)
```

Catálogo disponible (`TITULOS`/`MAPA`): CPF (2.2.2.A/B), perfiles V-Q/P-Q
síncronas y asíncronas (3.3.2, 3.3.3, 3.5.1, 3.5.2), zonas ante huecos de
tensión (4.1.1.A/B, 4.2.1, 4.2.1.B). Parámetros CENACE que rigen la selección:

- **tecnología** (SINCRONA/ASINCRONA) → perfiles y curvas de hueco distintos.
- **tipo de central** (B/C usan Tabla 4.1.1; D usa Tabla 4.2.1).
- Sin tipo conocido, `figuras_para` incluye ambas variantes.

## 3. Repositorio histórico de gráficas (`gcv.reporting.repositorio`)

Evidencia gráfica persistida por central en `projects/<central>/graficas/`.

```python
from gcv.reporting.repositorio import listar_centrales, listar_graficas, cargar_figura
listar_centrales()                 # centrales con histórico
listar_graficas("Central Solar Norte")   # entradas: prueba, resultado, fecha, ruta
cargar_figura(entrada["ruta_json"])      # re-abrir una figura Plotly
```

Cada entrada del `indice.json` trae prueba, resultado, fecha y archivos; los
nombres son trazables (`<CENTRAL>_<PRUEBA>_<AAAAmmdd_HHMMSS>_<n>`).

## Lineamientos CENACE para anexos

- **Trazabilidad total**: cada tabla/figura/dato referencia su origen normativo
  (Manual INTE, CONE, POC/Anexo 5, Código de Red 2.0 — DOF 31-dic-2021).
- **Sin criterio VALIDADO no hay límite**: un anexo puede reportar mediciones,
  pero no afirma cumplimiento sin cita. Consulta `normative/matriz_pruebas.yaml`
  (`estado_normativo`, `fuente_documental`) antes de asentar un umbral.
- **Formato de fuente**: documento + numeral + versión/fecha DOF.
- Los anexos acompañan (no sustituyen) al Protocolo y al Checklist generados por
  la skill `generar-protocolos`.

## Verificación

1. Los manuales HTML abren de forma autocontenible (sin recursos externos).
2. Las figuras normativas seleccionadas corresponden a la tecnología y tipo de
   la central.
3. Toda cifra de referencia tiene su fuente documental citada.
