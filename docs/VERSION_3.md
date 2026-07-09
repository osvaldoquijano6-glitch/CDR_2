# Versión 3.0 — Reestructuración: protocolos fieles y nueva interfaz

Fecha: 2026-07-09 · Rama `claude/grid-compliance-verification-j8j52w` · 151 unit tests en verde.

El sistema se reestructura alrededor del flujo real del proyecto, con la
generación de protocolos como pieza central y **fidelidad absoluta a las
plantillas del usuario**: los documentos de salida SON las plantillas
originales, con los datos del proyecto estampados y las pruebas
seleccionadas insertadas.

## 1. Nueva interfaz — 3 módulos

| Módulo | Contenido |
|---|---|
| **1 · Protocolos** | Datos del proyecto → selección de pruebas (universo Anexo 5, 1–45, editable a pantalla completa) → genera Protocolo por Central, Protocolo por Unidad, Checklist y Anexo de Revisiones. |
| **2 · Gráficas de pruebas** | Carga de mediciones (Excel/CSV/COMTRADE) → ejecución de pruebas → resultados con veredicto y evidencia gráfica → informes (Excel/HTML/Word/PDF) y guardado de proyecto. |
| **3 · Repositorio** | Histórico de gráficas por central · **Manuales HTML de apoyo** (tablas y datos de pruebas, consultables y descargables) · Figuras normativas oficiales · Reabrir proyecto. |

Cambios de fondo de la interfaz:

- **Sin barra lateral**: desaparece el problema del botón de expandir y todo
  el ancho queda para trabajar. La configuración vive dentro de cada módulo.
- **Espacio amplio para pruebas**: la selección es una tabla editable a
  pantalla completa (45 filas con criterio, tipo, aplica, ejecutar y
  comentarios), no un multiselect apretado.

## 2. Generación de protocolos fiel (gcv.protocolos)

Estrategia de **cirugía documental**: el .docx de salida se abre desde la
plantilla del usuario, por lo que portada, control de revisiones,
definiciones, encabezados/pies, estilos (Montserrat/Helvetica Neue, índigo
#312E81) y capítulos finales quedan idénticos. Solo se interviene:

1. Portada y encabezados — proyecto, código, tipo, tecnología, ubicación, fechas.
2. Tabla maestra — columna "APLICA (SI/NO)" según la selección (con notas
   libres, p.ej. "No se cuenta con la infraestructura").
3. Capítulo de pruebas — se reconstruye desde el catálogo YAML insertando
   las secciones seleccionadas con su texto completo (objetivo, condiciones y
   desarrollo, señales, criterio, resultados, marcos de gráfica); las no
   seleccionadas quedan "(no aplica)" con su nota, igual que en la plantilla.
   Tablas de datos y marcos de figura se clonan del XML original.
4. Tabla de aplicabilidad por prueba — marca X bajo el tipo (A–D) del proyecto.

### Catálogo de textos de pruebas (editable)

`tools/extraer_catalogo_protocolos.py` extrae de las plantillas los textos de
**todas** las pruebas a `normative/protocolos/catalogo_{central,unidad}.yaml`
(39 secciones: 21 por unidad con 4 grupos de sistema + 18 por central).
Para editar el texto de una prueba se edita el YAML; para actualizar las
plantillas se reemplaza el .docx y se corre de nuevo el extractor.

### Excel por cirugía

- **Checklist** (`generar_checklist`): abre `Checklist_de_Pruebas_REV_1.1.xlsx`
  y solo escribe APLICA / ¿SE PUEDE EJECUTAR? / comentarios. Formato intacto.
- **Anexo de Revisiones** (`generar_revisiones`): abre
  `Revisiones_Comentarios_SySCE_v1.0.xlsx` y estampa el proyecto en la portada.
- **Revisión Anexo 5** — **eliminado** (repetitivo, decisión del usuario).

## 3. Depuración realizada

- `documentos_iniciales.py` queda solo con el Plan de Trabajo CRE (Centros de
  Carga); el resto lo sustituye `gcv.protocolos`.
- Eliminados `checklist_pruebas_rev3.yaml` y `anexo5_revision_pruebas.yaml`
  (los datos viven ahora en las plantillas del usuario).
- Retirado el código de barra lateral (CSS y logo) de `ui_theme`.
- `st.iframe` en lugar del deprecado `components.html`.

## 4. Pendientes anotados (etapa posterior)

- Rediseño visual completo (el usuario lo pospuso explícitamente; los tokens
  actuales se conservan mientras tanto).
- Textos de catálogo para pruebas que la plantilla trae como "(no aplica)"
  (p.ej. PSS, MEL/OEL): el generador ya los insertará al llenarlos en el YAML.
- Plantilla del usuario para Centro de Carga (hoy sigue el Plan de Trabajo CRE
  genérico).

## 5. Operación

```bash
pip install -e .[reporting,ui]
./run_app.sh      # módulos: Protocolos → Gráficas → Repositorio
pytest            # 151 tests
python tools/extraer_catalogo_protocolos.py   # re-extraer catálogo tras cambiar plantillas
```
