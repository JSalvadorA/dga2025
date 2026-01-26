# Heterogeneidad por quintiles PIA/PIM

Outcome: cumple_v4. Muestra: ALWAYS_IN.
Quintiles basados en PIA 2024 (time-invariant).

## 1. Estadisticas por quintil PIA
| quintil_pia | n_entities | pia_mean | pia_median | pia_min | pia_max | cumple_v4_mean |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | 257 | 1380096.97 | 1374826.0 | 567287 | 2257615 | 0.34 |
| Q2 | 257 | 3578658.79 | 3465657.0 | 2272428 | 5270155 | 0.37 |
| Q3 | 256 | 8106208.76 | 7764754.0 | 5280365 | 11802729 | 0.36 |
| Q4 | 257 | 17938720.05 | 16792112.0 | 11989238 | 27694999 | 0.38 |
| Q5 | 257 | 88129592.48 | 57842369.0 | 27779093 | 1565201206 | 0.39 |

## 2. Efecto post_2025 por quintil PIA (separado)

FE: entidad. SE: cluster entity+time.

| quintile | n_entities | n_obs | beta_post_2025 | se_post_2025 | r2_within | raw_pre_mean | raw_post_mean | raw_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | 257 | 1028 | 0.6524 | 0.0183 | 0.4777 | 0.1725 | 0.8249 | 0.6524 |
| Q2 | 257 | 1028 | 0.6783 | 0.0438 | 0.5032 | 0.2049 | 0.8833 | 0.6783 |
| Q3 | 256 | 1023 | 0.6782 | 0.03 | 0.5173 | 0.189 | 0.8672 | 0.6781 |
| Q4 | 257 | 1028 | 0.7432 | 0.0356 | 0.5826 | 0.1907 | 0.9339 | 0.7432 |
| Q5 | 257 | 1028 | 0.7198 | 0.0371 | 0.5465 | 0.214 | 0.9339 | 0.7198 |

## 3. Efecto post_2025 por quintil PIM (separado)

| quintile | n_entities | n_obs | beta_post_2025 | se_post_2025 | r2_within | raw_pre_mean | raw_post_mean | raw_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | 257 | 1028 | 0.6576 | 0.0229 | 0.4825 | 0.179 | 0.8366 | 0.6576 |
| Q2 | 257 | 1028 | 0.6965 | 0.0303 | 0.5351 | 0.1829 | 0.8794 | 0.6965 |
| Q3 | 256 | 1024 | 0.6823 | 0.034 | 0.5078 | 0.2005 | 0.8828 | 0.6823 |
| Q4 | 257 | 1027 | 0.7236 | 0.0267 | 0.5654 | 0.1909 | 0.9144 | 0.7235 |
| Q5 | 257 | 1028 | 0.7121 | 0.0407 | 0.5362 | 0.2179 | 0.93 | 0.7121 |

## 4. Modelo con interacciones (PIA)

Spec: cumple_v4 ~ post_2025 + post_2025*Q2 + ... + post_2025*Q5 | FE_entity
Base: Q1 (entidades mas pequenas).
Interpretacion: post_2025 = efecto para Q1; post_x_Qk = diferencial de Qk vs Q1.

n = 5135, R2_within = 0.5263

| Variable | beta | se |
|----------|------|-----|
| post_2025 | 0.6524 | 0.0183 |
| post_x_Q2 | 0.0259 | 0.0413 |
| post_x_Q3 | 0.0258 | 0.0300 |
| post_x_Q4 | 0.0908 | 0.0329 |
| post_x_Q5 | 0.0674 | 0.0340 |

## 5. Modelo con interacciones + controles (PIA)

Spec: cumple_v4 ~ post_2025 + post_2025*Qk + log_pia + log_pim | FE_entity + region_year

Nota: region_year absorbio post_2025; se uso FE entidad sin region_year en esta especificacion.

n = 5135, R2_within = 0.5278

| Variable | beta | se |
|----------|------|-----|
| post_2025 | 0.6318 | 0.0189 |
| post_x_Q2 | 0.0358 | 0.0398 |
| post_x_Q3 | 0.0379 | 0.0329 |
| post_x_Q4 | 0.1038 | 0.0345 |
| post_x_Q5 | 0.0802 | 0.0353 |
| log_pia | 0.0329 | 0.0177 |
| log_pim | 0.0036 | 0.0226 |

## Interpretacion

### Lectura de coeficientes
- post_2025 (base Q1): efecto para entidades pequenas = 0.65 (65pp de salto).
- post_x_Qk: diferencial del quintil k respecto a Q1.
  - Q2, Q3: ~0.03, no significativos -> salto similar a Q1.
  - Q4: 0.09 (SE 0.03), significativo -> salta ~9pp mas que Q1.
  - Q5: 0.07 (SE 0.04), marginalmente significativo -> salta ~7pp mas que Q1.

### Patron observado
- El salto es GENERALIZADO: todos los quintiles saltan >65pp.
- Hay heterogeneidad MODERADA: Q4/Q5 saltan algo mas que Q1/Q2/Q3.
- Patron NO estrictamente monotono: Q4 > Q5 (las MAS grandes no son las que mas saltan).

### Consistencia con Oaxaca-Blinder
- El R2 bajo en Oaxaca individual (PIA/PIM explican poco) es CONSISTENTE con
  heterogeneidad moderada aqui: el tamano presupuestal modula levemente el efecto,
  pero NO es el driver principal del salto.

### Conclusion para el informe
- El salto de cumplimiento en 2025 es GENERALIZADO en todos los tamanos de entidad.
- Entidades medianas-grandes (Q4) muestran el mayor salto (~74pp vs ~65pp en Q1).
- La diferencia de ~9pp entre Q4 y Q1 es estadisticamente significativa pero
  MODESTA comparada con el salto base de 65pp.
- Implicancia de politica: el cambio de plataforma beneficio a todas las entidades,
  con un efecto ligeramente mayor en entidades medianas-grandes. Estrategias de
  soporte tecnico focalizado a entidades pequenas podrian reducir esta brecha.

### Limitaciones
- Interpretacion exploratoria, no causal estricta.
- El outcome es binario; la regresion lineal es aproximacion.
- Los quintiles se basan en PIA 2024, asumiendo estabilidad temporal.
