# Diagnosticos Extras: F-test y Bootstrap

Fecha: 2026-01-23

## 1) F-test para pre-trends

**Hipotesis:**
- H0: beta_d_2023 = beta_d_2024 = 0 (no hay tendencia previa)
- H1: Al menos uno es distinto de 0

**Resultado:**
- Wald statistic = 130.6822
- F statistic = 65.3411
- p-value = 0.0
- **Rechazar H0 al 5%? SI**

**Coeficientes:**
- d_2023 = 0.080078 (SE = 0.007053)
- d_2024 = 0.091604 (SE = 0.009986)

**Interpretacion:**
- Se rechaza H0: hay evidencia de tendencia previa (pre-trends no son cero).
- Sin embargo, esto NO invalida el Event Study descriptivo.
- Lo que muestra es que ya habia tendencia positiva 2022-2024, pero el salto
  2025 es de magnitud mucho mayor (0.75 vs 0.08-0.09).

## 2) Bootstrap Oaxaca-Blinder

**Configuracion:** 500 repeticiones bootstrap (resample por entidad)

**Resultados con IC 95%:**

| Componente | Estimacion (pp) | IC 95% | SE |
|------------|-----------------|--------|-----|
| Delta total | 56.96 | [54.71, 59.3] | 1.19 |
| Comportamiento | 44.87 | [43.25, 46.91] | 0.97 |
| Composicion | 12.09 | [10.77, 13.26] | 0.65 |

**Interpretacion:**
- Los intervalos de confianza permiten evaluar la precision de la descomposicion.
- Si el IC de composicion incluye cero, el efecto composicion podria no ser
  estadisticamente significativo.
- El efecto comportamiento es claramente dominante y su IC no incluye cero.
