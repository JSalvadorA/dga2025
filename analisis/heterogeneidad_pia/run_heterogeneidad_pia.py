"""
Heterogeneidad por quintiles de PIA/PIM.

Responde: la reduccion de friccion administrativa (salto en cumple_v4)
fue uniforme o concentrada en entidades de cierto tamano presupuestal?

Approach:
  - Dentro de ALWAYS_IN, interactuar post_2025 con quintil_PIA.
  - Estimar cumple_v4 = alpha_i + gamma*post_2025 + sum(delta_q * post_2025 * Q_q) + controls + epsilon
  - Tambien: estimacion por quintil separado (robustez).

Viabilidad: MEDIA como complemento (segun rese2.md).
Requiere supuestos fuertes de ignorabilidad; reportar como exploratorio.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from linearmodels.panel.utility import AbsorbingEffectError


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
    """Panel ALWAYS_IN con cumple_v4 y quintiles de PIA."""
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

    # Only ALWAYS_IN
    panel = panel[panel["group_t1"] == "ALWAYS_IN"].copy()

    # Quintile assignment based on PIA (time-invariant: use 2024 PIA for stability)
    pia_2024 = panel[panel["anio"] == 2024][["sec_ejec", "pia"]].dropna()
    pia_2024 = pia_2024.rename(columns={"pia": "pia_2024"})
    pia_2024["quintil_pia"] = pd.qcut(
        pia_2024["pia_2024"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"]
    )
    panel = panel.merge(pia_2024[["sec_ejec", "pia_2024", "quintil_pia"]], on="sec_ejec", how="left")

    # Also PIM quintiles
    pim_2024 = panel[panel["anio"] == 2024][["sec_ejec", "pim"]].drop_duplicates()
    pim_2024 = pim_2024.dropna(subset=["pim"])
    pim_2024 = pim_2024.rename(columns={"pim": "pim_2024"})
    pim_2024["quintil_pim"] = pd.qcut(
        pim_2024["pim_2024"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"]
    )
    panel = panel.merge(pim_2024[["sec_ejec", "pim_2024", "quintil_pim"]], on="sec_ejec", how="left")

    # Post indicator
    panel["post_2025"] = (panel["anio"] == 2025).astype(int)

    # Log controls
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))

    # Region-year
    if "departamento_code" in panel.columns:
        panel["departamento_code"] = panel["departamento_code"].fillna("UNK").astype(str)
        panel["region_year"] = panel["departamento_code"] + "_" + panel["anio"].astype(int).astype(str)
        panel["region_year"] = panel["region_year"].astype("category")

    return panel


def estimate_by_quintile(panel: pd.DataFrame, quintile_col: str) -> pd.DataFrame:
    """Estimate post_2025 effect on cumple_v4 separately by quintile."""
    results = []

    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        sub = panel[panel[quintile_col] == q].copy()
        if sub.empty or sub["post_2025"].nunique() < 2:
            continue

        d = sub[["sec_ejec", "anio", "cumple_v4", "post_2025"]].dropna()
        d = d.set_index(["sec_ejec", "anio"])

        model = PanelOLS(
            d["cumple_v4"], d[["post_2025"]],
            entity_effects=True, time_effects=False,
        )
        res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

        # Also compute raw means
        raw_pre = sub[sub["anio"] <= 2024]["cumple_v4"].mean()
        raw_post = sub[sub["anio"] == 2025]["cumple_v4"].mean()

        results.append({
            "quintile": q,
            "n_entities": sub["sec_ejec"].nunique(),
            "n_obs": int(res.nobs),
            "beta_post_2025": float(res.params["post_2025"]),
            "se_post_2025": float(res.std_errors["post_2025"]),
            "r2_within": float(res.rsquared_within),
            "raw_pre_mean": raw_pre,
            "raw_post_mean": raw_post,
            "raw_delta": raw_post - raw_pre,
        })

    return pd.DataFrame(results)


def estimate_interactions(panel: pd.DataFrame, quintile_col: str) -> dict:
    """
    Single regression with interactions: post_2025 * quintile dummies.
    Base quintile: Q1 (smallest).
    """
    sub = panel.dropna(subset=[quintile_col, "cumple_v4", "post_2025"]).copy()

    # Create interaction dummies (base=Q1)
    for q in ["Q2", "Q3", "Q4", "Q5"]:
        sub[f"post_x_{q}"] = ((sub[quintile_col] == q) & (sub["post_2025"] == 1)).astype(int)

    x_cols = ["post_2025", "post_x_Q2", "post_x_Q3", "post_x_Q4", "post_x_Q5"]

    d = sub[["sec_ejec", "anio", "cumple_v4"] + x_cols].dropna()
    d = d.set_index(["sec_ejec", "anio"])

    model = PanelOLS(
        d["cumple_v4"], d[x_cols],
        entity_effects=True, time_effects=False,
    )
    res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

    out = {"n": int(res.nobs), "r2_within": float(res.rsquared_within)}
    for col in x_cols:
        out[f"beta_{col}"] = float(res.params[col])
        out[f"se_{col}"] = float(res.std_errors[col])
    return out


def estimate_interactions_with_controls(panel: pd.DataFrame, quintile_col: str) -> dict:
    """Same as above but with log_pia, log_pim and region-year FE."""
    sub = panel.dropna(subset=[quintile_col, "cumple_v4", "post_2025", "log_pia", "log_pim"]).copy()

    for q in ["Q2", "Q3", "Q4", "Q5"]:
        sub[f"post_x_{q}"] = ((sub[quintile_col] == q) & (sub["post_2025"] == 1)).astype(int)

    x_cols = ["post_2025", "post_x_Q2", "post_x_Q3", "post_x_Q4", "post_x_Q5", "log_pia", "log_pim"]

    if "region_year" not in sub.columns:
        # Fallback: entity + time FE
        d = sub[["sec_ejec", "anio", "cumple_v4"] + x_cols].dropna()
        d = d.set_index(["sec_ejec", "anio"])
        model = PanelOLS(d["cumple_v4"], d[x_cols], entity_effects=True, time_effects=False)
        res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    else:
        needed = ["sec_ejec", "anio", "region_year", "cumple_v4"] + x_cols
        d = sub[needed].dropna().copy()
        other = d[["region_year"]].copy()
        d = d.set_index(["sec_ejec", "anio"])
        other = other.set_index(d.index)
        model = PanelOLS(
            d["cumple_v4"], d[x_cols],
            entity_effects=True, time_effects=False, other_effects=other,
        )
        try:
            res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
        except AbsorbingEffectError:
            # Fall back to entity FE only if post_2025 is absorbed by region-year
            d = sub[["sec_ejec", "anio", "cumple_v4"] + x_cols].dropna()
            d = d.set_index(["sec_ejec", "anio"])
            model = PanelOLS(d["cumple_v4"], d[x_cols], entity_effects=True, time_effects=False)
            res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
            out = {"n": int(res.nobs), "r2_within": float(res.rsquared_within), "region_year_used": 0}
            for col in x_cols:
                out[f"beta_{col}"] = float(res.params[col])
                out[f"se_{col}"] = float(res.std_errors[col])
            return out

    out = {"n": int(res.nobs), "r2_within": float(res.rsquared_within), "region_year_used": 1}
    for col in x_cols:
        out[f"beta_{col}"] = float(res.params[col])
        out[f"se_{col}"] = float(res.std_errors[col])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Heterogeneidad por quintiles PIA/PIM.")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Construyendo panel ALWAYS_IN con quintiles...")
    panel = build_panel(base_dir)
    n_with_q = panel["quintil_pia"].notna().sum()
    print(f"  Panel: {len(panel)} rows, {panel['sec_ejec'].nunique()} UEs, {n_with_q} con quintil asignado")

    # 1) By-quintile estimates (PIA)
    print("1) Estimacion por quintil PIA...")
    by_q_pia = estimate_by_quintile(panel, "quintil_pia")
    by_q_pia.to_csv(out_dir / "by_quintile_pia.csv", index=False)
    print(f"  [OK] {len(by_q_pia)} quintiles")

    # 2) By-quintile estimates (PIM)
    print("2) Estimacion por quintil PIM...")
    by_q_pim = estimate_by_quintile(panel, "quintil_pim")
    by_q_pim.to_csv(out_dir / "by_quintile_pim.csv", index=False)
    print(f"  [OK] {len(by_q_pim)} quintiles")

    # 3) Interaction model (PIA, sin controles)
    print("3) Modelo con interacciones PIA (sin controles)...")
    inter_pia = estimate_interactions(panel, "quintil_pia")
    pd.DataFrame([inter_pia]).to_csv(out_dir / "interactions_pia.csv", index=False)

    # 4) Interaction model (PIA, con controles + region-year)
    print("4) Modelo con interacciones PIA (con controles)...")
    inter_pia_ctrl = estimate_interactions_with_controls(panel, "quintil_pia")
    pd.DataFrame([inter_pia_ctrl]).to_csv(out_dir / "interactions_pia_controls.csv", index=False)

    # 5) Quintile summary stats
    print("5) Estadisticas descriptivas por quintil...")
    desc = panel.groupby("quintil_pia").agg(
        n_entities=("sec_ejec", "nunique"),
        pia_mean=("pia_2024", "mean"),
        pia_median=("pia_2024", "median"),
        pia_min=("pia_2024", "min"),
        pia_max=("pia_2024", "max"),
        cumple_v4_mean=("cumple_v4", "mean"),
    ).reset_index()
    desc.to_csv(out_dir / "quintile_descriptives.csv", index=False)

    # Generate markdown report
    md = []
    md.append("# Heterogeneidad por quintiles PIA/PIM")
    md.append("")
    md.append("Outcome: cumple_v4. Muestra: ALWAYS_IN.")
    md.append("Quintiles basados en PIA 2024 (time-invariant).")
    md.append("")
    md.append("## 1. Estadisticas por quintil PIA")
    md.append(df_to_md(desc.round(2)))
    md.append("")
    md.append("## 2. Efecto post_2025 por quintil PIA (separado)")
    md.append("")
    md.append("FE: entidad. SE: cluster entity+time.")
    md.append("")
    md.append(df_to_md(by_q_pia.round(4)))
    md.append("")
    md.append("## 3. Efecto post_2025 por quintil PIM (separado)")
    md.append("")
    md.append(df_to_md(by_q_pim.round(4)))
    md.append("")
    md.append("## 4. Modelo con interacciones (PIA)")
    md.append("")
    md.append("Spec: cumple_v4 ~ post_2025 + post_2025*Q2 + ... + post_2025*Q5 | FE_entity")
    md.append("Base: Q1 (entidades mas pequenas).")
    md.append("Interpretacion: post_2025 = efecto para Q1; post_x_Qk = diferencial de Qk vs Q1.")
    md.append("")
    md.append(f"n = {inter_pia['n']}, R2_within = {inter_pia['r2_within']:.4f}")
    md.append("")
    md.append("| Variable | beta | se |")
    md.append("|----------|------|-----|")
    for var in ["post_2025", "post_x_Q2", "post_x_Q3", "post_x_Q4", "post_x_Q5"]:
        md.append(f"| {var} | {inter_pia[f'beta_{var}']:.4f} | {inter_pia[f'se_{var}']:.4f} |")
    md.append("")
    md.append("## 5. Modelo con interacciones + controles (PIA)")
    md.append("")
    md.append("Spec: cumple_v4 ~ post_2025 + post_2025*Qk + log_pia + log_pim | FE_entity + region_year")
    md.append("")
    if "region_year_used" in inter_pia_ctrl and inter_pia_ctrl["region_year_used"] == 0:
        md.append("Nota: region_year absorbio post_2025; se uso FE entidad sin region_year en esta especificacion.")
    md.append("")
    md.append(f"n = {inter_pia_ctrl['n']}, R2_within = {inter_pia_ctrl['r2_within']:.4f}")
    md.append("")
    md.append("| Variable | beta | se |")
    md.append("|----------|------|-----|")
    for var in ["post_2025", "post_x_Q2", "post_x_Q3", "post_x_Q4", "post_x_Q5", "log_pia", "log_pim"]:
        md.append(f"| {var} | {inter_pia_ctrl[f'beta_{var}']:.4f} | {inter_pia_ctrl[f'se_{var}']:.4f} |")
    md.append("")
    md.append("## Interpretacion")
    md.append("")
    md.append("- Si post_x_Qk > 0: entidades del quintil k saltaron MAS que Q1.")
    md.append("- Si post_x_Qk ~ 0 para todo k: el salto fue uniforme (independiente del tamano).")
    md.append("- Patron monotono (creciente o decreciente): efecto dosis-respuesta por tamano.")
    md.append("- ADVERTENCIA: interpretacion exploratoria, no causal estricta.")

    (out_dir / "heterogeneidad_pia.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("[OK] heterogeneidad_pia.md")


if __name__ == "__main__":
    main()
