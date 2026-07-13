# Investigación de parámetros normativos — Código de Red (México)

Investigación para poblar los criterios de aceptación de la matriz de pruebas.
Recopilada por búsqueda en la red (julio 2026). **Los PDF oficiales del gobierno
(DOF/CENACE/CFE) bloquean el acceso automatizado**, por lo que los valores de
abajo provienen de **fuentes técnicas secundarias que citan el Código de Red**.

## Regla de uso (obligatoria)

Cada valor lleva una etiqueta de confianza:

- **[S] Secundaria** — valor citado por una consultora/artículo que referencia
  el Código de Red. Debe **confirmarse contra el PDF oficial** antes de pasar la
  prueba a `estado_normativo: VALIDADO` en `matriz_pruebas.yaml`.
- **[G] Pendiente (gap)** — no se obtuvo por búsqueda; requiere el PDF oficial.

Mientras un parámetro esté en [S] o [G], el motor sigue devolviendo
`NO_EVALUABLE`. Los valores propuestos ya están volcados en
`normative/parametros_propuestos.yaml` con `estado: PROPUESTO_POR_CONFIRMAR`
para que, una vez confirmados, se copien a la matriz.

## Fuentes primarias a confirmar (abrir manualmente)

| # | Documento | Dónde |
|---|---|---|
| P1 | Código de Red — DACG (DOF 08-04-2016, RES-151-2016) | cenace.gob.mx › Marco Regulatorio |
| P2 | Manual de Interconexión de Centrales y Conexión de Centros de Carga (DOF 09-02-2018) | interconexion.cfe.mx/marcoregulatorio/Manuales |
| P3 | Actualización Código de Red (DOF 31-12-2021) | dof.gob.mx/2021/CRE/CRE_311221.pdf |
| P4 | Guía de requerimientos del Código de Red para Centros de Carga (V2) | gob.mx (SENER/CRE) |
| P5 | Requerimientos del Código de Red para Centros de Carga | amuvie.mx (biblioteca) |
| P6 | CFE L0000-45 "Desviaciones permisibles en forma de onda" | lapem.cfe.gob.mx/normas |

> Si compartes estos PDF (o los subes a una carpeta del repo), confirmo cada
> tabla y actualizo la matriz a VALIDADO en una pasada.

---

## 1. Frecuencia

### 1.1 Centros de Carga  [S]

| Condición | Rango | Tiempo |
|---|---|---|
| Estado permanente | 59.0 – 61.0 Hz | continuo |
| Transitorio | 58.0 – 62.5 Hz | 30 min |

Tolerancia declarada: ±0.1 Hz permanente; hasta ±2 Hz por 30 min.
Fuente: radthink.com.mx (Voltaje y Frecuencia). **Confirmar en P2/P4.**

### 1.2 Centrales Eléctricas  [G parcial]

El Manual INTER (P2) contiene la tabla de rangos de frecuencia con tiempos
mínimos de operación sin desconexión para centrales (típicamente escalones en
57.5 / 58.5 / 59.3 / 60.5 / 61.5 / 62.5 Hz). **Los tiempos exactos por banda no
se obtuvieron por búsqueda** — requieren el PDF (P2, capítulo de variaciones de
frecuencia). Mapea a `CE-F-01` (`limites.bandas`).

### 1.3 ROCOF  [G]

No hay valor público confiable del ROCOF de inmunidad ni de la ventana de
cálculo. Requiere P2. Mapea a `CE-F-02` (`rocof_inmunidad_hz_s`, `ventana_rocof_ms`).

---

## 2. Tensión

### 2.1 Centrales — rango en el Punto de Interconexión  [S]

| Rango (pu) | Tiempo de operación |
|---|---|
| 0.90 ≤ V < 0.95 | 30 min |
| 0.95 ≤ V ≤ 1.05 | continuo (ilimitado) |
| 1.05 < V ≤ 1.10 | 30 min |

Fuente: resúmenes del Manual INTER (búsqueda). Base pu = tensión nominal del POI.
Mapea a `CE-V-01` (`limites.bandas` con `v_min_pu`, `v_max_pu`, `t_min_s`).
**Confirmar bandas fuera de 0.90–1.10 y tiempos en P2.**

### 2.2 Centros de Carga  [G]

Rango de tensión por nivel (MT/AT) no obtenido con precisión; requiere P4/P5.
Mapea a `CC-01`.

---

## 3. Factor de potencia  [S]

- Mínimo exigido: **FP ≥ 0.95**.
- Media Tensión (13.8/23/34.5 kV): en promedio.
- Alta Tensión: intervalos de **5 min**, cumpliendo **≥ 95 % del tiempo** en un
  periodo mensual.

Fuente: Risoul / resúmenes CFE (búsqueda). Mapea a `CC-04`
(`fp_min: 0.95`, `cumplimiento_minimo_pct: 95`) y al control de FP de centrales.
**Confirmar en P4/P5.**

---

## 4. Calidad de la potencia

### 4.1 Armónicos de tensión (THD)  [S / G]

- Nivel **1–69 kV: THD de tensión máx. 3.0 %**.  [S]
- Tablas del Código de Red: **3.8.A (≤69 kV), 3.8.B, 3.8.C** (niveles > 69 kV).
- Límites de **armónicos individuales** y niveles > 69 kV: **[G]** — requieren P1/P4.

Fuente: kin.energy / radthink (búsqueda). Mapea a `CE-Q-04`
(`thd_max_pct`, `armonicos: {orden: límite}`, `percentil`).

### 4.2 Armónicos de corriente (TDD)  [G]

Las tablas 3.8 fijan la distorsión de corriente por nivel de tensión y por
relación Isc/IL. **Valores no obtenidos** — requieren P1/P4. Mapea a `CE-Q-05`.

### 4.3 Flicker  [S]

- **Pst ≤ 1.0** (ventana 10 min).
- **Plt ≤ 0.65** (2 h, a partir de 12 valores de Pst).

Fuente: radthink / CFE L0000-45 (P6). Mapea a `CE-Q-02`
(`pst_max: 1.0`, `plt_max: 0.65`). **Confirmar percentil/tiempo de campaña.**

### 4.4 Desbalance  [S]

- **Desbalance de tensión ≤ 2 %** — valor de secuencia negativa, agregación 10 min.
- **Desbalance de corriente ≤ 15 %** (puntos de conexión en MT/AT).

Fuente: kin.energy / radthink (búsqueda). Mapea a `CE-Q-01`
(`metodo: iec`, `limite_pct: 2.0`, `percentil`). **Confirmar en P1/P4.**

### 4.5 Variaciones rápidas de tensión (RVC)  [G]

Límite (%) y ocurrencia permitida no obtenidos; requieren P1. Mapea a `CE-Q-03`.

---

## 5. Clasificación de Centrales Tipo A/B/C/D  [G]

La búsqueda **no devolvió** las bandas de capacidad instalada (MW) por Tipo y
por área síncrona (SIN, BCA, BCS, Mulegé). Nota confirmada: en **BCS** hay
disposiciones específicas (tope ~10 MW agregados para centrales < 0.5 MW).
Las bandas A/B/C/D exactas están en el **Manual INTER (P2)** y son
**imprescindibles** para decidir qué pruebas aplican a cada central
(`evaluation/applicability.py`). **Prioridad de confirmación alta.**

> Nota: "A/B/C/D" del Código de Red = clasificación de **centrales por tamaño**.
> No confundir con los criterios operativos N/N-1/N-2 (contingencias), que
> algunos resúmenes mezclan.

---

## 6. Cobertura de esta investigación

| Prueba | Parámetro | Estado |
|---|---|---|
| CE-V-01 | Bandas de tensión (pu) + tiempos | [S] propuesto |
| CC-04 | FP ≥ 0.95, 95 % del tiempo, 5 min | [S] propuesto |
| CE-Q-02 | Pst ≤ 1.0, Plt ≤ 0.65 | [S] propuesto |
| CE-Q-01 | Desbalance ≤ 2 % | [S] propuesto |
| CE-Q-04 | THD tensión ≤ 3.0 % (≤69 kV) | [S] parcial |
| CC-01 | Rango tensión CC | [G] |
| CC-02 | Frecuencia CC (59–61 / 58–62.5) | [S] propuesto |
| CE-F-01 | Bandas de frecuencia centrales + tiempos | [G] |
| CE-F-02 | ROCOF | [G] |
| CE-Q-05 | TDD corriente | [G] |
| CE-Q-03 | RVC | [G] |
| Tipo A/B/C/D | Bandas de capacidad por área | [G] — prioridad alta |

**Siguiente paso más eficiente:** compartir P2 (Manual INTER) y P4 (Guía Centros
de Carga). Con esos dos cierro casi todos los [G] y confirmo los [S].
