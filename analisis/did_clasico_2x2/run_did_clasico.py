"""
DiD Clasico 2x2: SWITCHER vs ALWAYS_IN, Pre vs Post.

Estima el efecto diferencial de ser SWITCHER en 2025 respecto a ALWAYS_IN.

Especificacion:
  cumple_v4_it = alpha + beta1*SWITCHER + beta2*POST + delta*(SWITCHER x POST) + X'gamma + epsilon

Donde:
  - SWITCHER = 1 si entidad paso de SIGA=NO a SIGA=SI en 2025
  - POST = 1 si anio = 2025
  - delta = efecto DiD (parametro de interes)

Interpretacion:
  - delta > 0: SWITCHER salto MAS que ALWAYS_IN
  - delta < 0: SWITCHER salto MENOS que ALWAYS_IN
  - delta ~ 0: ambos grupos saltaron igual

Limitaciones:
  - Pre-trends no paralelos (SWITCHER ya estaba por debajo)
  - Interpretacion descriptiva, no causal estricta
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS


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

    # Panel T1 (tiene grupos y presupuesto)
    t1 = pd.read_parquet(outputs / "panel_t1" / "panel_t1_muni.parquet")
    for col in ["anio", "pia", "pim", "devengado"]:
        if col in t1.columns:
            t1[col] = pd.to_numeric(t1[col], errors="coerce")

    # CMN cumple_v4
    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    # Merge
    panel = t1.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)

    # Filtrar solo SWITCHER y ALWAYS_IN
    panel = panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])].copy()

    # Crear variables DiD
    panel["switcher"] = (panel["group_t1"] == "SWITCHER").astype(int)
    panel["post"] = (panel["anio"] == 2025).astype(int)
    panel["switcher_x_post"] = panel["switcher"] * panel["post"]

    # Controles
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))

    return panel


def estimate_did_ols(panel: pd.DataFrame) -> dict:
    """DiD con OLS pooled (sin efectos fijos)."""
    d = panel[["cumple_v4", "switcher", "post", "switcher_x_post", "log_pia", "log_pim"]].dropna()

    # Sin controles
    X1 = sm.add_constant(d[["switcher", "post", "switcher_x_post"]])
    m1 = sm.OLS(d["cumple_v4"], X1).fit(cov_type="HC1")

    # Con controles
    X2 = sm.add_constant(d[["switcher", "post", "switcher_x_post", "log_pia", "log_pim"]])
    m2 = sm.OLS(d["cumple_v4"], X2).fit(cov_type="HC1")

    return {
        "ols_sin_controles": {
            "n": int(m1.nobs),
            "r2": float(m1.rsquared),
            "delta": float(m1.params["switcher_x_post"]),
            "se_delta": float(m1.bse["switcher_x_post"]),
            "pvalue_delta": float(m1.pvalues["switcher_x_post"]),
            "beta_switcher": float(m1.params["switcher"]),
            "beta_post": float(m1.params["post"]),
        },
        "ols_con_controles": {
            "n": int(m2.nobs),
            "r2": float(m2.rsquared),
            "delta": float(m2.params["switcher_x_post"]),
            "se_delta": float(m2.bse["switcher_x_post"]),
            "pvalue_delta": float(m2.pvalues["switcher_x_post"]),
            "beta_switcher": float(m2.params["switcher"]),
            "beta_post": float(m2.params["post"]),
        },
    }


def estimate_did_fe(panel: pd.DataFrame) -> dict:
    """DiD con efectos fijos de entidad (absorbe switcher)."""
    d = panel[["sec_ejec", "anio", "cumple_v4", "post", "switcher_x_post", "log_pia", "log_pim"]].dropna()
    d = d.set_index(["sec_ejec", "anio"])

    # Solo post y switcher_x_post (switcher absorbido por FE entidad)
    # Sin controles
    m1 = PanelOLS(d["cumple_v4"], d[["post", "switcher_x_post"]], entity_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )

    # Con controles
    m2 = PanelOLS(d["cumple_v4"], d[["post", "switcher_x_post", "log_pia", "log_pim"]], entity_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )

    return {
        "fe_sin_controles": {
            "n": int(m1.nobs),
            "r2_within": float(m1.rsquared_within),
            "delta": float(m1.params["switcher_x_post"]),
            "se_delta": float(m1.std_errors["switcher_x_post"]),
            "beta_post": float(m1.params["post"]),
        },
        "fe_con_controles": {
            "n": int(m2.nobs),
            "r2_within": float(m2.rsquared_within),
            "delta": float(m2.params["switcher_x_post"]),
            "se_delta": float(m2.std_errors["switcher_x_post"]),
            "beta_post": float(m2.params["post"]),
        },
    }


def compute_did_manual(panel: pd.DataFrame) -> dict:
    """Calculo manual del DiD 2x2."""
    # Tasas por grupo y periodo
    always_pre = panel[(panel["group_t1"] == "ALWAYS_IN") & (panel["anio"] <= 2024)]["cumple_v4"].mean()
    always_post = panel[(panel["group_t1"] == "ALWAYS_IN") & (panel["anio"] == 2025)]["cumple_v4"].mean()
    switch_pre = panel[(panel["group_t1"] == "SWITCHER") & (panel["anio"] <= 2024)]["cumple_v4"].mean()
    switch_post = panel[(panel["group_t1"] == "SWITCHER") & (panel["anio"] == 2025)]["cumple_v4"].mean()

    # DiD manual
    diff_always = always_post - always_pre
    diff_switch = switch_post - switch_pre
    did = diff_switch - diff_always

    # Conteos
    n_always = panel[panel["group_t1"] == "ALWAYS_IN"]["sec_ejec"].nunique()
    n_switch = panel[panel["group_t1"] == "SWITCHER"]["sec_ejec"].nunique()

    return {
        "always_in_pre": always_pre,
        "always_in_post": always_post,
        "always_in_diff": diff_always,
        "switcher_pre": switch_pre,
        "switcher_post": switch_post,
        "switcher_diff": diff_switch,
        "did_manual": did,
        "n_always_in": n_always,
        "n_switcher": n_switch,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DiD Clasico 2x2: SWITCHER vs ALWAYS_IN")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("DiD CLASICO 2x2: SWITCHER vs ALWAYS_IN")
    print("=" * 70)

    # Construir panel
    print("\n[1] Construyendo panel...")
    panel = build_panel(base_dir)
    print(f"    Panel: {len(panel)} obs, {panel['sec_ejec'].nunique()} UEs")
    print(f"    ALWAYS_IN: {(panel['group_t1']=='ALWAYS_IN').sum()} obs")
    print(f"    SWITCHER: {(panel['group_t1']=='SWITCHER').sum()} obs")

    # DiD manual
    print("\n[2] Calculo manual DiD 2x2...")
    did_manual = compute_did_manual(panel)
    print(f"    ALWAYS_IN: {did_manual['always_in_pre']:.4f} -> {did_manual['always_in_post']:.4f} (diff: {did_manual['always_in_diff']:.4f})")
    print(f"    SWITCHER:  {did_manual['switcher_pre']:.4f} -> {did_manual['switcher_post']:.4f} (diff: {did_manual['switcher_diff']:.4f})")
    print(f"    DiD = {did_manual['did_manual']:.4f} ({did_manual['did_manual']*100:.2f} pp)")

    # OLS
    print("\n[3] Estimacion OLS pooled...")
    ols_results = estimate_did_ols(panel)
    print(f"    Sin controles: delta = {ols_results['ols_sin_controles']['delta']:.4f} (SE: {ols_results['ols_sin_controles']['se_delta']:.4f})")
    print(f"    Con controles: delta = {ols_results['ols_con_controles']['delta']:.4f} (SE: {ols_results['ols_con_controles']['se_delta']:.4f})")

    # FE
    print("\n[4] Estimacion con FE entidad...")
    fe_results = estimate_did_fe(panel)
    print(f"    Sin controles: delta = {fe_results['fe_sin_controles']['delta']:.4f} (SE: {fe_results['fe_sin_controles']['se_delta']:.4f})")
    print(f"    Con controles: delta = {fe_results['fe_con_controles']['delta']:.4f} (SE: {fe_results['fe_con_controles']['se_delta']:.4f})")

    # Guardar resultados
    pd.DataFrame([did_manual]).to_csv(out_dir / "did_manual.csv", index=False)
    pd.DataFrame([ols_results["ols_sin_controles"]]).to_csv(out_dir / "ols_sin_controles.csv", index=False)
    pd.DataFrame([ols_results["ols_con_controles"]]).to_csv(out_dir / "ols_con_controles.csv", index=False)
    pd.DataFrame([fe_results["fe_sin_controles"]]).to_csv(out_dir / "fe_sin_controles.csv", index=False)
    pd.DataFrame([fe_results["fe_con_controles"]]).to_csv(out_dir / "fe_con_controles.csv", index=False)

    # Generar markdown
    md = []
    md.append("# DiD Clasico 2x2: SWITCHER vs ALWAYS_IN")
    md.append("")
    md.append("## 1. Especificacion")
    md.append("")
    md.append("```")
    md.append("cumple_v4_it = alpha + beta1*SWITCHER + beta2*POST + delta*(SWITCHER x POST) + X'gamma + epsilon")
    md.append("```")
    md.append("")
    md.append("Donde:")
    md.append("- SWITCHER = 1 si entidad paso de SIGA=NO a SIGA=SI en 2025")
    md.append("- POST = 1 si anio = 2025")
    md.append("- delta = efecto DiD (parametro de interes)")
    md.append("")
    md.append("## 2. Calculo manual DiD 2x2")
    md.append("")
    md.append("| Grupo | Pre (2022-2024) | Post (2025) | Diferencia |")
    md.append("|-------|-----------------|-------------|------------|")
    md.append(f"| ALWAYS_IN (n={did_manual['n_always_in']}) | {did_manual['always_in_pre']:.4f} | {did_manual['always_in_post']:.4f} | {did_manual['always_in_diff']:.4f} |")
    md.append(f"| SWITCHER (n={did_manual['n_switcher']}) | {did_manual['switcher_pre']:.4f} | {did_manual['switcher_post']:.4f} | {did_manual['switcher_diff']:.4f} |")
    md.append(f"| **DiD** | | | **{did_manual['did_manual']:.4f}** |")
    md.append("")
    md.append(f"**Interpretacion:** SWITCHER salto {did_manual['did_manual']*100:.2f} pp {'MAS' if did_manual['did_manual'] > 0 else 'MENOS'} que ALWAYS_IN.")
    md.append("")
    md.append("## 3. Estimacion OLS pooled")
    md.append("")
    md.append("| Especificacion | n | R2 | delta | SE | p-value |")
    md.append("|----------------|---|-----|-------|-----|---------|")
    r1 = ols_results["ols_sin_controles"]
    r2 = ols_results["ols_con_controles"]
    md.append(f"| Sin controles | {r1['n']} | {r1['r2']:.4f} | {r1['delta']:.4f} | {r1['se_delta']:.4f} | {r1['pvalue_delta']:.4f} |")
    md.append(f"| Con controles (log_pia, log_pim) | {r2['n']} | {r2['r2']:.4f} | {r2['delta']:.4f} | {r2['se_delta']:.4f} | {r2['pvalue_delta']:.4f} |")
    md.append("")
    md.append("## 4. Estimacion con FE entidad")
    md.append("")
    md.append("Nota: SWITCHER es absorbido por FE entidad (time-invariant).")
    md.append("")
    md.append("| Especificacion | n | R2_within | delta | SE |")
    md.append("|----------------|---|-----------|-------|-----|")
    f1 = fe_results["fe_sin_controles"]
    f2 = fe_results["fe_con_controles"]
    md.append(f"| FE entidad, sin controles | {f1['n']} | {f1['r2_within']:.4f} | {f1['delta']:.4f} | {f1['se_delta']:.4f} |")
    md.append(f"| FE entidad, con controles | {f2['n']} | {f2['r2_within']:.4f} | {f2['delta']:.4f} | {f2['se_delta']:.4f} |")
    md.append("")
    md.append("## 5. Interpretacion")
    md.append("")
    md.append(f"- El coeficiente delta = {fe_results['fe_con_controles']['delta']:.4f} indica que SWITCHER salto")
    md.append(f"  {abs(fe_results['fe_con_controles']['delta'])*100:.2f} pp {'MAS' if fe_results['fe_con_controles']['delta'] > 0 else 'MENOS'} que ALWAYS_IN en 2025.")
    md.append("- Esto es DESCRIPTIVO, no causal, porque:")
    md.append("  1. Pre-trends no paralelos (SWITCHER ya estaba por debajo en 2022-2024)")
    md.append("  2. La asignacion a SWITCHER no es aleatoria")
    md.append("")
    md.append("## 6. Limitaciones")
    md.append("")
    md.append("- SWITCHER tenia cumple_v4 cercano a 0 en pre-periodo (casi sin variacion)")
    md.append("- ALWAYS_IN ya tenia SIGA implementado; no es un 'control puro'")
    md.append("- El supuesto de tendencias paralelas NO se cumple")

    (out_dir / "did_clasico_2x2.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n[OK] Resultados guardados en:", out_dir)


if __name__ == "__main__":
    main()
