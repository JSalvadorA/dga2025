"""
Transition chart 2024 -> 2025 aligned to the municipal T1 universe.

This version avoids hardcoded counts. It recomputes flows using:
  - outputs/panel_t1/panel_t1_muni.parquet (universe ALWAYS_IN + SWITCHER)
  - outputs/processed/cmn_cumple_v4.parquet (cumple_v4 by year)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS = BASE_DIR / "outputs"
EVENT_DIR = Path(__file__).resolve().parent
OUT_DIR = EVENT_DIR / "outputs"
FIGS = OUT_DIR / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

PANEL_T1 = OUTPUTS / "panel_t1" / "panel_t1_muni.parquet"
CMN = OUTPUTS / "processed" / "cmn_cumple_v4.parquet"


C_MAIN = "#1B4F72"
C_ACCENT = "#A10115"
C_GREEN = "#1B4F72"
C_GREY = "#95A5A6"
C_LIGHT_GREEN = "#D6EAF8"
C_LIGHT_RED = "#E2B2B8"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Roboto", "DejaVu Sans", "Arial"],
        "font.size": 10,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _clean_sec(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\D", "", regex=True)


def load_universe_t1() -> set[str]:
    panel = pd.read_parquet(PANEL_T1)
    panel["sec_ejec"] = _clean_sec(panel["sec_ejec"])
    ids = (
        panel[panel["group_t1"].isin(["ALWAYS_IN", "SWITCHER"])]["sec_ejec"]
        .dropna()
        .unique()
    )
    return set(ids)


def load_cmn() -> pd.DataFrame:
    cmn = pd.read_parquet(CMN)
    cmn["sec_ejec"] = _clean_sec(cmn["sec_ejec"])
    cmn["anio"] = pd.to_numeric(cmn["anio"], errors="coerce").astype("Int64")
    cmn = cmn[["sec_ejec", "anio", "cumple_v4"]].drop_duplicates(
        subset=["sec_ejec", "anio"]
    )
    cmn["cumple_v4"] = cmn["cumple_v4"].fillna(0).astype(int)
    return cmn


def compute_flows(ids: set[str], cmn: pd.DataFrame) -> tuple[dict[tuple[str, str], int], pd.DataFrame]:
    base = pd.DataFrame({"sec_ejec": sorted(ids)})

    d24 = (
        cmn[cmn["anio"] == 2024][["sec_ejec", "cumple_v4"]]
        .rename(columns={"cumple_v4": "c24"})
        .copy()
    )
    d25 = (
        cmn[cmn["anio"] == 2025][["sec_ejec", "cumple_v4"]]
        .rename(columns={"cumple_v4": "c25"})
        .copy()
    )

    t = base.merge(d24, on="sec_ejec", how="left").merge(d25, on="sec_ejec", how="left")
    # Missing CMN rows are treated as no_cumple (0) for the transition.
    t["c24"] = t["c24"].fillna(0).astype(int)
    t["c25"] = t["c25"].fillna(0).astype(int)

    flows = {
        ("cumple", "cumple"): int(((t["c24"] == 1) & (t["c25"] == 1)).sum()),
        ("cumple", "no_cumple"): int(((t["c24"] == 1) & (t["c25"] == 0)).sum()),
        ("no_cumple", "cumple"): int(((t["c24"] == 0) & (t["c25"] == 1)).sum()),
        ("no_cumple", "no_cumple"): int(((t["c24"] == 0) & (t["c25"] == 0)).sum()),
    }
    return flows, t


def write_counts(flows: dict[tuple[str, str], int], transition: pd.DataFrame) -> None:
    counts_path = OUT_DIR / "transition_t1_counts.csv"
    md_path = OUT_DIR / "transition_t1_counts.md"

    rows = [
        {"desde": k[0], "hacia": k[1], "n": v} for k, v in sorted(flows.items())
    ]
    df = pd.DataFrame(rows)
    df.to_csv(counts_path, index=False)

    n_universe = len(transition)
    no_cumple_2024 = flows[("no_cumple", "cumple")] + flows[("no_cumple", "no_cumple")]
    pct_jump = 100 * flows[("no_cumple", "cumple")] / no_cumple_2024 if no_cumple_2024 else np.nan

    lines = [
        "# Transicion 2024 -> 2025 (universo T1 municipal)",
        "",
        f"- Universo ALWAYS_IN + SWITCHER: {n_universe}",
        f"- no_cumple -> cumple: {flows[('no_cumple', 'cumple')]}",
        f"- cumple -> no_cumple: {flows[('cumple', 'no_cumple')]}",
        f"- Flujo neto: {flows[('no_cumple', 'cumple')] - flows[('cumple', 'no_cumple')]}",
        f"- % de no_cumple 2024 que salta a cumple 2025: {pct_jump:.1f}%",
        "",
        "## Matriz",
        df.to_markdown(index=False),
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def save_dual(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    fig.set_size_inches(12, 6.3)
    fig.savefig(FIGS / f"{name}_linkedin.png", dpi=100, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def plot_transition(flows: dict[tuple[str, str], int]) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    left_cumple = flows[("cumple", "cumple")] + flows[("cumple", "no_cumple")]
    left_nocumple = flows[("no_cumple", "cumple")] + flows[("no_cumple", "no_cumple")]
    right_cumple = flows[("cumple", "cumple")] + flows[("no_cumple", "cumple")]
    right_nocumple = flows[("cumple", "no_cumple")] + flows[("no_cumple", "no_cumple")]
    total = left_cumple + left_nocumple

    left_cumple_h = left_cumple / total * 7
    left_nocumple_h = left_nocumple / total * 7
    right_cumple_h = right_cumple / total * 7
    right_nocumple_h = right_nocumple / total * 7

    left_x = 1.5
    right_x = 8.5
    bar_w = 1.0
    base_y = 1.5

    ax.barh(
        base_y + left_nocumple_h / 2,
        bar_w,
        left_nocumple_h,
        left=left_x - bar_w / 2,
        color=C_LIGHT_RED,
        edgecolor="white",
        linewidth=1.5,
    )
    ax.barh(
        base_y + left_nocumple_h + 0.2 + left_cumple_h / 2,
        bar_w,
        left_cumple_h,
        left=left_x - bar_w / 2,
        color=C_LIGHT_GREEN,
        edgecolor="white",
        linewidth=1.5,
    )

    ax.barh(
        base_y + right_nocumple_h / 2,
        bar_w,
        right_nocumple_h,
        left=right_x - bar_w / 2,
        color=C_LIGHT_RED,
        edgecolor="white",
        linewidth=1.5,
    )
    ax.barh(
        base_y + right_nocumple_h + 0.2 + right_cumple_h / 2,
        bar_w,
        right_cumple_h,
        left=right_x - bar_w / 2,
        color=C_LIGHT_GREEN,
        edgecolor="white",
        linewidth=1.5,
    )

    ax.text(
        left_x,
        base_y + left_nocumple_h + 0.2 + left_cumple_h / 2,
        f"Cumple\n(n={left_cumple})",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color=C_GREEN,
    )
    ax.text(
        left_x,
        base_y + left_nocumple_h / 2,
        f"No cumple\n(n={left_nocumple})",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color=C_ACCENT,
    )

    ax.text(
        right_x,
        base_y + right_nocumple_h + 0.2 + right_cumple_h / 2,
        f"Cumple\n(n={right_cumple})",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color=C_GREEN,
    )
    ax.text(
        right_x,
        base_y + right_nocumple_h / 2,
        f"No cumple\n(n={right_nocumple})",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color=C_ACCENT,
    )

    ax.text(left_x, 9.2, "2024", ha="center", fontsize=14, fontweight="bold", color=C_MAIN)
    ax.text(right_x, 9.2, "2025", ha="center", fontsize=14, fontweight="bold", color=C_MAIN)

    arrow_props = dict(
        arrowstyle="->,head_width=0.3,head_length=0.15",
        connectionstyle="arc3,rad=0.15",
        linewidth=1.5,
    )

    main_flow = flows[("no_cumple", "cumple")]
    main_frac_left = main_flow / left_nocumple if left_nocumple else 0.0
    main_frac_right = main_flow / right_cumple if right_cumple else 0.0

    mid_left_nc = base_y + left_nocumple_h * (1 - main_frac_left / 2)
    mid_right_c = base_y + right_nocumple_h + 0.2 + right_cumple_h * (main_frac_right / 2)

    ax.annotate(
        "",
        xy=(right_x - bar_w / 2 - 0.1, mid_right_c),
        xytext=(left_x + bar_w / 2 + 0.1, mid_left_nc),
        arrowprops=dict(**arrow_props, color=C_GREEN, lw=3),
    )
    ax.text(
        5,
        mid_left_nc + 0.8,
        f"{main_flow:,}\n(saltan!)",
        ha="center",
        fontsize=11,
        fontweight="bold",
        color=C_GREEN,
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="white",
            edgecolor=C_GREEN,
            linewidth=1.5,
        ),
    )

    mid_left_c = base_y + left_nocumple_h + 0.2 + left_cumple_h * 0.6
    mid_right_c2 = base_y + right_nocumple_h + 0.2 + right_cumple_h * 0.8
    ax.annotate(
        "",
        xy=(right_x - bar_w / 2 - 0.1, mid_right_c2),
        xytext=(left_x + bar_w / 2 + 0.1, mid_left_c),
        arrowprops=dict(**arrow_props, color=C_GREY, lw=1.5),
    )
    ax.text(5, mid_left_c + 0.2, f"{flows[('cumple', 'cumple')]:,}", ha="center", fontsize=9, color=C_GREY)

    mid_right_nc = base_y + right_nocumple_h * 0.7
    mid_left_c_low = base_y + left_nocumple_h + 0.2 + left_cumple_h * 0.25
    ax.annotate(
        "",
        xy=(right_x - bar_w / 2 - 0.1, mid_right_nc),
        xytext=(left_x + bar_w / 2 + 0.1, mid_left_c_low),
        arrowprops=dict(**arrow_props, color=C_ACCENT, lw=1),
    )
    ax.text(5.4, mid_left_c_low - 0.6, f"{flows[('cumple', 'no_cumple')]:,}", ha="center", fontsize=8, color=C_ACCENT)

    mid_left_nc_low = base_y + left_nocumple_h * 0.35
    mid_right_nc_low = base_y + right_nocumple_h * 0.35
    ax.annotate(
        "",
        xy=(right_x - bar_w / 2 - 0.1, mid_right_nc_low),
        xytext=(left_x + bar_w / 2 + 0.1, mid_left_nc_low),
        arrowprops=dict(**arrow_props, color=C_GREY, lw=1),
    )
    ax.text(5, mid_left_nc_low - 0.2, f"{flows[('no_cumple', 'no_cumple')]:,}", ha="center", fontsize=8, color=C_GREY)

    pct_jump = 100 * main_flow / left_nocumple if left_nocumple else np.nan
    ax.text(
        5,
        0.5,
        f"{pct_jump:.1f}% de las no-cumplidoras en 2024 pasaron a cumplir en 2025",
        ha="center",
        fontsize=9,
        style="italic",
        color=C_MAIN,
        bbox=dict(boxstyle="round,pad=0.4", facecolor=C_LIGHT_GREEN, alpha=0.3, edgecolor="none"),
    )

    fig.tight_layout()
    save_dual(fig, "fig10_transition_t1")
    print("[OK] fig10_transition_t1")


def main() -> None:
    ids = load_universe_t1()
    cmn = load_cmn()
    flows, transition = compute_flows(ids, cmn)
    write_counts(flows, transition)
    plot_transition(flows)
    print(f"[OK] Universe T1 size: {len(ids)}")
    print(f"[OK] Flows: {flows}")
    print(f"[OK] Figures saved to: {FIGS}")


if __name__ == "__main__":
    main()
