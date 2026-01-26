# Oaxaca-Blinder: Descomposicion del salto Ind V4

## 1. Descomposicion agregada (Kitagawa)

Formula:
```
Delta = (N_A/N_25)*(r_A_25 - r_A_24) + (N_E/N_25)*(r_E_25 - r_A_24)
      = Efecto_Comportamiento        + Efecto_Composicion
```

| Componente | Valor (pp) | Share |
|------------|-----------|-------|
| Delta total | 56.96 | 100% |
| Comportamiento (ALWAYS_IN mejora) | 44.87 | 78.8% |
| Composicion (ENTRY entra con tasa diferente) | 12.09 | 21.2% |

Parametros:
- r_A_24 = 0.2274 (1284 UEs)
- r_A_25 = 0.8886 (1284 UEs)
- r_E_25 = 0.6036 (608 UEs)
- w_A = 0.6786, w_E = 0.3214

## 2. Descomposicion multi-anio

| period | r_base | r_target_AI | r_target_ENTRY | n_AI | n_ENTRY | delta_total_pp | delta_behavior_pp | delta_composition_pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022->2023 | 0.1395 | 0.2157 | 0.0 | 1284 | 607 | 0.6967 | 5.1751 | -4.4784 |
| 2023->2024 | 0.2157 | 0.2274 | 0.0049 | 1284 | 607 | -5.973 | 0.7932 | -6.7662 |
| 2024->2025 | 0.2274 | 0.8886 | 0.6036 | 1284 | 608 | 56.9626 | 44.8732 | 12.0894 |

Nota: Para 2022->2023 y 2023->2024, ENTRY=0 (no hay entradas), 
asi que delta_composition=0 y todo es comportamiento.

## 3. Descomposicion individual (LPM Blinder-Oaxaca, ALWAYS_IN)

Modelo: cumple_v4 = b0 + b1*log(PIA) + b2*log(PIM) + e
Aplicado solo a ALWAYS_IN para separar:
  - Endowments: cambio en caracteristicas (composicion de X)
  - Coefficients: cambio en retornos (comportamiento)
  - Interaction: termino cruzado

| Componente | Valor |
|------------|-------|
| y_bar_24 | 0.2274 |
| y_bar_25 | 0.8886 |
| Delta_y | 0.6612 |
| Endowments | 0.0007 |
| Coefficients | 0.6589 |
| Interaction | 0.0016 |
| R2_2024 | 0.0007 |
| R2_2025 | 0.0148 |

### Detalle por variable
| variable | endowment | coefficient | interaction |
| --- | --- | --- | --- |
| const | 0.0 | 0.280819 | 0.0 |
| log_pia | -0.000235 | 0.083907 | 0.000311 |
| log_pim | 0.000943 | 0.294174 | 0.001295 |

### Coeficientes LPM
| Variable | beta_24 | se_24 | beta_25 | se_25 |
|----------|---------|-------|---------|-------|
| const | 0.076564 | 0.154528 | 0.357383 | 0.135189 |
| log_pia | -0.003977 | 0.026838 | 0.001287 | 0.023136 |
| log_pim | 0.012998 | 0.029783 | 0.030845 | 0.025801 |

## Interpretacion

### Descomposicion AGREGADA (Kitagawa)
- Separa el salto total en lo que aporta cada grupo (ALWAYS_IN vs ENTRY).
- Resultado robusto: 78.8% del salto proviene de que ALWAYS_IN mejoro su tasa,
  no de la entrada de nuevas entidades.
- Esto justifica el mensaje central: el salto esta dominado por cambio dentro
  de las mismas entidades, no por cambio en composicion.

### Descomposicion INDIVIDUAL (LPM Blinder-Oaxaca)
- Separa el cambio de tasa dentro de ALWAYS_IN en:
  - Endowments: cambio en caracteristicas (composicion de X)
  - Coefficients: cambio en retornos (relacion X -> Y)
- LIMITACION IMPORTANTE: R2 muy bajo (0.07% en 2024, 1.5% en 2025).
  Esto significa que log_pia y log_pim NO explican cumple_v4.
- Endowments ~ 0: trivial dado que X no predice Y.
- Coefficients ~ 0.66: captura TODO lo que cambio que no es composicion de X.
  En terminos tecnicos, refleja factores NO OBSERVADOS en los datos.

### Interpretacion correcta del "Coefficients effect"
- NO significa literalmente "cambio de comportamiento de las entidades".
- Significa: "algo cambio en la relacion estructura -> cumplimiento que no
  esta capturado por PIA/PIM".
- Hipotesis mas plausible: el cambio de plataforma (SIGA Escritorio -> SIGA Web)
  es el driver no observado que explica el salto.

### Conclusion para el informe
- La narrativa correcta es: "El salto es explicado por factores no capturados
  por las variables presupuestales (PIA/PIM), lo cual es consistente con el
  cambio de plataforma tecnologica implementado en 2025."
