# Versión 2.0 — Sistema de Verificación de Código de Red

Fecha: 2026-07-07 · Rama `claude/grid-compliance-verification-j8j52w` (PR #1) · 146 unit tests en verde.

Esta versión cierra los pendientes que no dependían de datos de campo y consolida
el sistema sobre el paquete `src/gcv`, retirando el monolito legado.

## 1. Novedades de la versión 2

| Novedad | Detalle |
|---|---|
| **Cotejo contra el DOF oficial** | La matriz se verificó contra `Codigo_de_Red_2_0 (1).pdf` (DOF 31-dic-2021). 13/13 criterios muestreados coinciden — ver [COTEJO_DOF.md](COTEJO_DOF.md). Cierra el pendiente urgente n.º 2 de la v1. |
| **Figura 4.1.1.B oficial** | Extraída del DOF (pág. 1066) e insertada en protocolo e informe; selección de curva de huecos consciente de tecnología **y** tipo (B/C vs D). |
| **Interarmónicos (CE-Q-04)** | El evaluador consume `interharmonic_voltage/current_<n>` del analizador y verifica el peor grupo contra el 0.2 %; alias de encabezado incluidos. Sin la señal, es NO EVALUABLE (no bloquea el THD). Cierra el pendiente urgente n.º 5. |
| **PDF directo** | `gcv.reporting.pdf_report.export_pdf` imprime el informe HTML con Chromium headless (o weasyprint). Integrado en la pestaña Reportes; si no hay motor, se informa y se ofrece el HTML. |
| **Cálculo espectral desde forma de onda** | `gcv.quality_power.spectral` obtiene magnitudes armónicas y THD por FFT en ventanas IEC 61000-4-7 desde señal muestreada (COMTRADE), cuando el analizador no entrega el reporte. |
| **Persistencia de proyectos** | `gcv.persistence` guarda y reabre una corrida completa (instalación, resultados, datos y gráficas) en `projects/<central>/`. En la app: botón Guardar en Reportes y selector Reabrir en la barra lateral. |
| **Plan de Trabajo CRE** | Documento inicial adicional para Centros de Carga (formato del Cap. 4.1, Manual CONE) con rangos obligatorios prellenados. Se agrega al paquete documental. |
| **Legado retirado** | `app.py`, `core/`, `components/` y scripts de campo se archivaron en `legacy/`; ya no forman parte del paquete ni de las pruebas. Toda la funcionalidad vive en `src/gcv`. |

## 2. Pendientes que dependen de datos o decisiones del usuario

Estos no se pueden cerrar desde el código; requieren insumos externos:

1. **Validar con datos reales de campo**: todo está probado con datos sintéticos.
   Correr 2–3 reportes históricos y comparar conclusiones contra los informes
   emitidos. Sigue siendo el paso crítico de aceptación.
2. **Tolerancia droop de protocolo (decisión A1)**: el 5 % Pref / 90 % de
   muestras es de protocolo, no del DOF (confirmado en el cotejo). Falta la
   confirmación del criterio que use CENACE en las pruebas reales.
3. **Pruebas por unidad de síncronas (Anexo 5, 1–20)**: el catálogo las marca
   PENDIENTES; se habilitan con el "Reporte de Pruebas por Unidad".

## 3. Mejoras a futuro (no bloquean el uso)

- Runback (P21), rechazo de carga parcial (P23) y amortiguamiento POD (P19):
  pruebas del Anexo 5 sin ficha de criterio cuantitativo; se agregan al definir
  su protocolo.
- Pst propio IEC 61000-4-15 desde forma de onda (hoy el flicker se lee del
  analizador; el espectral de armónicos ya está disponible).
- scikit-learn opcional para sustituir los detectores base del módulo ML.

## 4. Cómo operar la versión 2

```bash
pip install -e .[reporting,ui]
./run_app.sh                  # interfaz: documentos → datos → pruebas → resultados → reportes → histórico
pytest                        # 146 tests en tests/unit
```

Flujo típico en la app:
1. **Documentos** — con la clasificación y la selección de pruebas genera el
   paquete de arranque (Checklist, Revisión Anexo 5, Protocolo, Anexo de
   Revisiones y, para Centros de Carga, Plan de Trabajo CRE).
2. **Datos** — carga Excel/CSV/COMTRADE; normalización con bitácora.
3. **Pruebas** — ejecuta las pruebas aplicables (clasificación automática A–D).
4. **Resultados** — veredicto por prueba con cita normativa y gráficas.
5. **Reportes** — Excel, HTML, Word, PDF y bitácora; Guardar proyecto.
6. **Histórico** — gráficas guardadas por central; Reabrir proyecto (barra lateral).

Parámetros clave por corrida: `tipo_ce` (B/C/D), `area_sincrona`, `estatismo`,
`p_ref_mw`, `v_base_v`, `cin_mw`, `v_kv`+`icc_il` (TDD), `tecnologia`,
`t_falla`/`t_reconexion`/`t_consigna` según la prueba. Cada evaluador documenta
sus parámetros en su docstring (`src/gcv/evaluation/`).
