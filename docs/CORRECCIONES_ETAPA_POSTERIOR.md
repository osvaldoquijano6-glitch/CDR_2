# Correcciones Requeridas — CDR_2 v3.0 (Etapa Posterior)

Documento generado: 2026-07-08  
Estado: **DOCUMENTADO — Pendiente de resolver en próxima etapa**

---

## Resumen

El usuario ha identificado correcciones necesarias que requieren atención en una etapa posterior. Esta etapa se enfoca en:
1. Formatos de exportación (Excel, Word) — deben ser idénticos a ejemplos proporcionados
2. Interfaz (barra lateral, espacio de pruebas) — usabilidad
3. Nueva etapa "Definir Pruebas" con formato específico del usuario
4. Depuración general de código
5. HTMLs de apoyo con referencias normativas

---

## 1. CORRECCIONES DE INTERFAZ

### Barra Lateral
- **Problema**: Al ocultarla, no hay botón visible para expandirla
- **Solución**: Agregar ícono/botón flotante o persistente para expand/collapse

### Espacio de Pruebas
- **Problema**: Layout muy comprimido, insuficiente para visualizar resultados
- **Solución**: Aumentar altura de contenedores, mejorar espaciado vertical

---

## 2. FORMATOS DE EXPORTACIÓN (CRÍTICO)

**Principio**: Replicar **exactamente** los ejemplos proporcionados por usuario  
**Regla**: Solo agregar/quitar información, NO cambiar formatos, colores o diseño

### Excel
- [ ] Checklist — Respetar formato exacto
- [ ] Revisiones — Respetar formato exacto
- [ ] ~~Revisión Anexo 5~~ — **ELIMINAR** (repetitivo)
- [ ] Matriz de cumplimiento — Respetar formato exacto

### Word
- [ ] Protocolo — Mantener estructura y estilos originales
- [ ] Plan de Trabajo CRE — Mantener estructura y estilos originales

### HTML
- [ ] Informe técnico — Incluir referencias y tablas desde .md de apoyo
- [ ] Incluir gráficas normativas (Figura 4.1.1.B, etc.)

---

## 3. NUEVA ETAPA: "DEFINIR PRUEBAS"

**Ubicación en flujo**: Entre "Documentos" y "Datos"

**Contenido**:
- Permitir descripción detallada de cada prueba a ejecutar
- Usar formato de descripción proporcionado por usuario
- Incluir referencias normativas y criterios de aceptación
- Mostrar tablas y datos de pruebas desde archivos de apoyo

**Archivos relevantes**:
- `normative/matriz_pruebas.yaml` — Criterios
- `docs/` — Documentación de apoyo

---

## 4. DOCUMENTACIÓN HTML DE APOYO

**Archivos faltantes**:
- HTMLs que embeben archivos .md de apoyo
- Tablas de datos de pruebas
- Referencias normativas
- Gráficas de referencia

**Acción**:
- Revisar archivos de apoyo proporcionados al usuario
- Generar HTMLs que integren estos datos
- Hacer accesibles desde la interfaz (nueva etapa "Definir Pruebas")

---

## 5. DEPURACIÓN DE CÓDIGO

- [ ] Revisar y eliminar errores lógicos
- [ ] Revisar y corregir manejo de excepciones
- [ ] Verificar flujos incompletos o rotos
- [ ] Validar integración de módulos

**Módulos críticos**:
- `src/gcv/reporting/excel.py`
- `src/gcv/reporting/docx_report.py`
- `src/gcv/reporting/html_report.py`
- `src/gcv/app/streamlit_app.py`

---

## 6. NOTA ARQUITECTÓNICA

> "Ya deja de lado el diseño y app original, esto evolucionó y debe reestructurarse todo."

**Decisión de usuario**: 
- ❌ No modificar diseño UI en esta etapa
- ❌ No tocar arquitectura de app original (legacy/)
- ✅ Solo resolver correcciones técnicas de fondo
- 🔄 Reestructuración completa para etapa posterior

---

## 7. PRÓXIMAS ACCIONES

1. **Usuario**: Proporcionar ejemplos exactos de formatos Excel y Word
2. **Usuario**: Proporcionar archivos .md de apoyo y referencias
3. **Usuario**: Confirmar orden de ejecución de correcciones
4. **Equipo dev**: Implementar en etapa posterior, respetando exactamente formatos dados

---

**Versión actual**: 2.0 (Funcionalidad completa)  
**Versión siguiente**: 3.0 (Formatos + Depuración + Reestructuración)
