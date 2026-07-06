# Versión 1.0 — Entrega del Sistema de Verificación de Código de Red

Fecha: 2026-07-05 · Rama `claude/grid-compliance-verification-j8j52w` (PR #1) · 117 unit tests en verde.

## 1. Qué entrega la versión 1

| Capacidad | Detalle |
|---|---|
| **Ingesta** | Excel (.xlsx/.xlsm), CSV de analizadores (preambulos, separadores, encodings) y COMTRADE (.cfg/.dat), con SHA-256 por fuente |
| **Normalización** | Alias de señales, homologación de unidades, timestamps con desambiguación día/mes, fs/huecos/duplicados, bitácora obligatoria de toda transformación, correcciones manuales YAML |
| **Matriz normativa** | 35 pruebas; **35 VALIDADAS** con numeral del CdR 2.0 (RES/550/2021) desde los catálogos del proyecto |
| **Motor determinístico** | 35 evaluadores (cobertura total de la matriz) dictaminando CUMPLE/NO_CUMPLE/NO_EVALUABLE con cita normativa, límites por tipo (B vs C/D), por área síncrona y por vigencia de fecha; clasificador A–D automático (Tabla 1.1) |
| **Pruebas cubiertas** | Frecuencia (rango, ROCOF 2.5/200ms, alta/baja, CPF, reconexión, limitación total/parcial), tensión (rango, huecos Zona A, modos de control V/Q/FP), capacidad (P25 240h/25h/no-inyección), calidad (desbalance, flicker, RVC/día, armónicos V con tablas completas, TDD por Icc/IL), CC (FP con vigencia 0.95→0.97) |
| **Evidencia y reportes** | Gráficas Plotly (doble eje según convención del proyecto + apilado), informe técnico HTML autocontenido, Word, matriz Excel con semáforo, bitácora JSON; objetivos/conclusiones de plantilla del catálogo (solo en CUMPLE) |
| **Interfaz** | Streamlit (`./run_app.sh`): proyecto → datos → pruebas aplicables → resultados → exportación |
| **ML de apoyo** | Sugerencia de mapeo difuso (confirmación obligatoria), anomalías (outliers/tramos planos/pérdida de señal), clasificación de eventos, aviso de pruebas incompletas — **nunca dictamina** |

Garantía central verificada por tests: sin criterio `VALIDADO` con numeral, el motor
calcula y reporta pero el resultado es NO_EVALUABLE. Trazabilidad completa:
informe → criterio → numeral → mapeo de columnas → SHA-256 del archivo fuente.

## 2. Pendientes URGENTES (antes de usar en un dictamen real)

1. **Validar con datos reales de campo**: todo está probado con datos sintéticos.
   Correr 2–3 reportes históricos del proyecto legado y comparar conclusiones
   contra los reportes emitidos. *Es el paso crítico de aceptación.*
2. **Cotejo final contra los PDF oficiales**: la matriz se validó con los
   catálogos internos (transcripciones del Manual INTE/CONE). Un cotejo
   muestral contra el DOF cierra el riesgo de transcripción.
3. **Tolerancia droop de protocolo (decisión A1)**: el 5 % Pref / 90 % de
   muestras es de protocolo, no normativo. Confirmar con el criterio que use
   CENACE en las pruebas reales (es una llave de la matriz, sin código).
4. **Pruebas por unidad de síncronas (Anexo 5, 1–20)**: el catálogo las marca
   PENDIENTES; se requiere el "Reporte de Pruebas por Unidad" para habilitarlas.
5. **Interarmónicos (≤0.2 %)**: el evaluador CE-Q-04 aún no consume señal de
   interarmónicos del analizador (llave ya definida en la matriz).

## 3. Mejoras a FUTURO (no bloquean el uso)

- Runback (P21), rechazo de carga parcial (P23) y amortiguamiento POD (P19):
  pruebas del Anexo 5 sin ficha de criterio cuantitativo en los catálogos;
  se agregan al definir su protocolo.
- **Plan de Trabajo CRE** como formato de salida (esquema ya capturado en el
  catálogo 03, §9).
- **PDF directo** (weasyprint requiere librerías del sistema; hoy la vía es HTML).
- **Persistencia de proyectos** en la app (guardar/cargar corridas y parámetros;
  hoy la sesión vive en memoria).
- **Cálculo espectral desde COMTRADE** (armónicos desde forma de onda) y Pst
  propio IEC 61000-4-15 cuando haya fs suficiente.
- **scikit-learn opcional** para sustituir los detectores base del módulo ML.
- **Paridad total y retiro del legado** (`app.py` monolito) cuando la app nueva
  cubra el flujo diario completo; luego mover legado a `legacy/`.
- **CI en GitHub** (pytest en cada push al PR).

## 4. Cómo operar la versión 1

```bash
pip install -e .[reporting,ui]
./run_app.sh                  # interfaz
pytest                        # 117 tests
```

Parámetros clave por corrida: `tipo_ce` (B/C/D), `area_sincrona`, `estatismo`,
`p_ref_mw`, `v_base_v`, `cin_mw`, `v_kv`+`icc_il` (TDD), `tecnologia`,
`t_falla`/`t_reconexion`/`t_consigna` según la prueba. Cada evaluador documenta
sus parámetros y estructura de límites en su docstring
(`src/gcv/evaluation/`).
