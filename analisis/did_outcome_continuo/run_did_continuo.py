"""
DiD con Outcome Continuo: Ejecucion Presupuestal (y_exec_pct).

Motivacion:
  - cumple_v4 es binario y casi deterministico (tener FASE3 => cumple)
  - Un outcome continuo permite detectar efectos en el margen INTENSIVO
  - La ejecucion presupuestal es un proxy de eficiencia/capacidad administrativa

Outcome:
  y_exec_pct = devengado / pim * 100

Especificacion:
  y_exec_pct_it = alpha_i + gamma_t + delta*(SWITCHER x POST) + X'beta + epsilon

Ventajas:
  - Outcome continuo con mas variacion
  - Permite verificar pre-trends con mas precision
  - Captura efecto en eficiencia, no solo en cumplimiento formal

Limitaciones:
  - Puede no estar relacionado directamente con SIGA Web
  - Ejecucion depende de muchos factores externos
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
    """Construye panel con SWITCHER y ALWAYS_IN, incluyendo ejecucion."""
    outputs = base_dir / "outputs"

    t1 = pd.read_parquet(outputs / "panel_t1" / "panel_t1_muni.parquet")
    for col in ["anio", "pia", "pim", "devengado"]:
        if col in t1.columns:
            t1[col] = pd.to_numeric(t1[col], errors="coerce")

    # Calcular % ejecucion
    t1["y_exec_pct"] = np.where(
        t1["pim"] > 0,
        (t1["devengado"] / t1["pim"]) * 100,
        np.nan
    )

    # Filtrar outliers extremos (ejecucion > 150% o < 0)
    t1["y_exec_pct"] = t1["y_exec_pct"].clip(0, 150)

    # Agregar cumple_v4 para comparacion
    cmn = pd.read_parquet(outputs / "processed" / "cmn_cumple_v4.parquet")
    cmn["sec_ejec"] = cmn["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn_cols = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(subset=["sec_ejec", "anio"])

    panel = t1.merge(cmn_cols, on=["sec_ejec", "anio"], how="left")
    panel["cumple_v4"] = panel["cumple_v4"].fillna(0).astype(float)
    panel = panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])].copy()

    # Variables DiD
    panel["switcher"] = (panel["group_t1"] == "SWITCHER").astype(int)
    panel["post"] = (panel["anio"] == 2025).astype(int)
    panel["switcher_x_post"] = panel["switcher"] * panel["post"]

    # Year dummies para event study
    for y in [2023, 2024, 2025]:
        panel[f"d_{y}"] = (panel["anio"] == y).astype(int)
        panel[f"switcher_x_{y}"] = panel["switcher"] * panel[f"d_{y}"]

    # Controles
    panel["log_pia"] = np.log1p(panel["pia"].clip(lower=0))
    panel["log_pim"] = np.log1p(panel["pim"].clip(lower=0))

    return panel


def descriptive_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """Estadisticas descriptivas de y_exec_pct por grupo y anio."""
    stats = panel.groupby(["anio", "group_t1"]).agg(
        n=("y_exec_pct", "count"),
        mean=("y_exec_pct", "mean"),
        std=("y_exec_pct", "std"),
        median=("y_exec_pct", "median"),
        p25=("y_exec_pct", lambda x: x.quantile(0.25)),
        p75=("y_exec_pct", lambda x: x.quantile(0.75)),
    ).reset_index()
    return stats


def estimate_did_2x2(panel: pd.DataFrame) -> dict:
    """DiD clasico 2x2 con y_exec_pct."""
    # Manual
    always_pre = panel[(panel["switcher"] == 0) & (panel["post"] == 0)]["y_exec_pct"].mean()
    always_post = panel[(panel["switcher"] == 0) & (panel["post"] == 1)]["y_exec_pct"].mean()
    switch_pre = panel[(panel["switcher"] == 1) & (panel["post"] == 0)]["y_exec_pct"].mean()
    switch_post = panel[(panel["switcher"] == 1) & (panel["post"] == 1)]["y_exec_pct"].mean()

    did = (switch_post - switch_pre) - (always_post - always_pre)

    # Regresion OLS
    d = panel[["y_exec_pct", "switcher", "post", "switcher_x_post", "log_pia", "log_pim"]].dropna()
    X = sm.add_constant(d[["switcher", "post", "switcher_x_post", "log_pia", "log_pim"]])
    m = sm.OLS(d["y_exec_pct"], X).fit(cov_type="HC1")

    return {
        "control_pre": always_pre,
        "control_post": always_post,
        "treated_pre": switch_pre,
        "treated_post": switch_post,
        "did_manual": did,
        "did_regression": float(m.params["switcher_x_post"]),
        "se": float(m.bse["switcher_x_post"]),
        "pvalue": float(m.pvalues["switcher_x_post"]),
        "n": int(m.nobs),
        "r2": float(m.rsquared),
    }


def estimate_did_fe(panel: pd.DataFrame) -> dict:
    """DiD con FE entidad y tiempo."""
    d = panel[["sec_ejec", "anio", "y_exec_pct", "switcher_x_post", "log_pia", "log_pim"]].dropna()
    d = d.set_index(["sec_ejec", "anio"])

    # Con FE entidad + tiempo
    m = PanelOLS(
        d["y_exec_pct"],
        d[["switcher_x_post", "log_pia", "log_pim"]],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

    return {
        "delta": float(m.params["switcher_x_post"]),
        "se": float(m.std_errors["switcher_x_post"]),
        "n": int(m.nobs),
        "r2_within": float(m.rsquared_within),
    }


def estimate_event_study(panel: pd.DataFrame) -> pd.DataFrame:
    """Event study con interacciones switcher x year."""
    d = panel[["sec_ejec", "anio", "y_exec_pct", "switcher_x_2023", "switcher_x_2024", "switcher_x_2025"]].dropna()
    d = d.set_index(["sec_ejec", "anio"])

    x_cols = ["switcher_x_2023", "switcher_x_2024", "switcher_x_2025"]
    m = PanelOLS(
        d["y_exec_pct"],
        d[x_cols],
        entity_effects=True,
        time_effects=True,
    ).fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

    results = []
    for col in x_cols:
        year = int(col.split("_")[-1])
        results.append({
            "year": year,
            "beta": float(m.params[col]),
            "se": float(m.std_errors[col]),
            "ci_lower": float(m.params[col] - 1.96 * m.std_errors[col]),
            "ci_upper": float(m.params[col] + 1.96 * m.std_errors[col]),
        })

    return pd.DataFrame(results)


def compare_outcomes(panel: pd.DataFrame) -> pd.DataFrame:
    """Compara resultados DiD para cumple_v4 vs y_exec_pct."""
    results = []

    for outcome in ["cumple_v4", "y_exec_pct"]:
        d = panel[["sec_ejec", "anio", outcome, "switcher_x_post", "log_pia", "log_pim"]].dropna()
        d = d.set_index(["sec_ejec", "anio"])

        m = PanelOLS(
            d[outcome],
            d[["switcher_x_post", "log_pia", "log_pim"]],
            entity_effects=True,
            time_effects=True,
        ).fit(cov_type="clustered", cluster_entity=True, cluster_time=True)

        results.append({
            "outcome": outcome,
            "delta": float(m.params["switcher_x_post"]),
            "se": float(m.std_errors["switcher_x_post"]),
            "n": int(m.nobs),
            "r2_within": float(m.rsquared_within),
        })

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="DiD con outcome continuo (ejecucion presupuestal)")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("DiD CON OUTCOME CONTINUO: EJECUCION PRESUPUESTAL")
    print("=" * 70)

    # Construir panel
    print("\n[1] Construyendo panel...")
    panel = build_panel(base_dir)
    n_valid = panel["y_exec_pct"].notna().sum()
    print(f"    Panel: {len(panel)} obs, {panel['sec_ejec'].nunique()} UEs")
    print(f"    Obs con y_exec_pct valido: {n_valid}")

    # Estadisticas descriptivas
    print("\n[2] Estadisticas descriptivas...")
    desc = descriptive_stats(panel)
    print(desc.to_string(index=False))

    # DiD 2x2
    print("\n[3] DiD clasico 2x2...")
    did_2x2 = estimate_did_2x2(panel)
    print(f"    ALWAYS_IN: {did_2x2['control_pre']:.2f}% -> {did_2x2['control_post']:.2f}%")
    print(f"    SWITCHER:  {did_2x2['treated_pre']:.2f}% -> {did_2x2['treated_post']:.2f}%")
    print(f"    DiD = {did_2x2['did_manual']:.2f} pp (regresion: {did_2x2['did_regression']:.2f}, SE: {did_2x2['se']:.2f})")

    # DiD con FE
    print("\n[4] DiD con FE entidad + tiempo...")
    did_fe = estimate_did_fe(panel)
    print(f"    delta = {did_fe['delta']:.2f} (SE: {did_fe['se']:.2f})")

    # Event study
    print("\n[5] Event study (pre-trends check)...")
    es = estimate_event_study(panel)
    for _, row in es.iterrows():
        sig = "*" if abs(row["beta"]) > 1.96 * row["se"] else ""
        print(f"    {int(row['year'])}: beta = {row['beta']:.2f} (SE: {row['se']:.2f}) {sig}")

    # Comparacion outcomes
    print("\n[6] Comparacion: cumple_v4 vs y_exec_pct...")
    compare = compare_outcomes(panel)
    print(compare.to_string(index=False))

    # Guardar resultados
    desc.to_csv(out_dir / "descriptive_stats.csv", index=False)
    pd.DataFrame([did_2x2]).to_csv(out_dir / "did_2x2.csv", index=False)
    pd.DataFrame([did_fe]).to_csv(out_dir / "did_fe.csv", index=False)
    es.to_csv(out_dir / "event_study.csv", index=False)
    compare.to_csv(out_dir / "compare_outcomes.csv", index=False)

    # Generar markdown
    md = []
    md.append("# DiD con Outcome Continuo: Ejecucion Presupuestal")
    md.append("")
    md.append("## 1. Motivacion")
    md.append("")
    md.append("- `cumple_v4` es binario y casi deterministico (tener FASE3 => cumple)")
    md.append("- Un outcome continuo permite detectar efectos en el margen INTENSIVO")
    md.append("- La ejecucion presupuestal es un proxy de eficiencia administrativa")
    md.append("")
    md.append("## 2. Variable dependiente")
    md.append("")
    md.append("```")
    md.append("y_exec_pct = (devengado / pim) * 100")
    md.append("```")
    md.append("")
    md.append("Rango: 0-150% (winsorizado)")
    md.append("")
    md.append("## 3. Estadisticas descriptivas")
    md.append("")
    md.append(df_to_md(desc.round(2)))
    md.append("")
    md.append("## 4. DiD Clasico 2x2")
    md.append("")
    md.append("| Grupo | Pre (2022-2024) | Post (2025) | Diferencia |")
    md.append("|-------|-----------------|-------------|------------|")
    md.append(f"| ALWAYS_IN | {did_2x2['control_pre']:.2f}% | {did_2x2['control_post']:.2f}% | {did_2x2['control_post']-did_2x2['control_pre']:.2f} pp |")
    md.append(f"| SWITCHER | {did_2x2['treated_pre']:.2f}% | {did_2x2['treated_post']:.2f}% | {did_2x2['treated_post']-did_2x2['treated_pre']:.2f} pp |")
    md.append(f"| **DiD** | | | **{did_2x2['did_manual']:.2f} pp** |")
    md.append("")
    md.append("### Regresion OLS")
    md.append("")
    md.append(f"- delta = {did_2x2['did_regression']:.2f} (SE: {did_2x2['se']:.2f}, p={did_2x2['pvalue']:.4f})")
    md.append(f"- n = {did_2x2['n']}, R2 = {did_2x2['r2']:.4f}")
    md.append("")
    md.append("## 5. DiD con Efectos Fijos")
    md.append("")
    md.append("Especificacion: FE entidad + FE tiempo, SE clustered")
    md.append("")
    md.append(f"- delta = **{did_fe['delta']:.2f}** (SE: {did_fe['se']:.2f})")
    md.append(f"- n = {did_fe['n']}, R2_within = {did_fe['r2_within']:.4f}")
    md.append("")
    md.append("## 6. Event Study (verificacion pre-trends)")
    md.append("")
    md.append("Coeficientes de interaccion SWITCHER x AÑO (base=2022):")
    md.append("")
    md.append(df_to_md(es.round(2)))
    md.append("")
    md.append("**Interpretacion pre-trends:**")
    pre_2023 = es[es["year"] == 2023]["beta"].values[0]
    pre_2024 = es[es["year"] == 2024]["beta"].values[0]
    if abs(pre_2023) < 2 and abs(pre_2024) < 2:
        md.append("- Pre-trends 2023, 2024 cercanos a cero: supuesto de tendencias paralelas mas creible")
    else:
        md.append("- Pre-trends distintos de cero: el supuesto de tendencias paralelas puede no cumplirse")
    md.append("")
    md.append("## 7. Comparacion: cumple_v4 vs y_exec_pct")
    md.append("")
    md.append(df_to_md(compare.round(4)))
    md.append("")
    md.append("## 8. Interpretacion")
    md.append("")
    md.append(f"- Con outcome `y_exec_pct`, el efecto DiD es **{did_fe['delta']:.2f} pp**")
    if did_fe["delta"] > 0:
        md.append("- SWITCHER mejoro su ejecucion presupuestal MAS que ALWAYS_IN")
    elif did_fe["delta"] < 0:
        md.append("- SWITCHER mejoro su ejecucion presupuestal MENOS que ALWAYS_IN")
    else:
        md.append("- No hay diferencia significativa entre grupos")
    md.append("")
    md.append("## 9. Limitaciones")
    md.append("")
    md.append("- La ejecucion presupuestal depende de muchos factores (no solo SIGA)")
    md.append("- Puede no capturar el efecto directo de la transicion SIGA Web")
    md.append("- Es un outcome complementario, no sustituto de cumple_v4")

    (out_dir / "did_outcome_continuo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n[OK] Resultados guardados en:", out_dir)


if __name__ == "__main__":
    main()
