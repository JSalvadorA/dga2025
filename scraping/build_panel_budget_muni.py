import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


def normalize_col(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def find_col(columns, targets, contains=False):
    norm_map = {normalize_col(c): c for c in columns}
    for t in targets:
        if t in norm_map:
            return norm_map[t]
    if contains:
        for c in columns:
            norm = normalize_col(c)
            if any(t in norm for t in targets):
                return c
    return None


def split_code_name(value: str):
    if not value:
        return None, None
    if ":" in value:
        code, name = value.split(":", 1)
        return code.strip(), name.strip()
    return None, value.strip()


def parse_num(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d\.-]", "", regex=True)
        .replace("", np.nan)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def read_csv_safe(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        return pd.read_csv(f, dtype=str)


def load_file(path: Path, siga: str, anio: int) -> pd.DataFrame:
    df = read_csv_safe(path)
    cols = list(df.columns)

    sec_col = find_col(cols, ["SECEJECEXTRACTED", "SECEJEC"], contains=True)
    dep_col = find_col(cols, ["DEPARTAMENTO"], contains=False)
    prov_col = find_col(cols, ["PROVINCIA"], contains=False)
    muni_col = find_col(cols, ["MUNICIPALIDAD"], contains=False)
    pia_col = find_col(cols, ["PIA"], contains=False)
    pim_col = find_col(cols, ["PIM"], contains=False)
    dev_col = find_col(cols, ["DEVENGADO"], contains=False)

    missing = [k for k, v in {
        "SEC_EJEC": sec_col,
        "PIA": pia_col,
        "PIM": pim_col,
        "DEVENGADO": dev_col,
    }.items() if v is None]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}. Found: {cols}")

    out = pd.DataFrame(index=df.index)
    out["anio"] = anio
    out["siga"] = siga
    out["source_file"] = path.name

    out["sec_ejec_raw"] = df[sec_col].astype(str)
    out["sec_ejec"] = out["sec_ejec_raw"].str.replace(r"\D", "", regex=True)
    out.loc[out["sec_ejec"] == "", "sec_ejec"] = np.nan

    if dep_col and dep_col in df.columns:
        out["departamento_raw"] = df[dep_col].astype(str)
        dep_code, dep_name = zip(*out["departamento_raw"].map(split_code_name))
        out["departamento_code"] = dep_code
        out["departamento_name"] = dep_name
    else:
        out["departamento_raw"] = np.nan
        out["departamento_code"] = np.nan
        out["departamento_name"] = np.nan

    if prov_col and prov_col in df.columns:
        out["provincia_raw"] = df[prov_col].astype(str)
        prov_code, prov_name = zip(*out["provincia_raw"].map(split_code_name))
        out["provincia_code"] = prov_code
        out["provincia_name"] = prov_name
    else:
        out["provincia_raw"] = np.nan
        out["provincia_code"] = np.nan
        out["provincia_name"] = np.nan

    if muni_col and muni_col in df.columns:
        out["municipalidad_raw"] = df[muni_col].astype(str)
        muni_code, muni_name = zip(*out["municipalidad_raw"].map(split_code_name))
        out["municipalidad_code"] = muni_code
        out["municipalidad_name"] = muni_name
        out["ubigeo"] = (
            out["municipalidad_code"]
            .astype(str)
            .str.split("-", n=1, expand=True)[0]
            .str.strip()
        )
        out.loc[out["ubigeo"] == "nan", "ubigeo"] = np.nan
    else:
        out["municipalidad_raw"] = np.nan
        out["municipalidad_code"] = np.nan
        out["municipalidad_name"] = np.nan
        out["ubigeo"] = np.nan

    out["pia_raw"] = df[pia_col].astype(str)
    out["pim_raw"] = df[pim_col].astype(str)
    out["devengado_raw"] = df[dev_col].astype(str)

    out["pia"] = parse_num(df[pia_col])
    out["pim"] = parse_num(df[pim_col])
    out["devengado"] = parse_num(df[dev_col])

    out["y_exec_pct"] = np.where(out["pim"] > 0, out["devengado"] / out["pim"], np.nan)
    out["y_reprog"] = np.where(out["pia"] > 0, (out["pim"] - out["pia"]) / out["pia"], np.nan)

    return out


def qc_group(df: pd.DataFrame) -> dict:
    non_null = df.dropna(subset=["sec_ejec"])
    grp = non_null.groupby(["anio", "sec_ejec"]).size()
    dup_keys = int((grp > 1).sum())
    dup_rows = int((grp[grp > 1] - 1).sum())

    y_exec = df["y_exec_pct"]
    y_reprog = df["y_reprog"]

    def q(series, p):
        return series.quantile(p) if series.notna().any() else np.nan

    return {
        "rows": int(len(df)),
        "sec_ejec_unique": int(non_null["sec_ejec"].nunique()),
        "missing_sec_ejec": int(df["sec_ejec"].isna().sum()),
        "dup_keys": dup_keys,
        "dup_rows": dup_rows,
        "y_exec_outside_0_1": int(((y_exec < 0) | (y_exec > 1)).sum()),
        "y_reprog_extreme": int(((y_reprog < -1) | (y_reprog > 10)).sum()),
        "y_exec_p01": q(y_exec, 0.01),
        "y_exec_p50": q(y_exec, 0.50),
        "y_exec_p99": q(y_exec, 0.99),
        "y_reprog_p01": q(y_reprog, 0.01),
        "y_reprog_p50": q(y_reprog, 0.50),
        "y_reprog_p99": q(y_reprog, 0.99),
    }


def build_qc(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (anio, siga), sub in df.groupby(["anio", "siga"]):
        row = {"anio": anio, "siga": siga}
        row.update(qc_group(sub))
        rows.append(row)
    overall = {"anio": "ALL", "siga": "ALL"}
    overall.update(qc_group(df))
    rows.append(overall)
    return pd.DataFrame(rows)


def write_qc_md(qc: pd.DataFrame, path: Path) -> None:
    overall = qc[(qc["anio"] == "ALL") & (qc["siga"] == "ALL")].iloc[0]
    lines = []
    lines.append("# QC presupuesto municipalidades")
    lines.append("")
    lines.append("## Resumen general")
    lines.append(f"- Rows: {overall['rows']}")
    lines.append(f"- UEs distintas: {overall['sec_ejec_unique']}")
    lines.append(f"- Missing sec_ejec: {overall['missing_sec_ejec']}")
    lines.append(f"- Duplicados (keys): {overall['dup_keys']}")
    lines.append(f"- Duplicados (rows): {overall['dup_rows']}")
    lines.append(f"- y_exec_pct fuera [0,1]: {overall['y_exec_outside_0_1']}")
    lines.append(f"- y_reprog extremos (<-1 o >10): {overall['y_reprog_extreme']}")
    lines.append("")
    lines.append("## Cuantiles (overall)")
    lines.append(
        f"- y_exec_pct p01/p50/p99: {overall['y_exec_p01']:.4f} / "
        f"{overall['y_exec_p50']:.4f} / {overall['y_exec_p99']:.4f}"
    )
    lines.append(
        f"- y_reprog p01/p50/p99: {overall['y_reprog_p01']:.4f} / "
        f"{overall['y_reprog_p50']:.4f} / {overall['y_reprog_p99']:.4f}"
    )
    lines.append("")
    lines.append("## Nota")
    lines.append("Los detalles por anio y SIGA estan en el CSV de QC.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Construir base presupuesto municipalidades normalizada.")
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--qc-dir", default=None)
    parser.add_argument("--write-csv", action="store_true")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    raw_dir = Path(args.raw_dir) if args.raw_dir else base_dir / "outputs" / "raw"
    processed_dir = Path(args.processed_dir) if args.processed_dir else base_dir / "outputs" / "processed"
    qc_dir = Path(args.qc_dir) if args.qc_dir else base_dir / "outputs" / "qc"

    processed_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for year in (2022, 2023, 2024, 2025):
        si_path = raw_dir / f"MUNI_{year}.csv"
        if si_path.exists():
            files.append((si_path, "SI", year))
        if year <= 2024:
            no_path = raw_dir / f"MUNICIPALIDADES_{year}.csv"
            if no_path.exists():
                files.append((no_path, "NO", year))

    if not files:
        raise SystemExit(f"No input files found in {raw_dir}")

    frames = []
    for path, siga, year in files:
        frames.append(load_file(path, siga, year))

    df = pd.concat(frames, ignore_index=True)

    qc = build_qc(df)
    qc_csv = qc_dir / "presupuesto_muni_qc.csv"
    qc.to_csv(qc_csv, index=False)

    qc_md = qc_dir / "presupuesto_muni_qc.md"
    write_qc_md(qc, qc_md)

    out_parquet = processed_dir / "presupuesto_muni_panel.parquet"
    df.to_parquet(out_parquet, index=False)
    if args.write_csv:
        out_csv = processed_dir / "presupuesto_muni_panel.csv"
        df.to_csv(out_csv, index=False)

    print(f"[OK] Rows: {len(df)}")
    print(f"[OK] Parquet: {out_parquet}")
    print(f"[OK] QC CSV: {qc_csv}")
    print(f"[OK] QC MD: {qc_md}")


if __name__ == "__main__":
    main()
