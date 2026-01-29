"""
Test 1: DiD por macro-region (Costa/Sierra/Selva) usando panel T1 municipal.

Salida:
- outputs/test1_macro_region_did.csv
- outputs/test1_macro_region_did.md
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


def macro_region_from_depto(name: str) -> str:
    if not isinstance(name, str):
        return "UNKNOWN"
    n = name.strip().upper()
    if "CALLAO" in n:
        return "COSTA"
    costa = {
        "TUMBES",
        "PIURA",
        "LAMBAYEQUE",
        "LA LIBERTAD",
        "ANCASH",
        "LIMA",
        "ICA",
        "AREQUIPA",
        "MOQUEGUA",
        "TACNA",
    }
    sierra = {
        "CAJAMARCA",
        "HUANUCO",
        "PASCO",
        "JUNIN",
        "HUANCAVELICA",
        "AYACUCHO",
        "APURIMAC",
        "CUSCO",
        "PUNO",
    }
    selva = {
        "AMAZONAS",
        "LORETO",
        "SAN MARTIN",
        "UCAYALI",
        "MADRE DE DIOS",
    }
    if n in costa:
        return "COSTA"
    if n in sierra:
        return "SIERRA"
    if n in selva:
        return "SELVA"
    return "UNKNOWN"


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
    panel["post"] = (panel["anio"] == 2025).astype(int)
    panel["switcher_x_post"] = panel["switcher"] * panel["post"]
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))
    panel["macro_region"] = panel["departamento_name"].map(macro_region_from_depto)
    return panel


def did_manual(df: pd.DataFrame) -> dict:
    always_pre = df[(df["switcher"] == 0) & (df["anio"] <= 2024)]["cumple_v4"].mean()
    always_post = df[(df["switcher"] == 0) & (df["anio"] == 2025)]["cumple_v4"].mean()
    switch_pre = df[(df["switcher"] == 1) & (df["anio"] <= 2024)]["cumple_v4"].mean()
    switch_post = df[(df["switcher"] == 1) & (df["anio"] == 2025)]["cumple_v4"].mean()
    did = (switch_post - switch_pre) - (always_post - always_pre)
    return {
        "always_pre": always_pre,
        "always_post": always_post,
        "switch_pre": switch_pre,
        "switch_post": switch_post,
        "did_manual": did,
    }


def did_ols(df: pd.DataFrame) -> dict:
    d = df[["cumple_v4", "switcher", "post", "switcher_x_post", "log_pia", "log_pim"]].dropna()
    if d.empty:
        return {"delta_ols": np.nan, "se_ols": np.nan, "pvalue_ols": np.nan, "n_ols": 0}
    X = sm.add_constant(d[["switcher", "post", "switcher_x_post", "log_pia", "log_pim"]])
    try:
        m = sm.OLS(d["cumple_v4"], X).fit(cov_type="HC1")
        return {
            "delta_ols": float(m.params["switcher_x_post"]),
            "se_ols": float(m.bse["switcher_x_post"]),
            "pvalue_ols": float(m.pvalues["switcher_x_post"]),
            "n_ols": int(m.nobs),
        }
    except Exception:
        return {"delta_ols": np.nan, "se_ols": np.nan, "pvalue_ols": np.nan, "n_ols": int(len(d))}


def main() -> None:
    panel = build_panel()

    rows = []
    for macro in sorted(panel["macro_region"].dropna().unique()):
        sub = panel[panel["macro_region"] == macro].copy()
        n_always = sub[sub["switcher"] == 0]["sec_ejec"].nunique()
        n_switch = sub[sub["switcher"] == 1]["sec_ejec"].nunique()

        stats = did_manual(sub)
        ols = did_ols(sub)

        rows.append(
            {
                "macro_region": macro,
                "n_always_in": n_always,
                "n_switcher": n_switch,
                **stats,
                **ols,
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "test1_macro_region_did.csv", index=False)

    md = []
    md.append("# Test 1: DiD por macro-region (Costa/Sierra/Selva)")
    md.append("")
    md.append("Macro-region se asigna por departamento (mapeo estandar por regiones naturales).")
    md.append("Si deseas otra definicion, edita la tabla de mapeo del script.")
    md.append("")
    md.append(out.to_markdown(index=False))
    (OUT_DIR / "test1_macro_region_did.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("[OK] test1_macro_region_did.csv")
    print("[OK] test1_macro_region_did.md")


if __name__ == "__main__":
    main()
