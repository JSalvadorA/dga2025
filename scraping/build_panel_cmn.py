import argparse
from pathlib import Path

import pandas as pd

from db import connect


def fetch_cmn_base(conn) -> pd.DataFrame:
    sql = """
        SELECT
            anio,
            sec_ejec,
            MAX(CASE WHEN fase_codigo = 1 THEN 1 ELSE 0 END) AS has_f1,
            MAX(CASE WHEN fase_codigo = 2 THEN 1 ELSE 0 END) AS has_f2,
            MAX(CASE WHEN fase_codigo = 3 THEN 1 ELSE 0 END) AS has_f3,
            MAX(CASE WHEN fuente = 'MEF' THEN 1 ELSE 0 END) AS has_mef,
            MAX(CASE WHEN fuente = 'MINEDU' THEN 1 ELSE 0 END) AS has_minedu,
            MAX(CASE WHEN fuente = 'MEF' AND fase_codigo = 1 THEN 1 ELSE 0 END) AS has_f1_mef,
            MAX(CASE WHEN fuente = 'MEF' AND fase_codigo = 2 THEN 1 ELSE 0 END) AS has_f2_mef,
            MAX(CASE WHEN fuente = 'MEF' AND fase_codigo = 3 THEN 1 ELSE 0 END) AS has_f3_mef,
            MAX(CASE WHEN fuente = 'MINEDU' AND fase_codigo = 1 THEN 1 ELSE 0 END) AS has_f1_minedu,
            MAX(CASE WHEN fuente = 'MINEDU' AND fase_codigo = 2 THEN 1 ELSE 0 END) AS has_f2_minedu,
            MAX(CASE WHEN fuente = 'MINEDU' AND fase_codigo = 3 THEN 1 ELSE 0 END) AS has_f3_minedu
        FROM dwh_ind1.fact_cmn_fase
        GROUP BY anio, sec_ejec
        ORDER BY anio, sec_ejec;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return pd.DataFrame(rows, columns=cols)


def build_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["cumple_v4"] = ((df["has_f1"] == 1) & (df["has_f2"] == 1) & (df["has_f3"] == 1)).astype(int)
    df["cumple_mef"] = (
        (df["has_f1_mef"] == 1) & (df["has_f2_mef"] == 1) & (df["has_f3_mef"] == 1)
    ).astype(int)
    df["cumple_minedu"] = (
        (df["has_f1_minedu"] == 1)
        & (df["has_f2_minedu"] == 1)
        & (df["has_f3_minedu"] == 1)
    ).astype(int)
    df["cumple_cross"] = (
        (df["cumple_v4"] == 1) & (df["cumple_mef"] == 0) & (df["cumple_minedu"] == 0)
    ).astype(int)
    return df


def build_qc(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("anio").agg(
        ues_total=("sec_ejec", "nunique"),
        cumple_v4=("cumple_v4", "sum"),
        cumple_mef=("cumple_mef", "sum"),
        cumple_minedu=("cumple_minedu", "sum"),
        cumple_cross=("cumple_cross", "sum"),
        has_mef=("has_mef", "sum"),
        has_minedu=("has_minedu", "sum"),
    )
    grouped["cumple_v4_pct"] = (grouped["cumple_v4"] / grouped["ues_total"] * 100).round(2)
    grouped["cumple_mef_pct"] = (grouped["cumple_mef"] / grouped["ues_total"] * 100).round(2)
    grouped["cumple_minedu_pct"] = (grouped["cumple_minedu"] / grouped["ues_total"] * 100).round(2)
    grouped["cumple_cross_pct"] = (grouped["cumple_cross"] / grouped["ues_total"] * 100).round(2)
    grouped = grouped.reset_index()
    return grouped


def write_qc_md(qc: pd.DataFrame, path: Path) -> None:
    lines = []
    lines.append("# QC cumple_v4 por anio")
    lines.append("")
    lines.append("| Anio | UEs | Cumple_v4 | Cumple_v4_% | Cumple_MEF | Cumple_MINEDU | Cumple_cross |")
    lines.append("|------|-----|-----------|-------------|------------|---------------|--------------|")
    for _, row in qc.iterrows():
        lines.append(
            f"| {int(row['anio'])} | {int(row['ues_total'])} | {int(row['cumple_v4'])} | "
            f"{row['cumple_v4_pct']:.2f} | {int(row['cumple_mef'])} | "
            f"{int(row['cumple_minedu'])} | {int(row['cumple_cross'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Construir base CMN (cumple_v4) desde dwh_ind1.fact_cmn_fase.")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--qc-dir", default=None)
    parser.add_argument("--write-csv", action="store_true")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    processed_dir = Path(args.processed_dir) if args.processed_dir else base_dir / "outputs" / "processed"
    qc_dir = Path(args.qc_dir) if args.qc_dir else base_dir / "outputs" / "qc"
    processed_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    conn = connect()
    df = fetch_cmn_base(conn)
    df = build_flags(df)

    qc = build_qc(df)
    qc_csv = qc_dir / "cmn_cumple_v4_qc.csv"
    qc.to_csv(qc_csv, index=False)
    qc_md = qc_dir / "cmn_cumple_v4_qc.md"
    write_qc_md(qc, qc_md)

    out_parquet = processed_dir / "cmn_cumple_v4.parquet"
    df.to_parquet(out_parquet, index=False)
    if args.write_csv:
        out_csv = processed_dir / "cmn_cumple_v4.csv"
        df.to_csv(out_csv, index=False)

    print(f"[OK] Rows: {len(df)}")
    print(f"[OK] Parquet: {out_parquet}")
    print(f"[OK] QC CSV: {qc_csv}")
    print(f"[OK] QC MD: {qc_md}")


if __name__ == "__main__":
    main()
