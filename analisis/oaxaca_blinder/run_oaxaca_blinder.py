"""
Oaxaca-Blinder Decomposition del salto del indicador V4.

Descompone el cambio en Ind_V4 (2024 -> 2025) en:
  - Efecto composicion: entrada de nuevas entidades (ENTRY) con tasa diferente.
  - Efecto comportamiento: cambio en tasa de cumplimiento de ALWAYS_IN.

Dos niveles:
  1) Descomposicion AGREGADA (Kitagawa): solo tasas y pesos.
  2) Descomposicion INDIVIDUAL (LPM Blinder-Oaxaca): con covariables X.

Nota: No identifica mecanismo causal especifico.
Viabilidad: ALTA (segun rese2.md).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


def df_to_md(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        values = [str(row[h]) for h in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_panel(base_dir: Path) -> pd.DataFrame:
    """Panel con cumple_v4 y covariables para todas las entidades del padron."""
    outputs = base_dir / "outputs"

    # Budget data (all municipalities)
    budget = pd.read_parquet(outputs / "processed" / "presupuesto_muni_panel.parquet")
    for col in ["anio", "pia", "pim", "devengado"]:
        budget[col] = pd.to_numeric(budget[col], errors="coerce")
    budget["sec_ejec"] = budget["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)

    # CMN cumple_v4
    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    # Padron (for group assignment)
    padron = pd.read_csv(
        outputs / "padron" / "padron_largo.csv",
        dtype=str, encoding="utf-8-sig"
    )
    padron["sec_ejec"] = padron["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    padron["anio"] = pd.to_numeric(padron["anio"], errors="coerce").astype("Int64")
    padron["siga_implementado"] = padron["siga_implementado"].str.upper().str.strip()
    padron["categoria"] = padron["categoria"].str.upper().str.strip()

    # Filter municipalities
    muni_padron = padron[padron["categoria"].str.contains("MUNICIPALIDADES", na=False)]
    muni_padron = muni_padron[muni_padron["anio"].isin([2022, 2023, 2024, 2025])]

    # Build groups
    pre_ues = set(
        muni_padron[(muni_padron["anio"] <= 2024) & (muni_padron["siga_implementado"] == "SI")]["sec_ejec"]
    )
    post_ues = set(muni_padron[muni_padron["anio"] == 2025]["sec_ejec"])

    def assign_group(se):
        if se in pre_ues and se in post_ues:
            return "ALWAYS_IN"
        elif se not in pre_ues and se in post_ues:
            return "ENTRY"
        elif se in pre_ues and se not in post_ues:
            return "EXIT"
        return "OTHER"

    all_ues = pre_ues | post_ues
    group_map = {se: assign_group(se) for se in all_ues}

    # Merge
    panel = budget.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)
    panel["group"] = panel["sec_ejec"].map(group_map)
    panel = panel[panel["group"].isin(["ALWAYS_IN", "ENTRY"])].copy()

    # Covariates
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))
    if "departamento_code" in panel.columns:
        panel["departamento_code"] = panel["departamento_code"].fillna("UNK").astype(str)

    return panel


def aggregate_decomposition(panel: pd.DataFrame) -> dict:
    """
    Kitagawa-style aggregate decomposition.

    Ind_2024 = r_A_24 (approx, since padron 2024 ~ ALWAYS_IN)
    Ind_2025 = (N_A/N_25)*r_A_25 + (N_E/N_25)*r_E_25

    Delta = Ind_25 - Ind_24
          = (N_A/N_25)*(r_A_25 - r_A_24)  ... Behavior effect
          + (N_E/N_25)*(r_E_25 - r_A_24)  ... Composition effect
    """
    # 2024 rates (only ALWAYS_IN in padron)
    a24 = panel[(panel["anio"] == 2024) & (panel["group"] == "ALWAYS_IN")]
    r_A_24 = a24["cumple_v4"].mean()
    n_A_24 = len(a24)

    # 2025 rates
    a25 = panel[(panel["anio"] == 2025) & (panel["group"] == "ALWAYS_IN")]
    e25 = panel[(panel["anio"] == 2025) & (panel["group"] == "ENTRY")]
    r_A_25 = a25["cumple_v4"].mean()
    r_E_25 = e25["cumple_v4"].mean() if len(e25) > 0 else np.nan
    n_A_25 = len(a25)
    n_E_25 = len(e25)
    n_25 = n_A_25 + n_E_25

    # Weights
    w_A = n_A_25 / n_25
    w_E = n_E_25 / n_25

    # Aggregate indicators
    ind_24 = r_A_24
    ind_25 = w_A * r_A_25 + w_E * r_E_25

    # Decomposition
    delta_total = ind_25 - ind_24
    delta_behavior = w_A * (r_A_25 - r_A_24)
    delta_composition = w_E * (r_E_25 - r_A_24)

    # Shares
    share_behavior = delta_behavior / delta_total if delta_total != 0 else np.nan
    share_composition = delta_composition / delta_total if delta_total != 0 else np.nan

    return {
        "r_A_24": r_A_24,
        "r_A_25": r_A_25,
        "r_E_25": r_E_25,
        "n_A_24": n_A_24,
        "n_A_25": n_A_25,
        "n_E_25": n_E_25,
        "n_25": n_25,
        "w_A": w_A,
        "w_E": w_E,
        "ind_24": ind_24,
        "ind_25": ind_25,
        "delta_total_pp": delta_total * 100,
        "delta_behavior_pp": delta_behavior * 100,
        "delta_composition_pp": delta_composition * 100,
        "share_behavior": share_behavior,
        "share_composition": share_composition,
    }


def individual_decomposition(panel: pd.DataFrame) -> dict:
    """
    LPM-based Blinder-Oaxaca decomposition.

    Model: cumple_v4 = beta_0 + beta_1*log_pia + beta_2*log_pim + epsilon

    Three-fold decomposition:
      Delta_Y_bar = (X_bar_25 - X_bar_24) * beta_hat_24   ... Endowments (composition)
                  + X_bar_24 * (beta_hat_25 - beta_hat_24) ... Coefficients (behavior)
                  + (X_bar_25 - X_bar_24) * (beta_hat_25 - beta_hat_24) ... Interaction

    Applied only to ALWAYS_IN (same entities both years).
    """
    always = panel[panel["group"] == "ALWAYS_IN"].copy()

    d24 = always[always["anio"] == 2024][["cumple_v4", "log_pia", "log_pim"]].dropna()
    d25 = always[always["anio"] == 2025][["cumple_v4", "log_pia", "log_pim"]].dropna()

    if d24.empty or d25.empty:
        return {"error": "Insufficient data for individual decomposition"}

    X_vars = ["log_pia", "log_pim"]

    # Fit LPM for each year
    X24 = sm.add_constant(d24[X_vars])
    X25 = sm.add_constant(d25[X_vars])
    y24 = d24["cumple_v4"]
    y25 = d25["cumple_v4"]

    m24 = sm.OLS(y24, X24).fit(cov_type="HC1")
    m25 = sm.OLS(y25, X25).fit(cov_type="HC1")

    beta_24 = m24.params.values  # [const, log_pia, log_pim]
    beta_25 = m25.params.values

    X_bar_24 = X24.mean().values
    X_bar_25 = X25.mean().values

    y_bar_24 = y24.mean()
    y_bar_25 = y25.mean()

    # Three-fold decomposition
    delta_X = X_bar_25 - X_bar_24
    delta_beta = beta_25 - beta_24

    endowments = float(delta_X @ beta_24)
    coefficients = float(X_bar_24 @ delta_beta)
    interaction = float(delta_X @ delta_beta)
    total = endowments + coefficients + interaction

    # Also compute detailed (per variable)
    var_names = ["const"] + X_vars
    detail = []
    for i, v in enumerate(var_names):
        detail.append({
            "variable": v,
            "endowment": delta_X[i] * beta_24[i],
            "coefficient": X_bar_24[i] * delta_beta[i],
            "interaction": delta_X[i] * delta_beta[i],
        })

    return {
        "y_bar_24": y_bar_24,
        "y_bar_25": y_bar_25,
        "delta_y": y_bar_25 - y_bar_24,
        "n_24": len(d24),
        "n_25": len(d25),
        "endowments_total": endowments,
        "coefficients_total": coefficients,
        "interaction_total": interaction,
        "total_decomposed": total,
        "check_residual": (y_bar_25 - y_bar_24) - total,
        "beta_24": dict(zip(var_names, beta_24)),
        "beta_25": dict(zip(var_names, beta_25)),
        "se_24": dict(zip(var_names, m24.bse.values)),
        "se_25": dict(zip(var_names, m25.bse.values)),
        "detail": detail,
        "r2_24": m24.rsquared,
        "r2_25": m25.rsquared,
    }


def multi_year_aggregate(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate decomposition for each year-pair: t vs t+1."""
    results = []
    for base_year in [2022, 2023, 2024]:
        target_year = base_year + 1
        if target_year > 2025:
            continue

        a_base = panel[(panel["anio"] == base_year) & (panel["group"] == "ALWAYS_IN")]
        a_target = panel[(panel["anio"] == target_year) & (panel["group"] == "ALWAYS_IN")]
        e_target = panel[(panel["anio"] == target_year) & (panel["group"] == "ENTRY")]

        if a_base.empty or a_target.empty:
            continue

        r_base = a_base["cumple_v4"].mean()
        r_target = a_target["cumple_v4"].mean()
        r_entry = e_target["cumple_v4"].mean() if len(e_target) > 0 else np.nan
        n_a = len(a_target)
        n_e = len(e_target) if len(e_target) > 0 else 0
        n_total = n_a + n_e

        w_a = n_a / n_total if n_total > 0 else 1
        w_e = n_e / n_total if n_total > 0 else 0

        delta_behavior = w_a * (r_target - r_base)
        delta_composition = w_e * (r_entry - r_base) if not np.isnan(r_entry) else 0
        delta_total = delta_behavior + delta_composition

        results.append({
            "period": f"{base_year}->{target_year}",
            "r_base": r_base,
            "r_target_AI": r_target,
            "r_target_ENTRY": r_entry,
            "n_AI": n_a,
            "n_ENTRY": n_e,
            "delta_total_pp": delta_total * 100,
            "delta_behavior_pp": delta_behavior * 100,
            "delta_composition_pp": delta_composition * 100,
        })

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Oaxaca-Blinder decomposition del salto V4.")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Construyendo panel...")
    panel = build_panel(base_dir)
    print(f"  Panel: {len(panel)} rows, {panel['sec_ejec'].nunique()} UEs")

    # 1) Aggregate decomposition (2024->2025)
    print("1) Descomposicion agregada (2024->2025)...")
    agg = aggregate_decomposition(panel)
    agg_df = pd.DataFrame([{k: v for k, v in agg.items() if not isinstance(v, (dict, list))}])
    agg_df.to_csv(out_dir / "aggregate_decomposition.csv", index=False)
    print(f"  Delta total: {agg['delta_total_pp']:.2f}pp")
    print(f"  Behavior: {agg['delta_behavior_pp']:.2f}pp ({agg['share_behavior']:.1%})")
    print(f"  Composition: {agg['delta_composition_pp']:.2f}pp ({agg['share_composition']:.1%})")

    # 2) Multi-year aggregate
    print("2) Descomposicion multi-anio...")
    multi = multi_year_aggregate(panel)
    multi.to_csv(out_dir / "multi_year_decomposition.csv", index=False)

    # 3) Individual LPM decomposition (ALWAYS_IN only)
    print("3) Descomposicion individual (LPM, ALWAYS_IN)...")
    indiv = individual_decomposition(panel)
    if "error" not in indiv:
        # Save detail
        detail_df = pd.DataFrame(indiv["detail"])
        detail_df.to_csv(out_dir / "individual_detail.csv", index=False)

        # Summary
        indiv_summary = {
            "y_bar_24": indiv["y_bar_24"],
            "y_bar_25": indiv["y_bar_25"],
            "delta_y": indiv["delta_y"],
            "endowments": indiv["endowments_total"],
            "coefficients": indiv["coefficients_total"],
            "interaction": indiv["interaction_total"],
            "check_residual": indiv["check_residual"],
            "r2_24": indiv["r2_24"],
            "r2_25": indiv["r2_25"],
            "n_24": indiv["n_24"],
            "n_25": indiv["n_25"],
        }
        pd.DataFrame([indiv_summary]).to_csv(out_dir / "individual_summary.csv", index=False)
        print(f"  Endowments: {indiv['endowments_total']:.4f}")
        print(f"  Coefficients: {indiv['coefficients_total']:.4f}")
        print(f"  Interaction: {indiv['interaction_total']:.4f}")
    else:
        print(f"  ERROR: {indiv['error']}")

    # Generate markdown report
    md = []
    md.append("# Oaxaca-Blinder: Descomposicion del salto Ind V4")
    md.append("")
    md.append("## 1. Descomposicion agregada (Kitagawa)")
    md.append("")
    md.append("Formula:")
    md.append("```")
    md.append("Delta = (N_A/N_25)*(r_A_25 - r_A_24) + (N_E/N_25)*(r_E_25 - r_A_24)")
    md.append("      = Efecto_Comportamiento        + Efecto_Composicion")
    md.append("```")
    md.append("")
    md.append(f"| Componente | Valor (pp) | Share |")
    md.append(f"|------------|-----------|-------|")
    md.append(f"| Delta total | {agg['delta_total_pp']:.2f} | 100% |")
    md.append(f"| Comportamiento (ALWAYS_IN mejora) | {agg['delta_behavior_pp']:.2f} | {agg['share_behavior']:.1%} |")
    md.append(f"| Composicion (ENTRY entra con tasa diferente) | {agg['delta_composition_pp']:.2f} | {agg['share_composition']:.1%} |")
    md.append("")
    md.append("Parametros:")
    md.append(f"- r_A_24 = {agg['r_A_24']:.4f} ({agg['n_A_24']} UEs)")
    md.append(f"- r_A_25 = {agg['r_A_25']:.4f} ({agg['n_A_25']} UEs)")
    md.append(f"- r_E_25 = {agg['r_E_25']:.4f} ({agg['n_E_25']} UEs)")
    md.append(f"- w_A = {agg['w_A']:.4f}, w_E = {agg['w_E']:.4f}")
    md.append("")
    md.append("## 2. Descomposicion multi-anio")
    md.append("")
    md.append(df_to_md(multi.round(4)))
    md.append("")
    md.append("Nota: Para 2022->2023 y 2023->2024, ENTRY=0 (no hay entradas), ")
    md.append("asi que delta_composition=0 y todo es comportamiento.")
    md.append("")

    if "error" not in indiv:
        md.append("## 3. Descomposicion individual (LPM Blinder-Oaxaca, ALWAYS_IN)")
        md.append("")
        md.append("Modelo: cumple_v4 = b0 + b1*log(PIA) + b2*log(PIM) + e")
        md.append("Aplicado solo a ALWAYS_IN para separar:")
        md.append("  - Endowments: cambio en caracteristicas (composicion de X)")
        md.append("  - Coefficients: cambio en retornos (comportamiento)")
        md.append("  - Interaction: termino cruzado")
        md.append("")
        md.append(f"| Componente | Valor |")
        md.append(f"|------------|-------|")
        md.append(f"| y_bar_24 | {indiv['y_bar_24']:.4f} |")
        md.append(f"| y_bar_25 | {indiv['y_bar_25']:.4f} |")
        md.append(f"| Delta_y | {indiv['delta_y']:.4f} |")
        md.append(f"| Endowments | {indiv['endowments_total']:.4f} |")
        md.append(f"| Coefficients | {indiv['coefficients_total']:.4f} |")
        md.append(f"| Interaction | {indiv['interaction_total']:.4f} |")
        md.append(f"| R2_2024 | {indiv['r2_24']:.4f} |")
        md.append(f"| R2_2025 | {indiv['r2_25']:.4f} |")
        md.append("")
        md.append("### Detalle por variable")
        md.append(df_to_md(detail_df.round(6)))
        md.append("")
        md.append("### Coeficientes LPM")
        md.append(f"| Variable | beta_24 | se_24 | beta_25 | se_25 |")
        md.append(f"|----------|---------|-------|---------|-------|")
        for v in indiv["beta_24"]:
            md.append(f"| {v} | {indiv['beta_24'][v]:.6f} | {indiv['se_24'][v]:.6f} | {indiv['beta_25'][v]:.6f} | {indiv['se_25'][v]:.6f} |")
    md.append("")
    md.append("## Interpretacion")
    md.append("")
    md.append("- La descomposicion AGREGADA separa el salto en lo que aporta cada grupo.")
    md.append("- La descomposicion INDIVIDUAL (ALWAYS_IN) separa si el cambio de tasa")
    md.append("  dentro del mismo grupo se debe a cambio en caracteristicas (endowments)")
    md.append("  o a cambio en como esas caracteristicas se asocian con cumplimiento (coefficients).")
    md.append("- Endowments ~ 0 indica que las mismas entidades cambiaron su comportamiento,")
    md.append("  no que su perfil presupuestal cambio.")
    md.append("- Coefficients grandes indica cambio en la relacion estructura -> cumplimiento.")

    (out_dir / "oaxaca_blinder.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("[OK] oaxaca_blinder.md")


if __name__ == "__main__":
    main()
