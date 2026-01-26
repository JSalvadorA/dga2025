# DiD con Propensity Score Matching (PSM-DiD)

## 1. Objetivo

Reducir sesgo por diferencias observables entre SWITCHER y ALWAYS_IN
emparejando entidades con caracteristicas similares antes del tratamiento.

## 2. Procedimiento

1. Estimar P(SWITCHER=1 | log_pia, log_pim) con logit
2. Matching 1:1 nearest neighbor con caliper
3. Verificar balance de covariables
4. Estimar DiD en muestra emparejada

## 3. Propensity Score

| Grupo | n | P-score medio |
|-------|---|---------------|
| SWITCHER | 607 | 0.3822 |
| ALWAYS_IN | 1284 | 0.2921 |

## 4. Matching (caliper=0.2)

- Pares emparejados: **607** de 607 tratados (100.0%)
- Distancia media: 0.0024

## 5. Balance de covariables

| variable | mean_treated_before | mean_control_before | smd_before | mean_treated_after | mean_control_after | smd_after | reduction_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| log_pia | 15.106 | 15.9382 | -0.6185 | 15.106 | 15.0947 | 0.0084 | 98.6418 |
| log_pim | 15.694 | 16.483 | -0.6387 | 15.694 | 15.7117 | -0.0143 | 97.7554 |

Nota: SMD (Standardized Mean Difference). |SMD| < 0.1 indica buen balance.

## 6. Resultados DiD (muestra emparejada)

| Grupo | Pre (2022-2024) | Post (2025) | Diferencia |
|-------|-----------------|-------------|------------|
| ALWAYS_IN (matched) | 0.1922 | 0.8616 | 0.6694 |
| SWITCHER (matched) | 0.0022 | 0.6046 | 0.6024 |
| **DiD** | | | **-0.0670** |

### Regresion DiD (con controles)

- delta (ATT) = **-0.0661** (SE: 0.0259)
- p-value = 0.0108
- n = 4856, R2 = 0.4566

## 7. Interpretacion

- En la muestra emparejada, SWITCHER salto -6.61 pp
  MENOS que ALWAYS_IN comparable.
- El matching reduce sesgo por diferencias en PIA/PIM pero:
  - No corrige seleccion en no-observables
  - Pre-trends aun pueden diferir

## 8. Limitaciones

- Solo corrige por diferencias OBSERVABLES (PIA, PIM)
- No corrige por capacidad tecnica, motivacion, etc.
- El supuesto CIA (Conditional Independence) puede no cumplirse
