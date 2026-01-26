# Fuentes de Datos

Este documento describe las fuentes de datos utilizadas en el análisis.

## Fuentes Principales

### 1. SIGA-MEF (Cuadro Multianual de Necesidades)

- **Descripción**: Registros de transmisión del CMN por Unidad Ejecutora
- **Período**: 2022-2025
- **Fuente**: Dirección General de Abastecimiento - MEF
- **Acceso**: Datos administrativos (no públicos)

### 2. Consulta Amigable MEF

- **Descripción**: Datos presupuestales (PIA, PIM, Devengado) por Unidad Ejecutora
- **Período**: 2022-2025
- **URL**: https://apps5.mineco.gob.pe/transparencia/
- **Acceso**: Público (scraping con Selenium)

### 3. Padrón SIGA

- **Descripción**: Listado de Unidades Ejecutoras habilitadas en SIGA
- **Fuente**: Dirección de Programación y Seguimiento de Inversiones Públicas (DPIP)
- **Acceso**: Datos administrativos

### 4. SIGA-MINEDU

- **Descripción**: Registros SIGA del sector Educación
- **Fuente**: Ministerio de Educación
- **Acceso**: Datos administrativos

---

## Estructura de Datos

### Esquema `raw`
Datos crudos tal como se extraen de las fuentes.

### Esquema `dwh`
Datos transformados y normalizados (dimensiones y hechos).

### Esquema `mart`
Tablas agregadas listas para análisis.

---

## Notas de Privacidad

Los datos utilizados son agregados a nivel de Unidad Ejecutora (institución pública) y no contienen información personal identificable.

Los scripts de este repositorio están diseñados para trabajar con datos públicos (Consulta Amigable) o replicar la estructura de datos administrativos sin incluir los datos originales.

---

## Reproducibilidad

Para replicar el análisis con datos públicos:

1. Ejecutar el scraping de Consulta Amigable (ver `scraping/`)
2. Cargar datos a PostgreSQL (ver `etl/`)
3. Ejecutar scripts de análisis (ver `analisis/`)

Los datos administrativos (SIGA-MEF, padrón) requieren autorización institucional.
