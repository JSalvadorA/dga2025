"""
Event Study con outcome = cumple_v4 (binario).

Parte A: Descriptivo puro (year dummies en ALWAYS_IN).
  - Responde: hubo salto abrupto en cumple_v4 en 2025?
  - No identifica causalidad; documenta la serie temporal.

Parte B: Contraste SWITCHER vs ALWAYS_IN (t1_post con Y=cumple_v4).
  - Responde: los SWITCHER saltaron mas que ALWAYS_IN?
  - Descriptivo comparativo; pre-trends de T1 fallan para ejecucion,
    se verifica si tambien fallan para cumple_v4.

Especificaciones:
  - FE: entidad (+ region-anio donde corresponde).
  - Controles: log(PIA), log(PIM).
  - SE: clustered por entidad + anio.
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


def prepare_controls(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["log_pia"] = np.log1p(d["pia"].clip(lower=0))
    d["log_pim"] = np.log1p(d["pim"].clip(lower=0))
    d["departamento_code"] = d["departamento_code"].fillna("UNK").astype(str)
    d["region_year"] = d["departamento_code"] + "_" + d["anio"].astype(int).astype(str)
    d["region_year"] = d["region_year"].astype("category")
    return d


def fit_panel_region_year(df: pd.DataFrame, y: str, x_cols: list[str]) -> dict:
    """PanelOLS con FE entidad + other_effects=region_year, cluster entity+time."""
    needed = ["sec_ejec", "anio", "region_year", y] + x_cols
    d = df[needed].dropna().copy()
    if d.empty or d[y].nunique() < 2:
        return {}
    other = d[["region_year"]].copy()
    d = d.set_index(["sec_ejec", "anio"])
    other = other.set_index(d.index)
    model = PanelOLS(
        d[y], d[x_cols],
        entity_effects=True,
        time_effects=False,
        other_effects=other,
    )
    try:
        res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    except AbsorbingEffectError:
        return {}
    out = {"n": int(res.nobs), "r2_within": float(res.rsquared_within)}
    for col in x_cols:
        out[f"beta_{col}"] = float(res.params[col])
        out[f"se_{col}"] = float(res.std_errors[col])
    return out


def fit_panel_entity_time(df: pd.DataFrame, y: str, x_cols: list[str]) -> dict:
    """PanelOLS con FE entidad + FE anio, cluster entity+time."""
    needed = ["sec_ejec", "anio", y] + x_cols
    d = df[needed].dropna().copy()
    if d.empty or d[y].nunique() < 2:
        return {}
    d = d.set_index(["sec_ejec", "anio"])
    model = PanelOLS(
        d[y], d[x_cols],
        entity_effects=True,
        time_effects=True,
    )
    res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    out = {"n": int(res.nobs), "r2_within": float(res.rsquared_within)}
    for col in x_cols:
        out[f"beta_{col}"] = float(res.params[col])
        out[f"se_{col}"] = float(res.std_errors[col])
    return out


def build_panel(base_dir: Path) -> pd.DataFrame:
    """Merge panel_t1 con cumple_v4 de panel_t2 o cmn_cumple_v4."""
    outputs = base_dir / "outputs"

    t1 = pd.read_parquet(outputs / "panel_t1" / "panel_t1_muni.parquet")
    for col in ["anio", "pia", "pim", "t1_switcher"]:
        t1[col] = pd.to_numeric(t1[col], errors="coerce")

    # cumple_v4 from cmn data
    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    panel = t1.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    # Entities without CMN records: cumple_v4 = 0 (didn't program)
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)

    return panel


def part_a_descriptive(panel: pd.DataFrame) -> pd.DataFrame:
    """Year dummies (base=2022) para ALWAYS_IN, con y sin controles."""
    always = panel[panel["group_t1"] == "ALWAYS_IN"].copy()

    # Year dummies (base=2022)
    always["d_2023"] = (always["anio"] == 2023).astype(int)
    always["d_2024"] = (always["anio"] == 2024).astype(int)
    always["d_2025"] = (always["anio"] == 2025).astype(int)

    always = prepare_controls(always)

    results = []

    # A1: Solo year dummies, FE entidad
    x_a1 = ["d_2023", "d_2024", "d_2025"]
    res_a1 = fit_panel_entity_time(always, "cumple_v4", x_a1)
    # Note: with entity+time FE, year dummies are collinear with time FE.
    # So we use entity FE only (no time FE) for this specification.
    d = always[["sec_ejec", "anio", "cumple_v4"] + x_a1].dropna().copy()
    d = d.set_index(["sec_ejec", "anio"])
    model = PanelOLS(d["cumple_v4"], d[x_a1], entity_effects=True, time_effects=False)
    res = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    res_a1 = {"spec": "A1_year_dummies_FE_entity", "n": int(res.nobs), "r2_within": float(res.rsquared_within)}
    for col in x_a1:
        res_a1[f"beta_{col}"] = float(res.params[col])
        res_a1[f"se_{col}"] = float(res.std_errors[col])
    results.append(res_a1)

    # A2: Year dummies + controles (log_pia, log_pim), FE entidad
    x_a2 = ["d_2023", "d_2024", "d_2025", "log_pia", "log_pim"]
    d2 = always[["sec_ejec", "anio", "cumple_v4"] + x_a2].dropna().copy()
    d2 = d2.set_index(["sec_ejec", "anio"])
    model2 = PanelOLS(d2["cumple_v4"], d2[x_a2], entity_effects=True, time_effects=False)
    res2 = model2.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    res_a2 = {"spec": "A2_year_dummies_controls_FE_entity", "n": int(res2.nobs), "r2_within": float(res2.rsquared_within)}
    for col in x_a2:
        res_a2[f"beta_{col}"] = float(res2.params[col])
        res_a2[f"se_{col}"] = float(res2.std_errors[col])
    results.append(res_a2)

    # A3: Year dummies + controles + region-year FE (collinear with year dummies)
    # Skip if absorbed to avoid invalid estimation.
    x_a3 = ["d_2023", "d_2024", "d_2025", "log_pia", "log_pim"]
    res_a3_raw = fit_panel_region_year(always, "cumple_v4", x_a3)
    if res_a3_raw:
        res_a3_raw["spec"] = "A3_year_dummies_controls_FE_region_year"
        results.append(res_a3_raw)

    return pd.DataFrame(results)


def part_b_contrast(panel: pd.DataFrame) -> pd.DataFrame:
    """SWITCHER vs ALWAYS_IN con event-study en cumple_v4."""
    # Only ALWAYS_IN and SWITCHER
    sub = panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])].copy()

    sub["switcher_2023"] = ((sub["t1_switcher"] == 1) & (sub["anio"] == 2023)).astype(int)
    sub["switcher_2024"] = ((sub["t1_switcher"] == 1) & (sub["anio"] == 2024)).astype(int)
    sub["switcher_2025"] = ((sub["t1_switcher"] == 1) & (sub["anio"] == 2025)).astype(int)

    sub = prepare_controls(sub)

    results = []

    # B1: Sin controles, FE entidad + anio
    x_b1 = ["switcher_2023", "switcher_2024", "switcher_2025"]
    res_b1 = fit_panel_entity_time(sub, "cumple_v4", x_b1)
    if res_b1:
        res_b1["spec"] = "B1_contrast_FE_entity_time"
        results.append(res_b1)

    # B2: Con controles + region-year
    x_b2 = ["switcher_2023", "switcher_2024", "switcher_2025", "log_pia", "log_pim"]
    res_b2 = fit_panel_region_year(sub, "cumple_v4", x_b2)
    if res_b2:
        res_b2["spec"] = "B2_contrast_controls_FE_region_year"
        results.append(res_b2)

    # B3: TWFE simple (t1_post), FE entidad + anio
    x_b3 = ["t1_post"]
    # Need t1_post in sub
    sub["post_2025"] = (sub["anio"] == 2025).astype(int)
    sub["t1_post"] = (sub["t1_switcher"] * sub["post_2025"]).astype(int)
    res_b3 = fit_panel_entity_time(sub, "cumple_v4", x_b3)
    if res_b3:
        res_b3["spec"] = "B3_twfe_t1_post_FE_entity_time"
        results.append(res_b3)

    return pd.DataFrame(results)


def descriptive_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """Rates by group and year for context."""
    groups = panel.groupby(["anio", "group_t1"]).agg(
        n=("cumple_v4", "count"),
        cumple=("cumple_v4", "sum"),
    ).reset_index()
    groups["rate"] = groups["cumple"] / groups["n"]
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Event Study con outcome=cumple_v4 (descriptivo + contraste)."
    )
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Construyendo panel con cumple_v4...")
    panel = build_panel(base_dir)

    # Descriptive stats
    stats = descriptive_stats(panel)
    stats.to_csv(out_dir / "descriptive_rates.csv", index=False)
    print(f"[OK] descriptive_rates.csv ({len(stats)} rows)")

    # Part A: Descriptive (ALWAYS_IN year dummies)
    print("Parte A: Descriptivo (year dummies en ALWAYS_IN)...")
    part_a = part_a_descriptive(panel)
    part_a.to_csv(out_dir / "part_a_descriptive.csv", index=False)
    print(f"[OK] part_a_descriptive.csv ({len(part_a)} specs)")

    # Part B: Contrast (SWITCHER vs ALWAYS_IN)
    print("Parte B: Contraste (SWITCHER vs ALWAYS_IN)...")
    part_b = part_b_contrast(panel)
    part_b.to_csv(out_dir / "part_b_contrast.csv", index=False)
    print(f"[OK] part_b_contrast.csv ({len(part_b)} specs)")

    # Generate markdown report
    md = []
    md.append("# Event Study: cumple_v4 como outcome")
    md.append("")
    md.append("## Tasas descriptivas (cumple_v4 por grupo y anio)")
    md.append(df_to_md(stats.round(4)))
    md.append("")
    md.append("## Parte A: Descriptivo puro (ALWAYS_IN, year dummies, base=2022)")
    md.append("")
    md.append("Responde: hubo salto abrupto en cumple_v4 en 2025?")
    md.append("No causal; documenta serie temporal dentro de ALWAYS_IN.")
    md.append("")
    md.append(df_to_md(part_a.round(6)))
    md.append("")
    md.append("Interpretacion:")
    md.append("- d_2023/d_2024 son pre-trends (deben ser cercanos a 0 o estables).")
    md.append("- d_2025 cuantifica el salto.")
    md.append("")
    md.append("## Parte B: Contraste SWITCHER vs ALWAYS_IN (cumple_v4)")
    md.append("")
    md.append("Responde: los SWITCHER saltaron mas en cumple_v4?")
    md.append("Hereda problema de pre-trends de T1. Contraste descriptivo, no causal.")
    md.append("")
    md.append(df_to_md(part_b.round(6)))
    md.append("")
    md.append("Interpretacion:")
    md.append("- switcher_2023/2024 son pre-trends del contraste (deben ~0).")
    md.append("- switcher_2025 es el diferencial post-2025.")
    md.append("- B3 (t1_post) es el TWFE simple del contraste.")

    (out_dir / "event_study_cumple_v4.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("[OK] event_study_cumple_v4.md")


if __name__ == "__main__":
    main()
