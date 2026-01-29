"""
Test 5: Placebo temporal (fake 2024) en muestra PSM matcheada.

Especificacion alineada al informe:
  cumpe_v4 ~ switcher + post_placebo + switcher_x_post_placebo + log_pia + log_pim
con OLS y errores robustos (HC1).

Salida:
- outputs/test5_placebo_psm_matched.csv
- outputs/test5_placebo_psm_matched.md
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PANEL_T1 = BASE_DIR / "outputs" / "panel_t1" / "panel_t1_muni.parquet"
CMN = BASE_DIR / "outputs" / "processed" / "cmn_cumple_v4.parquet"
MATCHED = BASE_DIR / "did_psm" / "outputs" / "matched_pairs.csv"


def build_panel() -> pd.DataFrame:
    t1 = pd.read_parquet(PANEL_T1)
    cmn = pd.read_parquet(CMN)
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    t1["sec_ejec"] = t1["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    for col in ["anio", "pia", "pim"]:
        if col in t1.columns:
            t1[col] = pd.to_numeric(t1[col], errors="coerce")

    panel = t1.merge(cmn, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)
    panel = panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])].copy()

    panel["switcher"] = (panel["group_t1"] == "SWITCHER").astype(int)
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))
    return panel


def placebo_2024(panel: pd.DataFrame) -> tuple[dict, dict]:
    """Placebo temporal con post_placebo=2024 (solo 2022-2024)."""
    pre = panel[panel["anio"] <= 2024].copy()
    pre["post_placebo"] = (pre["anio"] == 2024).astype(int)
    pre["switcher_x_post_placebo"] = pre["switcher"] * pre["post_placebo"]

    always_pre = pre[(pre["switcher"] == 0) & (pre["post_placebo"] == 0)]["cumple_v4"].mean()
    always_post = pre[(pre["switcher"] == 0) & (pre["post_placebo"] == 1)]["cumple_v4"].mean()
    switch_pre = pre[(pre["switcher"] == 1) & (pre["post_placebo"] == 0)]["cumple_v4"].mean()
    switch_post = pre[(pre["switcher"] == 1) & (pre["post_placebo"] == 1)]["cumple_v4"].mean()
    did_manual = (switch_post - switch_pre) - (always_post - always_pre)

    d = pre[
        [
            "cumple_v4",
            "switcher",
            "post_placebo",
            "switcher_x_post_placebo",
            "log_pia",
            "log_pim",
        ]
    ].dropna()
    if d.empty:
        reg = {"delta": np.nan, "se": np.nan, "pvalue": np.nan, "n": 0}
    else:
        X = sm.add_constant(d[["switcher", "post_placebo", "switcher_x_post_placebo", "log_pia", "log_pim"]])
        m = sm.OLS(d["cumple_v4"], X).fit(cov_type="HC1")
        reg = {
            "delta": float(m.params["switcher_x_post_placebo"]),
            "se": float(m.bse["switcher_x_post_placebo"]),
            "pvalue": float(m.pvalues["switcher_x_post_placebo"]),
            "n": int(m.nobs),
        }

    stats = {
        "always_pre": always_pre,
        "always_post": always_post,
        "switch_pre": switch_pre,
        "switch_post": switch_post,
        "did_manual": did_manual,
    }
    return stats, reg


def main() -> None:
    if not MATCHED.exists():
        raise FileNotFoundError(f"matched_pairs.csv no encontrado: {MATCHED}")

    panel = build_panel()

    matched_pairs = pd.read_csv(MATCHED)
    for col in ["treated_sec_ejec", "control_sec_ejec"]:
        matched_pairs[col] = (
            matched_pairs[col]
            .astype(str)
            .str.replace(r"\D", "", regex=True)
        )
    matched_ids = set(matched_pairs["treated_sec_ejec"]) | set(matched_pairs["control_sec_ejec"])

    # Full sample placebo
    stats_full, reg_full = placebo_2024(panel)
    n_full = panel["sec_ejec"].nunique()

    # Matched sample placebo
    panel_matched = panel[panel["sec_ejec"].isin(matched_ids)].copy()
    stats_matched, reg_matched = placebo_2024(panel_matched)
    n_matched = panel_matched["sec_ejec"].nunique()

    out = pd.DataFrame(
        [
            {
                "sample": "full",
                "n_ues": n_full,
                **stats_full,
                **reg_full,
            },
            {
                "sample": "matched",
                "n_ues": n_matched,
                **stats_matched,
                **reg_matched,
            },
        ]
    )

    out.to_csv(OUT_DIR / "test5_placebo_psm_matched.csv", index=False)

    md = []
    md.append("# Test 5: Placebo temporal (2024) en muestra PSM matcheada")
    md.append("")
    md.append("Especificacion OLS con controles (log_pia, log_pim), consistente con PSM-DiD del informe.")
    md.append("Post placebo = 2024, muestra 2022-2024.")
    md.append("")
    md.append(out.to_markdown(index=False))
    (OUT_DIR / "test5_placebo_psm_matched.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("[OK] test5_placebo_psm_matched.csv")
    print("[OK] test5_placebo_psm_matched.md")


if __name__ == "__main__":
    main()
