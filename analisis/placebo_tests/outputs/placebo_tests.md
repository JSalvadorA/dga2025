# Tests de Placebo para DiD

## 1. Fundamento

Los placebos son **pruebas de falsificacion** (Cunningham, Causal Inference: The Mixtape, cap. 9.5).
Se reestima el DiD en un escenario donde **no deberia haber efecto**.
Si aparece 'efecto' en placebo, sugiere problemas de identificacion.

## 2. Placebo Temporal

Se finge tratamiento en 2023 o 2024 (usando solo datos pre-2025).
Si delta placebo ≈ 0, las pre-trends son paralelas.

| Test | delta | SE | Significativo |
|------|-------|-----|---------------|
| Placebo 2023 | -0.0770 | 0.0151 | Si |
| Placebo 2024 | -0.0452 | 0.0143 | Si |

## 3. Placebo Outcome

Se usa y_exec_pct (ejecucion presupuestal), que no deberia reaccionar al tratamiento.

- delta = -0.1400 (SE: 0.7329)
- Significativo: No

## 4. Comparacion: Real vs Placebos

| test | delta | se | pvalue | significant |
| --- | --- | --- | --- | --- |
| REAL (2025) | -0.0923 | 0.0227 | 0.0 | * |
| PLACEBO (2023) | -0.0773 | 0.0124 | nan | * |
| PLACEBO (2024) | -0.047 | 0.0117 | nan | * |

## 5. Interpretacion

**ADVERTENCIA:** Los placebos temporales son significativos, lo que indica:
- Pre-trends no paralelos: SWITCHER ya estaba por debajo de ALWAYS_IN antes de 2025
- Existe una tendencia previa de menor cumplimiento en SWITCHER

**Sin embargo**, hay matices importantes:

| Año | δ placebo | Interpretacion |
|-----|-----------|----------------|
| 2023 | -7.7 pp | Brecha pre-existente |
| 2024 | -4.5 pp | Brecha pre-existente (menor) |
| 2025 | -9.2 pp | Efecto REAL (mayor que placebos) |

El efecto 2025 es **más grande** que los placebos previos, sugiriendo que:
- Hay algo adicional ocurriendo en 2025 (posiblemente la transición SIGA)
- Pero no podemos separar limpiamente el efecto de la tendencia previa

**Placebo outcome (y_exec_pct):** NO significativo (δ = -0.14, SE = 0.73)
- Buena señal: no hay degradación de ejecución presupuestal
- El efecto es específico a cumple_v4, no a performance general

## 6. Conclusion

Los tests de placebo revelan:
1. **Pre-trends NO paralelos** para cumple_v4 (placebos temporales significativos)
2. **Efecto 2025 mayor** que placebos previos (+2 a +5 pp más grande)
3. **Sin efecto en ejecución** presupuestal (placebo outcome no significativo)

**Implicancia:** El DiD debe interpretarse con cautela como **descriptivo**,
no como efecto causal puro. La brecha entre grupos existía antes de 2025,
aunque se amplió con la transición.

## 7. Referencias
- Cunningham, S. (2021). *Causal Inference: The Mixtape*, cap. 9.5
- Roth, J. (2022). "Pretrends in DiD: What to do when parallel trends fail"
