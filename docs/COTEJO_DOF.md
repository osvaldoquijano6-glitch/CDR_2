# Cotejo de la matriz normativa contra el DOF oficial

Fuente cotejada: `Codigo_de_Red_2_0 (1).pdf` — Código de Red 2.0 (RES/550/2021),
DOF 31 de diciembre de 2021, 257 páginas. Subido al repositorio por el usuario
el 2026-07-07. Método: extracción de texto e imágenes por página (pypdf) y
comparación literal contra `normative/matriz_pruebas.yaml` y
`normative/limites/tablas_cdr2.yaml`.

Este cotejo cierra el pendiente urgente n.º 2 de VERSION_1.md ("cotejo final
contra los PDF oficiales").

## Resultado: 13/13 criterios muestreados COINCIDEN

| # | Criterio | Numeral / Tabla DOF | Pág. DOF | Valor sistema | Resultado |
|---|---|---|---|---|---|
| 1 | Clasificación A–D por área y CIN | Tabla 1.1 | 1053 | `clasificacion_centrales` | Coincide (4 áreas × 4 tipos) |
| 2 | Bandas de frecuencia CE por área | Tabla 2.1 | 1053 | CE-F-01 `bandas_por_area` | Coincide (5 bandas × 2 grupos; 62.4 SIN/SIBC, 63.0 SIBCS/SIM) |
| 3 | ROCOF | 2.2.1 | 1054 | CE-F-02 (2.5 Hz/s, 200 ms) | Coincide |
| 4 | Umbral alta frecuencia | 2.2.3 | 1056 | CE-F-03 (60.2; SIM 60.3; droop 3–8 %; activación <2 s) | Coincide |
| 5 | Umbral baja frecuencia | 2.2.4 | 1057 | CE-F-04 (59.8; SIM 59.7; droop 3–8 %) | Coincide |
| 6 | Rango de regulación P por tecnología | Tabla 2.2.2.B | 1055-1056 | `rango_regulacion_p_pct` (16 tecnologías) | Coincide, incl. notas motor gas/diésel |
| 7 | Reconexión automática | 2.2.8 | 1058 | CE-F-10 (58.8–60.2 Hz, ±5 % V, 5 min, rampa 10 % CIN/min) | Coincide |
| 8 | Rango de tensión CE | Tabla 3.1.1 | 1059 | CE-V-01 (0.90–0.95 y 1.05–1.10 pu 30 min; 0.95–1.05 ilimitado) | Coincide |
| 9 | Huecos de tensión Zona A (4 curvas) | Tablas 4.1.1.A/B, 4.2.1.A/B | 1065-1068 | `huecos_zona_a` + recuperación 0.25–0.5 s (4.1.2) | Coincide (los 34 puntos) |
| 10 | Rango de tensión CC | Tablas 2.1.A/B | 1078-1079 | CC-01 (95–105 % permanente; 90–110 % ≤20 min) | Coincide |
| 11 | Rango de frecuencia CC | Tabla 2.2.A | 1079 | CC-02 (59–61 permanente; 58–62.5 30 min; maniobras ≤0.1 Hz) | Coincide |
| 12 | Factor de potencia CC | 2.4 | 1079 | CC-04 (0.95→0.97 desde 2026-04-08, cinco-minutal, ≥95 % mensual) | Coincide |
| 13 | TDD corriente (3 tablas) | Tablas 2.8.A/B/C + notas | 1081-1082 | `tdd` (pares 25 % de impares, P95 semanal 10 min, hornos de arco +50 %) | Coincide (las 13 filas × 6 columnas) |

## Notas del cotejo

- **Figura 4.1.1.B**: no venía en el paquete FIGURAS.zip; se extrajo la imagen
  oficial de la pág. 1066 del DOF y es la que insertan protocolo e informe.
- **Área Blanca reactivos (Tabla 3.3.2)**: el DOF confirma ±0.33 Q/Pmáx
  obligatorio (±0.5 área gris opcional) en 0.95–1.05 pu, común a síncronas y
  asíncronas, con Pmáx = Capacidad Instalada Neta.
- **Estatismo**: el DOF define un rango continuo seleccionable de 3 % a 8 %
  (no una lista); la matriz usa `estatismos_admisibles: [0.03, 0.05, 0.08]`
  como valores típicos de ajuste y el evaluador acepta cualquier valor
  declarado dentro del rango. Sin cambio requerido.
- La tolerancia droop del 5 % Pref / 90 % de muestras (CE-F-03/04) **no aparece
  en el DOF**: es criterio de protocolo (decisión A1). Sigue pendiente de
  confirmación con CENACE, como documenta la matriz.

## Qué queda fuera de este cotejo

Muestreo dirigido a los criterios que dictaminan las pruebas implementadas.
No se cotejó texto normativo no cuantitativo (procedimientos administrativos,
TIC, protecciones) ni el Manual de Estudios. El riesgo de transcripción de la
matriz queda cerrado para los límites que el motor usa en veredictos.
