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


def build_groups(padron: pd.DataFrame) -> pd.DataFrame:
    muni = padron[padron["categoria"].str.contains("MUNICIPALIDADES", na=False)].copy()
    muni = muni[muni["anio"].isin([2022, 2023, 2024, 2025])]

    pre = muni[muni["anio"].isin([2022, 2023, 2024])]
    post = muni[muni["anio"] == 2025][["sec_ejec", "siga_implementado"]].drop_duplicates()
    post = post.rename(columns={"siga_implementado": "post_siga"})

    pre_status = (
        pre.groupby("sec_ejec")["siga_implementado"]
        .apply(lambda s: "SI" if (s == "SI").any() else ("NO" if (s == "NO").any() else "ABSENT"))
        .reset_index()
        .rename(columns={"siga_implementado": "pre_siga"})
    )

    groups = pre_status.merge(post, on="sec_ejec", how="outer")
    groups["post_siga"] = groups["post_siga"].fillna("ABSENT")
    groups["pre_siga"] = groups["pre_siga"].fillna("ABSENT")

    def label(row):
        if row["post_siga"] == "SI" and row["pre_siga"] == "SI":
            return "ALWAYS_IN"
        if row["post_siga"] == "SI" and row["pre_siga"] == "NO":
            return "SWITCHER"
        if row["post_siga"] == "SI" and row["pre_siga"] == "ABSENT":
            return "ENTRY_ABSENT"
        if row["post_siga"] == "ABSENT" and row["pre_siga"] == "SI":
            return "EXIT"
        return "OTHER"

    groups["group_t1"] = groups.apply(label, axis=1)
    groups["t1_switcher"] = (groups["group_t1"] == "SWITCHER").astype(int)
    return muni, groups


def build_panel(presupuesto: pd.DataFrame, muni: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    padron_year = muni[["sec_ejec", "anio", "siga_implementado"]].drop_duplicates()
    padron_year = padron_year.rename(columns={"siga_implementado": "siga_padron"})

    panel = presupuesto.merge(padron_year, on=["sec_ejec", "anio"], how="left")
    panel = panel.merge(groups[["sec_ejec", "pre_siga", "post_siga", "group_t1", "t1_switcher"]], on="sec_ejec", how="left")

    panel["post_2025"] = (panel["anio"] == 2025).astype(int)
    panel["t1_post"] = ((panel["t1_switcher"] == 1) & (panel["post_2025"] == 1)).astype(int)
    return panel


def qc(panel: pd.DataFrame) -> pd.DataFrame:
    counts = (
        panel.groupby(["anio", "group_t1"], dropna=False)["sec_ejec"]
        .nunique()
        .reset_index()
        .rename(columns={"sec_ejec": "ues"})
    )
    missing_group = panel["group_t1"].isna().sum()
    missing_padron = panel["siga_padron"].isna().sum()

    summary = pd.DataFrame(
        [
            {"metric": "rows", "value": int(len(panel))},
            {"metric": "missing_group", "value": int(missing_group)},
            {"metric": "missing_padron_year", "value": int(missing_padron)},
        ]
    )
    return counts, summary


def write_md(counts: pd.DataFrame, summary: pd.DataFrame, path: Path) -> None:
    lines = []
    lines.append("# QC panel T1 (NO->SI)")
    lines.append("")
    for _, row in summary.iterrows():
        lines.append(f"- {row['metric']}: {row['value']}")
    lines.append("")
    lines.append("| Anio | Group | UEs |")
    lines.append("|------|-------|-----|")
    for _, row in counts.sort_values(["anio", "group_t1"]).iterrows():
        lines.append(f"| {row['anio']} | {row['group_t1']} | {int(row['ues'])} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Construir panel T1 (NO->SI / adopcion SIGA Web).")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--padron-path", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--write-csv", action="store_true")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    processed_dir = Path(args.processed_dir) if args.processed_dir else base_dir / "outputs" / "processed"
    padron_path = Path(args.padron_path) if args.padron_path else base_dir / "outputs" / "padron" / "padron_largo.csv"
    out_dir = Path(args.out_dir) if args.out_dir else base_dir / "outputs" / "panel_t1"
    out_dir.mkdir(parents=True, exist_ok=True)

    presupuesto_path = processed_dir / "presupuesto_muni_panel.parquet"
    presupuesto = pd.read_parquet(presupuesto_path)

    padron = read_padron(padron_path)
    muni, groups = build_groups(padron)
    panel = build_panel(presupuesto, muni, groups)

    panel_parquet = out_dir / "panel_t1_muni.parquet"
    panel.to_parquet(panel_parquet, index=False)
    if args.write_csv:
        panel_csv = out_dir / "panel_t1_muni.csv"
        panel.to_csv(panel_csv, index=False)

    counts, summary = qc(panel)
    qc_csv = out_dir / "panel_t1_qc.csv"
    counts.to_csv(qc_csv, index=False)
    qc_md = out_dir / "panel_t1_qc.md"
    write_md(counts, summary, qc_md)

    print(f"[OK] Rows: {len(panel)}")
    print(f"[OK] Panel: {panel_parquet}")
    print(f"[OK] QC CSV: {qc_csv}")
    print(f"[OK] QC MD: {qc_md}")


if __name__ == "__main__":
    main()
