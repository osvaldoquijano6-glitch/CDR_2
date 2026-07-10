---
name: generar-protocolos
description: >-
  Genera documentos y protocolos de pruebas del Código de Red (Protocolo por
  Central .docx, Protocolo por Unidad .docx, Checklist .xlsx y Anexo de
  Revisiones .xlsx) por CIRUGÍA sobre las plantillas del usuario, con fidelidad
  absoluta de formato. Úsalo cuando el usuario pida crear/armar/generar un
  protocolo, checklist, anexo de revisiones o documento de pruebas para una
  central o unidad, o cuando pida seleccionar qué pruebas aplican por tipo de
  central (A/B/C/D) y tecnología (síncrona/asíncrona) del universo Anexo 5.
---

# Generación de documentos y protocolos (docx, xlsx)

Produce los cuatro entregables del proyecto **abriendo las plantillas del
usuario y sustituyendo solo información** — nunca se reconstruye el diseño.

## Regla de oro (lineamiento del usuario, innegociable)

> "Solo es quitar o poner información. Idénticos a mis ejemplos."

- El .docx/.xlsx de salida **ES** la plantilla original. Portada, control de
  revisiones, encabezados/pies, estilos (Montserrat/Helvetica Neue, índigo
  `#312E81`), celdas combinadas, anchos, alturas y bordes quedan intactos.
- **Prohibido** cambiar colores, fuentes, layout o reconstruir hojas/tablas.
- Los textos de pruebas viven en catálogos YAML editables
  (`normative/protocolos/catalogo_{central,unidad}.yaml`); se re-extraen de las
  plantillas con `python tools/extraer_catalogo_protocolos.py` tras cambiarlas.

## Plantillas fuente (`normative/plantillas_usuario/`)

| Entregable | Plantilla | Módulo |
|---|---|---|
| Protocolo por Central (.docx) | `Protocolo_Central_v1.2.1.docx` | `gcv.protocolos.builder` |
| Protocolo por Unidad (.docx) | `Protocolo_Unidad_v1.2.1.docx` | `gcv.protocolos.builder` |
| Checklist de Pruebas (.xlsx) | `Checklist_de_Pruebas_REV_1.1.xlsx` | `gcv.protocolos.checklist` |
| Anexo de Revisiones (.xlsx) | `Revisiones_Comentarios_SySCE_v1.0.xlsx` | `gcv.protocolos.revisiones` |

> La antigua "Revisión Anexo 5" fue **eliminada** por repetitiva (decisión del
> usuario). No la regeneres.

## Parámetros requeridos por CENACE

Todo protocolo se parametriza con `ProyectoProtocolo`:

```python
from gcv.protocolos import ProyectoProtocolo, generar_protocolo, generar_checklist, generar_revisiones

proyecto = ProyectoProtocolo(
    nombre_central="Central Eléctrica Solar Norte",  # sustituye a "CATERPILLAR" en portada
    codigo="SNO",                 # clave corta de encabezados (reemplaza "CNK")
    proyecto="GCE311_SNO_Solar",  # línea "Proyecto:" de portada
    tipo="B",                     # Tipo de central A/B/C/D → marca X de aplicabilidad
    tecnologia="SINCRONA",        # SINCRONA | ASINCRONA → "CENTRALES ELÉCTRICAS SÍNCRONAS/ASÍNCRONAS"
    ubicacion="Piedras Negras, Coahuila, México",
    fecha_pruebas="2026-08-15",
    fecha_envio="2026-08-30",
    pruebas_aplican={1, 2, 3, 17, 21, 22, 26},  # universo Anexo 5 1–45
    notas={27: "No se cuenta con la infraestructura"},  # nota libre por prueba no aplicable
)
```

### Universo de pruebas (Anexo 5, 1–45)

- **1–20**: pruebas **por unidad** (`generar_protocolo("unidad", ...)`, offset 0).
- **21–45**: pruebas **por central** (`generar_protocolo("central", ...)`,
  offset 20 → "Prueba 1" del protocolo = prueba 21 del universo).
- Lee el universo real (número, nombre, criterio, tipo EN SITIO/DOCUMENTAL/NA)
  desde la plantilla con `universo_pruebas()` — no lo inventes.
- Cada tipo de central (A/B/C/D) y tecnología define qué pruebas aplican;
  respeta la tabla de aplicabilidad de la plantilla. Ante duda sobre si una
  prueba aplica a un tipo, consulta `normative/matriz_pruebas.yaml`
  (`categorias`, `tecnologia`) — no supongas.

## Qué se interviene (y solo eso)

1. **Portada y encabezados/pies** — proyecto, código, tipo, tecnología,
   ubicación, fechas (`_portada`, `_encabezados_pies`).
2. **Tabla maestra** — columna "APLICA (SI/NO)": **únicamente** `SI`, `NO`,
   `APLICA` o `NO APLICA` (`_tabla_maestra`). **REGLA DURA**: las notas libres
   (p.ej. "No se cuenta con la infraestructura") corresponden a datos de
   visita en sitio, solicitud de CENACE o dictamen de un profesional — el
   asistente NUNCA las redacta ni excluye pruebas por iniciativa propia;
   solo las estampa si el usuario las entrega textualmente en
   `proyecto.notas`. El asistente se limita a los lineamientos del Código
   de Red.
3. **Capítulo de pruebas** — se reconstruye desde el YAML: las seleccionadas con
   su texto completo (objetivo, condiciones, señales, criterio, marcos de
   gráfica); las no seleccionadas quedan `(no aplica)` con su nota. Tablas de
   datos y marcos de figura se **clonan del XML original**.
4. **Tabla de aplicabilidad por prueba** — marca `X` bajo el tipo del proyecto.

## Excel por cirugía

- **Checklist** (`generar_checklist`): solo escribe columnas H–K
  (APLICA / ¿SE PUEDE EJECUTAR? / COMENTARIOS REV₁ / REV₂). Firma:
  `generar_checklist(destino, aplica={21:"SI"}, ejecutar={21:"SI"}, comentarios_rev1={...}, comentarios_rev2={...})`.
  Las pruebas no incluidas conservan el valor de la plantilla.
- **Anexo de Revisiones** (`generar_revisiones(destino, proyecto=..., documento_base=...)`):
  solo estampa la portada.

## Flujo recomendado

```python
generar_protocolo("central", proyecto, "salida/")   # → salida/Protocolo_Central_SNO.docx
generar_protocolo("unidad",  proyecto, "salida/")
generar_checklist("salida/Checklist.xlsx",
                  aplica={n: "SI" for n in proyecto.pruebas_aplican})
generar_revisiones("salida/Anexo_Revisiones.xlsx", proyecto=proyecto.proyecto)
```

## Verificación antes de entregar

1. Abre un documento generado y confirma que portada/encabezados llevan los
   datos del proyecto y el resto del formato es idéntico a la plantilla.
2. Confirma que la tabla maestra refleja exactamente `pruebas_aplican` y las
   notas.
3. Corre `pytest tests/unit/test_protocolos.py` — deben pasar los 7 casos.
4. Si editaste una plantilla, re-extrae el catálogo antes de generar.
