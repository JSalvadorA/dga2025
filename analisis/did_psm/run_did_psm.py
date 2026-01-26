"""
DiD con Propensity Score Matching (PSM-DiD).

Objetivo: Reducir sesgo por diferencias observables entre SWITCHER y ALWAYS_IN.

Pasos:
  1. Estimar P(SWITCHER=1 | X) usando caracteristicas pre-tratamiento
  2. Emparejar cada SWITCHER con ALWAYS_IN de propensity score similar
  3. Verificar balance de covariables post-matching
  4. Estimar DiD en muestra emparejada
  5. Reportar ATT (Average Treatment Effect on Treated)

Covariables para matching:
  - log(PIA_2024): tamano presupuestal
  - log(PIM_2024): presupuesto modificado
  - departamento_code: region geografica

Limitaciones:
  - Solo corrige por diferencias OBSERVABLES
  - No corrige por seleccion en no-observables (capacidad tecnica, motivacion)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.spatial.distance import cdist


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
    """Construye panel con SWITCHER y ALWAYS_IN."""
    outputs = base_dir / "outputs"

    t1 = pd.read_parquet(outputs / "panel_t1" / "panel_t1_muni.parquet")
    for col in ["anio", "pia", "pim", "devengado"]:
        if col in t1.columns:
            t1[col] = pd.to_numeric(t1[col], errors="coerce")

    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    panel = t1.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)
    panel = panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])].copy()

    panel["switcher"] = (panel["group_t1"] == "SWITCHER").astype(int)
    panel["post"] = (panel["anio"] == 2025).astype(int)
    panel["switcher_x_post"] = panel["switcher"] * panel["post"]

    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))

    if "departamento_code" in panel.columns:
        panel["departamento_code"] = panel["departamento_code"].fillna("UNK").astype(str)

    return panel


def get_baseline_characteristics(panel: pd.DataFrame) -> pd.DataFrame:
    """Extrae caracteristicas baseline (2024) por entidad."""
    # Usar 2024 como baseline (ultimo anio pre-tratamiento)
    baseline = panel[panel["anio"] == 2024][["sec_ejec", "group_t1", "switcher", "log_pia", "log_pim"]].copy()

    if "departamento_code" in panel.columns:
        dept = panel[panel["anio"] == 2024][["sec_ejec", "departamento_code"]].drop_duplicates()
        baseline = baseline.merge(dept, on="sec_ejec", how="left")

    baseline = baseline.drop_duplicates(subset=["sec_ejec"])
    return baseline


def estimate_propensity_score(baseline: pd.DataFrame) -> pd.DataFrame:
    """Estima P(SWITCHER=1 | X) con logit."""
    # Variables para el modelo
    X_vars = ["log_pia", "log_pim"]

    # Agregar dummies de region si hay suficientes
    if "departamento_code" in baseline.columns:
        dept_dummies = pd.get_dummies(baseline["departamento_code"], prefix="dept", drop_first=True)
        # Solo usar si no hay demasiadas columnas
        if dept_dummies.shape[1] < 20:
            baseline = pd.concat([baseline, dept_dummies], axis=1)
            X_vars = X_vars + list(dept_dummies.columns)

    # Filtrar NaN
    model_data = baseline[["sec_ejec", "switcher"] + X_vars].dropna()

    # Estimar logit
    X = sm.add_constant(model_data[X_vars])
    y = model_data["switcher"]

    try:
        logit = sm.Logit(y, X).fit(disp=0)
        model_data["pscore"] = logit.predict(X)
    except Exception as e:
        print(f"    [WARN] Logit fallo: {e}. Usando OLS.")
        ols = sm.OLS(y, X).fit()
        model_data["pscore"] = ols.predict(X).clip(0.01, 0.99)

    return model_data[["sec_ejec", "switcher", "pscore", "log_pia", "log_pim"]]


def nearest_neighbor_matching(pscore_df: pd.DataFrame, caliper: float = 0.1) -> pd.DataFrame:
    """Matching 1:1 nearest neighbor con caliper."""
    treated = pscore_df[pscore_df["switcher"] == 1].copy()
    control = pscore_df[pscore_df["switcher"] == 0].copy()

    if treated.empty or control.empty:
        return pd.DataFrame()

    # Calcular distancias
    treated_ps = treated["pscore"].values.reshape(-1, 1)
    control_ps = control["pscore"].values.reshape(-1, 1)
    distances = cdist(treated_ps, control_ps, metric="euclidean")

    # Matching 1:1 sin reemplazo
    matched_pairs = []
    control_used = set()

    for i, t_idx in enumerate(treated.index):
        # Encontrar control mas cercano no usado
        dists = distances[i, :]
        sorted_indices = np.argsort(dists)

        for j in sorted_indices:
            c_idx = control.index[j]
            if c_idx not in control_used and dists[j] <= caliper:
                matched_pairs.append({
                    "treated_sec_ejec": treated.loc[t_idx, "sec_ejec"],
                    "control_sec_ejec": control.loc[c_idx, "sec_ejec"],
                    "treated_pscore": treated.loc[t_idx, "pscore"],
                    "control_pscore": control.loc[c_idx, "pscore"],
                    "distance": dists[j],
                })
                control_used.add(c_idx)
                break

    return pd.DataFrame(matched_pairs)


def check_balance(baseline: pd.DataFrame, matched_pairs: pd.DataFrame) -> pd.DataFrame:
    """Verifica balance de covariables antes y despues del matching."""
    # Antes del matching
    treated_all = baseline[baseline["switcher"] == 1]
    control_all = baseline[baseline["switcher"] == 0]

    # Despues del matching
    matched_treated = baseline[baseline["sec_ejec"].isin(matched_pairs["treated_sec_ejec"])]
    matched_control = baseline[baseline["sec_ejec"].isin(matched_pairs["control_sec_ejec"])]

    balance = []
    for var in ["log_pia", "log_pim"]:
        # Antes
        mean_t_before = treated_all[var].mean()
        mean_c_before = control_all[var].mean()
        std_before = baseline[var].std()
        smd_before = (mean_t_before - mean_c_before) / std_before if std_before > 0 else 0

        # Despues
        mean_t_after = matched_treated[var].mean()
        mean_c_after = matched_control[var].mean()
        smd_after = (mean_t_after - mean_c_after) / std_before if std_before > 0 else 0

        balance.append({
            "variable": var,
            "mean_treated_before": mean_t_before,
            "mean_control_before": mean_c_before,
            "smd_before": smd_before,
            "mean_treated_after": mean_t_after,
            "mean_control_after": mean_c_after,
            "smd_after": smd_after,
            "reduction_pct": (1 - abs(smd_after) / abs(smd_before)) * 100 if smd_before != 0 else 0,
        })

    return pd.DataFrame(balance)


def estimate_did_matched(panel: pd.DataFrame, matched_pairs: pd.DataFrame) -> dict:
    """Estima DiD en la muestra emparejada."""
    # Filtrar panel a entidades matched
    matched_ues = set(matched_pairs["treated_sec_ejec"]) | set(matched_pairs["control_sec_ejec"])
    panel_matched = panel[panel["sec_ejec"].isin(matched_ues)].copy()

    # DiD manual
    always_pre = panel_matched[(panel_matched["switcher"] == 0) & (panel_matched["post"] == 0)]["cumple_v4"].mean()
    always_post = panel_matched[(panel_matched["switcher"] == 0) & (panel_matched["post"] == 1)]["cumple_v4"].mean()
    switch_pre = panel_matched[(panel_matched["switcher"] == 1) & (panel_matched["post"] == 0)]["cumple_v4"].mean()
    switch_post = panel_matched[(panel_matched["switcher"] == 1) & (panel_matched["post"] == 1)]["cumple_v4"].mean()

    did = (switch_post - switch_pre) - (always_post - always_pre)

    # Regresion DiD
    d = panel_matched[["cumple_v4", "switcher", "post", "switcher_x_post", "log_pia", "log_pim"]].dropna()
    X = sm.add_constant(d[["switcher", "post", "switcher_x_post", "log_pia", "log_pim"]])
    m = sm.OLS(d["cumple_v4"], X).fit(cov_type="HC1")

    return {
        "n_pairs": len(matched_pairs),
        "n_obs": len(d),
        "did_manual": did,
        "did_regression": float(m.params["switcher_x_post"]),
        "se_regression": float(m.bse["switcher_x_post"]),
        "pvalue": float(m.pvalues["switcher_x_post"]),
        "r2": float(m.rsquared),
        "control_pre": always_pre,
        "control_post": always_post,
        "treated_pre": switch_pre,
        "treated_post": switch_post,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DiD con Propensity Score Matching")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--caliper", type=float, default=0.1, help="Caliper para matching (default: 0.1)")
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("DiD CON PROPENSITY SCORE MATCHING (PSM-DiD)")
    print("=" * 70)

    # Construir panel
    print("\n[1] Construyendo panel...")
    panel = build_panel(base_dir)
    print(f"    Panel: {len(panel)} obs, {panel['sec_ejec'].nunique()} UEs")

    # Caracteristicas baseline
    print("\n[2] Extrayendo caracteristicas baseline (2024)...")
    baseline = get_baseline_characteristics(panel)
    n_switch = baseline["switcher"].sum()
    n_control = len(baseline) - n_switch
    print(f"    SWITCHER: {n_switch}, ALWAYS_IN (control): {n_control}")

    # Estimar propensity score
    print("\n[3] Estimando propensity score...")
    pscore_df = estimate_propensity_score(baseline)
    print(f"    P-score SWITCHER: mean={pscore_df[pscore_df['switcher']==1]['pscore'].mean():.4f}")
    print(f"    P-score CONTROL:  mean={pscore_df[pscore_df['switcher']==0]['pscore'].mean():.4f}")

    # Matching
    print(f"\n[4] Matching 1:1 nearest neighbor (caliper={args.caliper})...")
    matched_pairs = nearest_neighbor_matching(pscore_df, caliper=args.caliper)
    print(f"    Pares emparejados: {len(matched_pairs)} de {n_switch} tratados ({len(matched_pairs)/n_switch*100:.1f}%)")

    if matched_pairs.empty:
        print("    [ERROR] No se pudo emparejar ninguna entidad. Aumenta el caliper.")
        return

    # Balance
    print("\n[5] Verificando balance post-matching...")
    balance = check_balance(baseline, matched_pairs)
    for _, row in balance.iterrows():
        print(f"    {row['variable']}: SMD {row['smd_before']:.3f} -> {row['smd_after']:.3f} (reduccion: {row['reduction_pct']:.1f}%)")

    # DiD en muestra matched
    print("\n[6] Estimando DiD en muestra emparejada...")
    did_results = estimate_did_matched(panel, matched_pairs)
    print(f"    DiD manual: {did_results['did_manual']:.4f}")
    print(f"    DiD regresion: {did_results['did_regression']:.4f} (SE: {did_results['se_regression']:.4f})")

    # Guardar resultados
    matched_pairs.to_csv(out_dir / "matched_pairs.csv", index=False)
    pscore_df.to_csv(out_dir / "propensity_scores.csv", index=False)
    balance.to_csv(out_dir / "balance_check.csv", index=False)
    pd.DataFrame([did_results]).to_csv(out_dir / "did_psm_results.csv", index=False)

    # Generar markdown
    md = []
    md.append("# DiD con Propensity Score Matching (PSM-DiD)")
    md.append("")
    md.append("## 1. Objetivo")
    md.append("")
    md.append("Reducir sesgo por diferencias observables entre SWITCHER y ALWAYS_IN")
    md.append("emparejando entidades con caracteristicas similares antes del tratamiento.")
    md.append("")
    md.append("## 2. Procedimiento")
    md.append("")
    md.append("1. Estimar P(SWITCHER=1 | log_pia, log_pim) con logit")
    md.append("2. Matching 1:1 nearest neighbor con caliper")
    md.append("3. Verificar balance de covariables")
    md.append("4. Estimar DiD en muestra emparejada")
    md.append("")
    md.append("## 3. Propensity Score")
    md.append("")
    md.append("| Grupo | n | P-score medio |")
    md.append("|-------|---|---------------|")
    md.append(f"| SWITCHER | {n_switch} | {pscore_df[pscore_df['switcher']==1]['pscore'].mean():.4f} |")
    md.append(f"| ALWAYS_IN | {n_control} | {pscore_df[pscore_df['switcher']==0]['pscore'].mean():.4f} |")
    md.append("")
    md.append(f"## 4. Matching (caliper={args.caliper})")
    md.append("")
    md.append(f"- Pares emparejados: **{len(matched_pairs)}** de {n_switch} tratados ({len(matched_pairs)/n_switch*100:.1f}%)")
    md.append(f"- Distancia media: {matched_pairs['distance'].mean():.4f}")
    md.append("")
    md.append("## 5. Balance de covariables")
    md.append("")
    md.append(df_to_md(balance.round(4)))
    md.append("")
    md.append("Nota: SMD (Standardized Mean Difference). |SMD| < 0.1 indica buen balance.")
    md.append("")
    md.append("## 6. Resultados DiD (muestra emparejada)")
    md.append("")
    md.append("| Grupo | Pre (2022-2024) | Post (2025) | Diferencia |")
    md.append("|-------|-----------------|-------------|------------|")
    md.append(f"| ALWAYS_IN (matched) | {did_results['control_pre']:.4f} | {did_results['control_post']:.4f} | {did_results['control_post']-did_results['control_pre']:.4f} |")
    md.append(f"| SWITCHER (matched) | {did_results['treated_pre']:.4f} | {did_results['treated_post']:.4f} | {did_results['treated_post']-did_results['treated_pre']:.4f} |")
    md.append(f"| **DiD** | | | **{did_results['did_manual']:.4f}** |")
    md.append("")
    md.append("### Regresion DiD (con controles)")
    md.append("")
    md.append(f"- delta (ATT) = **{did_results['did_regression']:.4f}** (SE: {did_results['se_regression']:.4f})")
    md.append(f"- p-value = {did_results['pvalue']:.4f}")
    md.append(f"- n = {did_results['n_obs']}, R2 = {did_results['r2']:.4f}")
    md.append("")
    md.append("## 7. Interpretacion")
    md.append("")
    md.append(f"- En la muestra emparejada, SWITCHER salto {did_results['did_regression']*100:.2f} pp")
    md.append(f"  {'MAS' if did_results['did_regression'] > 0 else 'MENOS'} que ALWAYS_IN comparable.")
    md.append("- El matching reduce sesgo por diferencias en PIA/PIM pero:")
    md.append("  - No corrige seleccion en no-observables")
    md.append("  - Pre-trends aun pueden diferir")
    md.append("")
    md.append("## 8. Limitaciones")
    md.append("")
    md.append("- Solo corrige por diferencias OBSERVABLES (PIA, PIM)")
    md.append("- No corrige por capacidad tecnica, motivacion, etc.")
    md.append("- El supuesto CIA (Conditional Independence) puede no cumplirse")

    (out_dir / "did_psm.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n[OK] Resultados guardados en:", out_dir)


if __name__ == "__main__":
    main()
