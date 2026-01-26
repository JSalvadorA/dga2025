# DiD Clasico 2x2: SWITCHER vs ALWAYS_IN

## 1. Especificacion

```
cumple_v4_it = alpha + beta1*SWITCHER + beta2*POST + delta*(SWITCHER x POST) + X'gamma + epsilon
```

Donde:
- SWITCHER = 1 si entidad paso de SIGA=NO a SIGA=SI en 2025
- POST = 1 si anio = 2025
- delta = efecto DiD (parametro de interes)

## 2. Calculo manual DiD 2x2

| Grupo | Pre (2022-2024) | Post (2025) | Diferencia |
|-------|-----------------|-------------|------------|
| ALWAYS_IN (n=1284) | 0.1942 | 0.8886 | 0.6944 |
| SWITCHER (n=607) | 0.0022 | 0.6046 | 0.6024 |
| **DiD** | | | **-0.0920** |

**Interpretacion:** SWITCHER salto -9.20 pp MENOS que ALWAYS_IN.

## 3. Estimacion OLS pooled

| Especificacion | n | R2 | delta | SE | p-value |
|----------------|---|-----|-------|-----|---------|
| Sin controles | 7563 | 0.4454 | -0.0920 | 0.0227 | 0.0000 |
| Con controles (log_pia, log_pim) | 7563 | 0.4471 | -0.0922 | 0.0226 | 0.0000 |

## 4. Estimacion con FE entidad

Nota: SWITCHER es absorbido por FE entidad (time-invariant).

| Especificacion | n | R2_within | delta | SE |
|----------------|---|-----------|-------|-----|
| FE entidad, sin controles | 7563 | 0.5428 | -0.0920 | 0.0227 |
| FE entidad, con controles | 7563 | 0.5434 | -0.0923 | 0.0227 |

## 5. Interpretacion

- El coeficiente delta = -0.0923 indica que SWITCHER salto
  9.23 pp MENOS que ALWAYS_IN en 2025.
- Esto es DESCRIPTIVO, no causal, porque:
  1. Pre-trends no paralelos (SWITCHER ya estaba por debajo en 2022-2024)
  2. La asignacion a SWITCHER no es aleatoria

## 6. Limitaciones

- SWITCHER tenia cumple_v4 cercano a 0 en pre-periodo (casi sin variacion)
- ALWAYS_IN ya tenia SIGA implementado; no es un 'control puro'
- El supuesto de tendencias paralelas NO se cumple
