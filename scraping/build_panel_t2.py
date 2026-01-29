import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def read_padron(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    df["sec_ejec"] = df["sec_ejec"].astype(str).str.replace(r"\D", "", regex=True)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["siga_implementado"] = df["siga_implementado"].str.upper().str.strip()
    df["categoria"] = df["categoria"].str.upper().str.strip()
    return df


def build_padron_year(padron: pd.DataFrame) -> pd.DataFrame:
    muni = padron[padron["categoria"].str.contains("MUNICIPALIDADES", na=False)].copy()
    muni = muni[muni["anio"].isin([2022, 2023, 2024, 2025])]
    muni["s_it"] = (muni["siga_implementado"] == "SI").astype(int)
    padron_year = (
        muni.groupby(["sec_ejec", "anio"], as_index=False)["s_it"]
        .max()
    )
    return padron_year


def build_always_in(padron_year: pd.DataFrame) -> pd.DataFrame:
    pivot = padron_year.pivot_table(
        index="sec_ejec",
        columns="anio",
        values="s_it",
        aggfunc="max",
        fill_value=0,
    )
    for year in [2022, 2023, 2024, 2025]:
        if year not in pivot.columns:
            pivot[year] = 0
    pivot["siga_always_in"] = (
        (pivot[2022] == 1)
        & (pivot[2023] == 1)
        & (pivot[2024] == 1)
        & (pivot[2025] == 1)
    ).astype(int)
    return pivot[["siga_always_in"]].reset_index()


def build_panel(presupuesto: pd.DataFrame, cmn: pd.DataFrame, padron_year: pd.DataFrame, always_in: pd.DataFrame) -> pd.DataFrame:
    panel = presupuesto.copy()
    panel["anio"] = pd.to_numeric(panel["anio"], errors="coerce").astype("Int64")

    panel = panel.merge(padron_year, on=["sec_ejec", "anio"], how="left")
    panel = panel.merge(always_in, on="sec_ejec", how="left")

    cmn_cols = [c for c in cmn.columns if c not in ("anio", "sec_ejec")]
    panel = panel.merge(cmn, on=["sec_ejec", "anio"], how="left")

    panel["cmn_present"] = panel["cumple_v4"].notna().astype(int)
    panel[cmn_cols] = panel[cmn_cols].fillna(0)

    panel["t_it"] = panel["cumple_v4"]
    panel["t_it_applicable"] = (panel["s_it"] == 1).astype(int)
    mask_not_app = panel["s_it"] != 1
    panel.loc[mask_not_app, ["t_it"] + cmn_cols] = np.nan

    return panel


def qc(panel: pd.DataFrame) -> pd.DataFrame:
    base = panel.groupby("anio").agg(
        ues_total=("sec_ejec", "nunique"),
        ues_s_it_1=("sec_ejec", lambda s: s[panel.loc[s.index, "s_it"] == 1].nunique()),
        ues_s_it_0=("sec_ejec", lambda s: s[panel.loc[s.index, "s_it"] == 0].nunique()),
        t_it_1=("t_it", "sum"),
        cmn_present=("cmn_present", "sum"),
    ).reset_index()
    base["t_it_rate"] = (base["t_it_1"] / base["ues_s_it_1"]).replace([np.inf, -np.inf], np.nan)
    return base


def write_md(qc_df: pd.DataFrame, path: Path) -> None:
    lines = []
    lines.append("# QC panel T2 (programo CMN)")
    lines.append("")
    lines.append("| Anio | UEs total | UEs S=SI | UEs S=NO | T_it=1 | T_it_rate | CMN present |")
    lines.append("|------|-----------|---------|---------|--------|-----------|-------------|")
    for _, row in qc_df.iterrows():
        lines.append(
            f"| {int(row['anio'])} | {int(row['ues_total'])} | {int(row['ues_s_it_1'])} | "
            f"{int(row['ues_s_it_0'])} | {int(row['t_it_1'])} | "
            f"{row['t_it_rate']:.4f} | {int(row['cmn_present'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Construir panel T2 (programo CMN) para municipalidades.")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--padron-path", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--write-csv", action="store_true")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    processed_dir = Path(args.processed_dir) if args.processed_dir else base_dir / "outputs" / "processed"
    padron_path = Path(args.padron_path) if args.padron_path else base_dir / "outputs" / "padron" / "padron_largo.csv"
    out_dir = Path(args.out_dir) if args.out_dir else base_dir / "outputs" / "panel_t2"
    out_dir.mkdir(parents=True, exist_ok=True)

    presupuesto_path = processed_dir / "presupuesto_muni_panel.parquet"
    cmn_path = processed_dir / "cmn_cumple_v4.parquet"

    presupuesto = pd.read_parquet(presupuesto_path)
    cmn = pd.read_parquet(cmn_path)

    padron = read_padron(padron_path)
    padron_year = build_padron_year(padron)
    always_in = build_always_in(padron_year)

    panel = build_panel(presupuesto, cmn, padron_year, always_in)

    panel_parquet = out_dir / "panel_t2_muni.parquet"
    panel.to_parquet(panel_parquet, index=False)
    if args.write_csv:
        panel_csv = out_dir / "panel_t2_muni.csv"
        panel.to_csv(panel_csv, index=False)

    qc_df = qc(panel)
    qc_csv = out_dir / "panel_t2_qc.csv"
    qc_df.to_csv(qc_csv, index=False)
    qc_md = out_dir / "panel_t2_qc.md"
    write_md(qc_df, qc_md)

    print(f"[OK] Rows: {len(panel)}")
    print(f"[OK] Panel: {panel_parquet}")
    print(f"[OK] QC CSV: {qc_csv}")
    print(f"[OK] QC MD: {qc_md}")


if __name__ == "__main__":
    main()
