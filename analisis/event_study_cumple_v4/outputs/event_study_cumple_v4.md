# Event Study: cumple_v4 como outcome

## Tasas descriptivas (cumple_v4 por grupo y anio)
| anio | group_t1 | n | cumple | rate |
| --- | --- | --- | --- | --- |
| 2022 | ALWAYS_IN | 1283 | 179.0 | 0.1395 |
| 2022 | SWITCHER | 607 | 1.0 | 0.0016 |
| 2023 | ALWAYS_IN | 1284 | 277.0 | 0.2157 |
| 2023 | SWITCHER | 607 | 0.0 | 0.0 |
| 2024 | ALWAYS_IN | 1284 | 292.0 | 0.2274 |
| 2024 | SWITCHER | 607 | 3.0 | 0.0049 |
| 2025 | ALWAYS_IN | 1284 | 1141.0 | 0.8886 |
| 2025 | ENTRY_ABSENT | 1 | 0.0 | 0.0 |
| 2025 | SWITCHER | 607 | 367.0 | 0.6046 |

## Parte A: Descriptivo puro (ALWAYS_IN, year dummies, base=2022)

Responde: hubo salto abrupto en cumple_v4 en 2025?
No causal; documenta serie temporal dentro de ALWAYS_IN.

| spec | n | r2_within | beta_d_2023 | se_d_2023 | beta_d_2024 | se_d_2024 | beta_d_2025 | se_d_2025 | beta_log_pia | se_log_pia | beta_log_pim | se_log_pim |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1_year_dummies_FE_entity | 5135 | 0.531793 | 0.076302 | 0.006449 | 0.087984 | 0.008443 | 0.749199 | 0.006686 | nan | nan | nan | nan |
| A2_year_dummies_controls_FE_entity | 5135 | 0.53203 | 0.080078 | 0.007053 | 0.091604 | 0.009986 | 0.751514 | 0.008513 | -0.005441 | 0.008376 | 0.022416 | 0.016813 |

Interpretacion:
- d_2023/d_2024 muestran tendencia positiva previa (0.08 y 0.09 pp respectivamente).
- d_2025 = 0.75 es un salto abrupto, mucho mayor que la tendencia 2022-2024.
- NOTA: Esto es analisis DESCRIPTIVO puro (sin grupo control). La tendencia previa
  no invalida el hallazgo; al contrario, REFUERZA que el salto 2025 es excepcional
  respecto al patron historico.

## Parte B: Contraste SWITCHER vs ALWAYS_IN (cumple_v4)

Responde: los SWITCHER saltaron mas en cumple_v4?
Hereda problema de pre-trends de T1. Contraste descriptivo, no causal.

| n | r2_within | beta_switcher_2023 | se_switcher_2023 | beta_switcher_2024 | se_switcher_2024 | beta_switcher_2025 | se_switcher_2025 | spec | beta_log_pia | se_log_pia | beta_log_pim | se_log_pim | beta_t1_post | se_t1_post |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7563 | -0.049221 | -0.077949 | nan | -0.084689 | 0.002815 | -0.146233 | 0.015558 | B1_contrast_FE_entity_time | nan | nan | nan | nan | nan | nan |
| 7563 | -0.028701 | -0.071467 | nan | -0.05829 | 0.005483 | -0.101219 | 0.015877 | B2_contrast_controls_FE_region_year | 0.001226 | 0.006317 | 0.006151 | 0.008741 | nan | nan |
| 7563 | -0.046835 | nan | nan | nan | nan | nan | nan | B3_twfe_t1_post_FE_entity_time | nan | nan | nan | nan | -0.092015 | 0.030286 |

Interpretacion:
- switcher_2023/2024 son pre-trends del contraste. Valores negativos indican que
  SWITCHER ya estaba por debajo de ALWAYS_IN antes de 2025.
- SE NaN en switcher_2023: SWITCHER tiene cumple_v4=0 en 2023 (varianza ~0),
  lo que genera problemas numericos en la matriz de covarianza.
- switcher_2025 = -0.10 a -0.15: SWITCHER salta MENOS que ALWAYS_IN en 2025.
  Esto es coherente con las tasas observadas:
    - SWITCHER: 0.005 -> 0.60 (salto enorme pero desde base muy baja)
    - ALWAYS_IN: 0.23 -> 0.89 (salto mayor en terminos absolutos)
- B3 (t1_post = -0.092): confirma que SWITCHER salta ~9pp MENOS que ALWAYS_IN.
- R2_within negativo: es matematicamente posible en modelos FE con outcome binario;
  indica baja capacidad explicativa del modelo, no necesariamente colinealidad severa.
- NOTA: Este contraste es DESCRIPTIVO, no causal. Los pre-trends no paralelos
  impiden interpretacion causal estricta.
