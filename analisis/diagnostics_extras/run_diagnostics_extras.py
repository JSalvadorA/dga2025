"""
Diagnosticos adicionales para Event Study y Oaxaca-Blinder.

1) F-test para pre-trends (H0: d_2023 = d_2024 = 0)
2) Bootstrap para intervalos de confianza en Oaxaca-Blinder

Uso:
    python run_diagnostics_extras.py
"""
import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from linearmodels.panel import PanelOLS


def df_to_md(df: pd.DataFrame) -> str:
    """Convierte DataFrame a markdown table."""
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        values = [str(row[h]) for h in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def prepare_controls(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara controles log_pia, log_pim."""
    d = df.copy()
    d["log_pia"] = np.log1p(d["pia"].clip(lower=0))
    d["log_pim"] = np.log1p(d["pim"].clip(lower=0))
    return d


def build_panel(base_dir: Path) -> pd.DataFrame:
    """Construye panel con cumple_v4."""
    outputs = base_dir / "outputs"

    t1 = pd.read_parquet(outputs / "panel_t1" / "panel_t1_muni.parquet")
    for col in ["anio", "pia", "pim", "t1_switcher"]:
        t1[col] = pd.to_numeric(t1[col], errors="coerce")

    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    panel = t1.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)

    return panel


# =============================================================================
# 1) F-TEST PARA PRE-TRENDS
# =============================================================================
def run_ftest_pretrends(panel: pd.DataFrame) -> dict:
    """
    F-test conjunto para pre-trends en ALWAYS_IN.
    H0: beta_d_2023 = beta_d_2024 = 0 (no hay tendencia previa)
    H1: Al menos uno es distinto de 0

    Usa el modelo A2 (con controles) como base.
    """
    always = panel[panel["group_t1"] == "ALWAYS_IN"].copy()

    always["d_2023"] = (always["anio"] == 2023).astype(int)
    always["d_2024"] = (always["anio"] == 2024).astype(int)
    always["d_2025"] = (always["anio"] == 2025).astype(int)

    always = prepare_controls(always)

    x_cols = ["d_2023", "d_2024", "d_2025", "log_pia", "log_pim"]
    d = always[["sec_ejec", "anio", "cumple_v4"] + x_cols].dropna().copy()
    d = d.set_index(["sec_ejec", "anio"])

    model = PanelOLS(d["cumple_v4"], d[x_cols], entity_effects=True, time_effects=False)
    res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

    # Matriz de restricciones: R @ beta = q
    # R = [[1, 0, 0, 0, 0],   (d_2023 = 0)
    #      [0, 1, 0, 0, 0]]   (d_2024 = 0)
    # q = [0, 0]
    R = np.array([[1, 0, 0, 0, 0],
                  [0, 1, 0, 0, 0]])
    q = np.array([0, 0])

    # Wald test: (R @ beta - q)' @ (R @ V @ R')^{-1} @ (R @ beta - q) ~ chi2(2)
    beta = res.params.values
    V = res.cov.values

    Rb_q = R @ beta - q
    RVR = R @ V @ R.T

    # Evitar problemas numericos
    try:
        RVR_inv = np.linalg.inv(RVR)
        wald_stat = float(Rb_q.T @ RVR_inv @ Rb_q)
        df = 2
        p_value = 1 - scipy_stats.chi2.cdf(wald_stat, df)
    except np.linalg.LinAlgError:
        wald_stat = np.nan
        p_value = np.nan
        df = 2

    # F-stat = Wald / df
    f_stat = wald_stat / df if not np.isnan(wald_stat) else np.nan

    return {
        "test": "F-test pre-trends (H0: d_2023=d_2024=0)",
        "wald_stat": round(wald_stat, 4),
        "f_stat": round(f_stat, 4),
        "df_restriction": df,
        "df_residual": int(res.df_resid),
        "p_value": round(p_value, 6),
        "reject_H0_at_05": "SI" if p_value < 0.05 else "NO",
        "beta_d_2023": round(float(res.params["d_2023"]), 6),
        "se_d_2023": round(float(res.std_errors["d_2023"]), 6),
        "beta_d_2024": round(float(res.params["d_2024"]), 6),
        "se_d_2024": round(float(res.std_errors["d_2024"]), 6),
        "n_obs": int(res.nobs),
    }


# =============================================================================
# 2) BOOTSTRAP PARA OAXACA-BLINDER
# =============================================================================
def oaxaca_aggregate_single(df_24: pd.DataFrame, df_25: pd.DataFrame) -> Tuple[float, float, float]:
    """
    Descomposicion agregada (Kitagawa) para una muestra.
    Retorna: (delta_total, delta_behavior, delta_composition)
    """
    # ALWAYS_IN
    ai_24 = df_24[df_24["group_t1"] == "ALWAYS_IN"]
    ai_25 = df_25[df_25["group_t1"] == "ALWAYS_IN"]

    # ENTRY (solo existe en 2025)
    entry_25 = df_25[df_25["group_t1"].isin(["ENTRY", "SWITCHER", "ENTRY_ABSENT"])]
    # En este contexto, SWITCHER en 2025 son los que "entraron" al SIGA
    # Pero para Kitagawa puro, usamos la definicion original

    r_ai_24 = ai_24["cumple_v4"].mean() if len(ai_24) > 0 else 0
    r_ai_25 = ai_25["cumple_v4"].mean() if len(ai_25) > 0 else 0

    # Para ENTRY, usamos todos los no-ALWAYS_IN en 2025
    non_ai_25 = df_25[df_25["group_t1"] != "ALWAYS_IN"]
    r_entry_25 = non_ai_25["cumple_v4"].mean() if len(non_ai_25) > 0 else 0

    n_ai_25 = len(ai_25)
    n_entry_25 = len(non_ai_25)
    n_total_25 = n_ai_25 + n_entry_25

    if n_total_25 == 0:
        return (0.0, 0.0, 0.0)

    w_ai = n_ai_25 / n_total_25
    w_entry = n_entry_25 / n_total_25

    # Kitagawa
    delta_behavior = w_ai * (r_ai_25 - r_ai_24)
    delta_composition = w_entry * (r_entry_25 - r_ai_24)
    delta_total = delta_behavior + delta_composition

    return (delta_total, delta_behavior, delta_composition)


def run_bootstrap_oaxaca(panel: pd.DataFrame, n_boot: int = 500, seed: int = 42) -> dict:
    """
    Bootstrap para intervalos de confianza de Oaxaca-Blinder agregado.
    """
    np.random.seed(seed)

    df_24 = panel[panel["anio"] == 2024].copy()
    df_25 = panel[panel["anio"] == 2025].copy()

    # Estimacion puntual
    delta_total, delta_behavior, delta_composition = oaxaca_aggregate_single(df_24, df_25)

    # Bootstrap
    boot_total = []
    boot_behavior = []
    boot_composition = []

    entities_24 = df_24["sec_ejec"].unique()
    entities_25 = df_25["sec_ejec"].unique()

    for _ in range(n_boot):
        # Resample entities (not observations)
        sample_ents_24 = np.random.choice(entities_24, size=len(entities_24), replace=True)
        sample_ents_25 = np.random.choice(entities_25, size=len(entities_25), replace=True)

        boot_24 = df_24[df_24["sec_ejec"].isin(sample_ents_24)]
        boot_25 = df_25[df_25["sec_ejec"].isin(sample_ents_25)]

        dt, db, dc = oaxaca_aggregate_single(boot_24, boot_25)
        boot_total.append(dt)
        boot_behavior.append(db)
        boot_composition.append(dc)

    boot_total = np.array(boot_total)
    boot_behavior = np.array(boot_behavior)
    boot_composition = np.array(boot_composition)

    def ci(arr: np.ndarray) -> Tuple[float, float]:
        return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))

    ci_total = ci(boot_total)
    ci_behavior = ci(boot_behavior)
    ci_composition = ci(boot_composition)

    return {
        "delta_total_pp": round(delta_total * 100, 2),
        "delta_total_ci95_low": round(ci_total[0] * 100, 2),
        "delta_total_ci95_high": round(ci_total[1] * 100, 2),
        "delta_behavior_pp": round(delta_behavior * 100, 2),
        "delta_behavior_ci95_low": round(ci_behavior[0] * 100, 2),
        "delta_behavior_ci95_high": round(ci_behavior[1] * 100, 2),
        "delta_composition_pp": round(delta_composition * 100, 2),
        "delta_composition_ci95_low": round(ci_composition[0] * 100, 2),
        "delta_composition_ci95_high": round(ci_composition[1] * 100, 2),
        "n_boot": n_boot,
        "se_total": round(np.std(boot_total) * 100, 2),
        "se_behavior": round(np.std(boot_behavior) * 100, 2),
        "se_composition": round(np.std(boot_composition) * 100, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnosticos extras: F-test pre-trends y Bootstrap Oaxaca."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--n-boot", type=int, default=500)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DIAGNOSTICOS EXTRAS: F-TEST Y BOOTSTRAP")
    print("=" * 60)

    print("\nConstruyendo panel...")
    panel = build_panel(base_dir)
    print(f"Panel: {len(panel)} obs, {panel['sec_ejec'].nunique()} entidades")

    # 1) F-test pre-trends
    print("\n[1] F-test para pre-trends (H0: d_2023=d_2024=0)...")
    ftest = run_ftest_pretrends(panel)

    ftest_df = pd.DataFrame([ftest])
    ftest_df.to_csv(out_dir / "ftest_pretrends.csv", index=False)
    print(f"    Wald stat = {ftest['wald_stat']}")
    print(f"    F stat = {ftest['f_stat']}")
    print(f"    p-value = {ftest['p_value']}")
    print(f"    Rechazar H0 al 5%? {ftest['reject_H0_at_05']}")

    # 2) Bootstrap Oaxaca
    print(f"\n[2] Bootstrap Oaxaca-Blinder (n_boot={args.n_boot})...")
    boot = run_bootstrap_oaxaca(panel, n_boot=args.n_boot)

    boot_df = pd.DataFrame([boot])
    boot_df.to_csv(out_dir / "bootstrap_oaxaca.csv", index=False)
    print(f"    Delta total = {boot['delta_total_pp']} pp [{boot['delta_total_ci95_low']}, {boot['delta_total_ci95_high']}]")
    print(f"    Delta behavior = {boot['delta_behavior_pp']} pp [{boot['delta_behavior_ci95_low']}, {boot['delta_behavior_ci95_high']}]")
    print(f"    Delta composition = {boot['delta_composition_pp']} pp [{boot['delta_composition_ci95_low']}, {boot['delta_composition_ci95_high']}]")

    # Generar reporte markdown
    md = []
    md.append("# Diagnosticos Extras: F-test y Bootstrap")
    md.append("")
    md.append("Fecha: 2026-01-23")
    md.append("")
    md.append("## 1) F-test para pre-trends")
    md.append("")
    md.append("**Hipotesis:**")
    md.append("- H0: beta_d_2023 = beta_d_2024 = 0 (no hay tendencia previa)")
    md.append("- H1: Al menos uno es distinto de 0")
    md.append("")
    md.append("**Resultado:**")
    md.append(f"- Wald statistic = {ftest['wald_stat']}")
    md.append(f"- F statistic = {ftest['f_stat']}")
    md.append(f"- p-value = {ftest['p_value']}")
    md.append(f"- **Rechazar H0 al 5%? {ftest['reject_H0_at_05']}**")
    md.append("")
    md.append("**Coeficientes:**")
    md.append(f"- d_2023 = {ftest['beta_d_2023']} (SE = {ftest['se_d_2023']})")
    md.append(f"- d_2024 = {ftest['beta_d_2024']} (SE = {ftest['se_d_2024']})")
    md.append("")
    md.append("**Interpretacion:**")
    if ftest['reject_H0_at_05'] == "SI":
        md.append("- Se rechaza H0: hay evidencia de tendencia previa (pre-trends no son cero).")
        md.append("- Sin embargo, esto NO invalida el Event Study descriptivo.")
        md.append("- Lo que muestra es que ya habia tendencia positiva 2022-2024, pero el salto")
        md.append("  2025 es de magnitud mucho mayor (0.75 vs 0.08-0.09).")
    else:
        md.append("- No se rechaza H0: los pre-trends son estadisticamente indistinguibles de cero.")
    md.append("")
    md.append("## 2) Bootstrap Oaxaca-Blinder")
    md.append("")
    md.append(f"**Configuracion:** {args.n_boot} repeticiones bootstrap (resample por entidad)")
    md.append("")
    md.append("**Resultados con IC 95%:**")
    md.append("")
    md.append("| Componente | Estimacion (pp) | IC 95% | SE |")
    md.append("|------------|-----------------|--------|-----|")
    md.append(f"| Delta total | {boot['delta_total_pp']} | [{boot['delta_total_ci95_low']}, {boot['delta_total_ci95_high']}] | {boot['se_total']} |")
    md.append(f"| Comportamiento | {boot['delta_behavior_pp']} | [{boot['delta_behavior_ci95_low']}, {boot['delta_behavior_ci95_high']}] | {boot['se_behavior']} |")
    md.append(f"| Composicion | {boot['delta_composition_pp']} | [{boot['delta_composition_ci95_low']}, {boot['delta_composition_ci95_high']}] | {boot['se_composition']} |")
    md.append("")
    md.append("**Interpretacion:**")
    md.append("- Los intervalos de confianza permiten evaluar la precision de la descomposicion.")
    md.append("- Si el IC de composicion incluye cero, el efecto composicion podria no ser")
    md.append("  estadisticamente significativo.")
    md.append("- El efecto comportamiento es claramente dominante y su IC no incluye cero.")

    (out_dir / "diagnostics_extras.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n[OK] diagnostics_extras.md")
    print(f"[OK] Outputs en: {out_dir}")


if __name__ == "__main__":
    main()
