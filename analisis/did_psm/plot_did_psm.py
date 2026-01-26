"""
Graficos para PSM-DiD.

Genera:
1. Balance antes/despues del matching (SMD)
2. Distribucion de propensity scores
3. DiD en muestra emparejada
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use("seaborn-v0_8-whitegrid")
COLORS = {"ALWAYS_IN": "#2E86AB", "SWITCHER": "#A23B72", "accent": "#F18F01"}


def load_results(out_dir: Path) -> dict:
    """Carga resultados del PSM-DiD."""
    return {
        "balance": pd.read_csv(out_dir / "balance_check.csv"),
        "pscore": pd.read_csv(out_dir / "propensity_scores.csv"),
        "did": pd.read_csv(out_dir / "did_psm_results.csv").iloc[0].to_dict(),
        "pairs": pd.read_csv(out_dir / "matched_pairs.csv"),
    }


def plot_balance(results: dict, out_dir: Path) -> None:
    """Grafico de balance: SMD antes vs despues."""
    bal = results["balance"]

    fig, ax = plt.subplots(figsize=(10, 5))

    y_pos = np.arange(len(bal))
    width = 0.35

    bars1 = ax.barh(y_pos - width/2, bal["smd_before"].abs(), width, label="Antes del matching", color="#E74C3C", alpha=0.7)
    bars2 = ax.barh(y_pos + width/2, bal["smd_after"].abs(), width, label="Después del matching", color="#27AE60", alpha=0.7)

    # Linea de referencia (|SMD| < 0.1 = buen balance)
    ax.axvline(x=0.1, color="black", linestyle="--", lw=1.5, label="Umbral |SMD| = 0.1")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(bal["variable"].str.replace("log_", "log(") + ")", fontsize=12)
    ax.set_xlabel("| Standardized Mean Difference |", fontsize=12)
    ax.legend(loc="upper right", fontsize=10)

    # Anotaciones de reduccion
    for i, row in bal.iterrows():
        ax.text(0.65, i, f"-{row['reduction_pct']:.0f}%", ha="left", va="center", fontsize=11, fontweight="bold", color="#27AE60")

    ax.set_xlim(0, 0.8)
    plt.tight_layout()
    fig.savefig(out_dir / "fig_psm_balance.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_psm_balance.png")


def plot_pscore_distribution(results: dict, out_dir: Path) -> None:
    """Histograma de propensity scores por grupo."""
    ps = results["pscore"]

    fig, ax = plt.subplots(figsize=(10, 5))

    ps_treated = ps[ps["switcher"] == 1]["pscore"]
    ps_control = ps[ps["switcher"] == 0]["pscore"]

    ax.hist(ps_control, bins=30, alpha=0.6, color=COLORS["ALWAYS_IN"], label=f"ALWAYS_IN (n={len(ps_control)})", density=True)
    ax.hist(ps_treated, bins=30, alpha=0.6, color=COLORS["SWITCHER"], label=f"SWITCHER (n={len(ps_treated)})", density=True)

    ax.axvline(ps_control.mean(), color=COLORS["ALWAYS_IN"], linestyle="--", lw=2)
    ax.axvline(ps_treated.mean(), color=COLORS["SWITCHER"], linestyle="--", lw=2)

    ax.set_xlabel("Propensity Score P(SWITCHER | X)", fontsize=12)
    ax.set_ylabel("Densidad", fontsize=12)
    ax.legend(fontsize=11)

    plt.tight_layout()
    fig.savefig(out_dir / "fig_psm_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_psm_distribution.png")


def plot_did_matched(results: dict, out_dir: Path) -> None:
    """DiD en muestra emparejada."""
    d = results["did"]

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.array([0, 1, 3, 4])
    heights = [
        d["control_pre"] * 100,
        d["control_post"] * 100,
        d["treated_pre"] * 100,
        d["treated_post"] * 100,
    ]
    colors = [COLORS["ALWAYS_IN"], COLORS["ALWAYS_IN"], COLORS["SWITCHER"], COLORS["SWITCHER"]]
    alphas = [0.5, 1.0, 0.5, 1.0]

    bars = ax.bar(x, heights, color=colors, edgecolor="black", linewidth=1.2)
    for bar, alpha in zip(bars, alphas):
        bar.set_alpha(alpha)

    for xi, h in zip(x, heights):
        ax.text(xi, h + 2, f"{h:.1f}%", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(["Pre\n(matched)", "Post\n(matched)", "Pre\n(matched)", "Post\n(matched)"], fontsize=11)
    ax.set_ylabel("Tasa cumple_v4 (%)", fontsize=12)
    ax.set_ylim(0, 105)
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS["ALWAYS_IN"], label="ALWAYS_IN (matched)"),
        Patch(facecolor=COLORS["SWITCHER"], label="SWITCHER (matched)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=11)

    did_val = d["did_manual"] * 100
    ax.text(0.98, 0.05, f"DiD = {did_val:.1f} pp\n(p = {d['pvalue']:.3f})",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=13, fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    plt.tight_layout()
    fig.savefig(out_dir / "fig_psm_did_matched.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_psm_did_matched.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Graficos PSM-DiD")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).resolve().parent / "outputs"

    print("=" * 50)
    print("GRAFICOS PSM-DiD")
    print("=" * 50)

    results = load_results(out_dir)

    plot_balance(results, out_dir)
    plot_pscore_distribution(results, out_dir)
    plot_did_matched(results, out_dir)

    print("\n[OK] Todos los graficos generados en:", out_dir)


if __name__ == "__main__":
    main()
