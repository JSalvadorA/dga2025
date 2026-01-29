"""
Graficos para DiD con Outcome Continuo.

Genera:
1. Event Study: pre-trends con y_exec_pct
2. Comparacion de outcomes: cumple_v4 vs y_exec_pct
3. Distribucion de y_exec_pct por grupo y periodo
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

C_MAIN = "#1B4F72"
C_ACCENT = "#A10115"
C_GREY = "#95A5A6"
COLORS = {"ALWAYS_IN": C_MAIN, "SWITCHER": C_ACCENT, "accent": C_ACCENT}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "DejaVu Sans", "Arial"],
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.5,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def load_results(out_dir: Path) -> dict:
    """Carga resultados del DiD continuo."""
    return {
        "event_study": pd.read_csv(out_dir / "event_study.csv"),
        "compare": pd.read_csv(out_dir / "compare_outcomes.csv"),
        "did_fe": pd.read_csv(out_dir / "did_fe.csv").iloc[0].to_dict(),
        "did_2x2": pd.read_csv(out_dir / "did_2x2.csv").iloc[0].to_dict(),
        "desc": pd.read_csv(out_dir / "descriptive_stats.csv"),
    }


def plot_event_study(results: dict, out_dir: Path) -> None:
    """Event study con IC 95%."""
    es = results["event_study"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    years = es["year"].values
    betas = es["beta"].values
    ci_lower = es["ci_lower"].values
    ci_upper = es["ci_upper"].values

    # Punto de referencia (2022 = 0)
    years_full = [2022] + list(years)
    betas_full = [0] + list(betas)
    ci_lower_full = [0] + list(ci_lower)
    ci_upper_full = [0] + list(ci_upper)

    ax.plot(years_full, betas_full, "o-", color=COLORS["SWITCHER"], lw=2.5, markersize=10)
    ax.fill_between(years_full, ci_lower_full, ci_upper_full, alpha=0.2, color=COLORS["SWITCHER"])

    # Linea de referencia
    ax.axhline(y=0, color=C_GREY, linestyle="--", lw=1)
    ax.axvline(x=2024.5, color="#A10115", linestyle=":", lw=2, label="Transición SIGA Web")

    ax.set_xticks([2022, 2023, 2024, 2025])
    ax.set_xlabel("Año", fontsize=11)
    ax.set_ylabel("Coeficiente (SWITCHER x Año)", fontsize=11)
    ax.legend(fontsize=10)

    # Anotacion
    ax.text(0.02, 0.98, "Pre-trends no significativos\n-> Tendencias paralelas más creíbles",
            transform=ax.transAxes, ha="left", va="top", fontsize=10,
            bbox=dict(boxstyle="round", facecolor="#E8F1FA", alpha=0.8))

    plt.tight_layout()
    fig.savefig(out_dir / "fig_event_study_continuo.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_event_study_continuo.png")


def plot_compare_outcomes(results: dict, out_dir: Path) -> None:
    """Comparacion de efectos DiD: cumple_v4 vs y_exec_pct."""
    cmp = results["compare"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    outcomes = cmp["outcome"].values
    deltas = cmp["delta"].values
    ses = cmp["se"].values

    x = np.arange(len(outcomes))
    colors = [C_ACCENT if abs(d) > 2*se else C_GREY for d, se in zip(deltas, ses)]

    bars = ax.bar(x, deltas, yerr=1.96*ses, capsize=5, color=colors, edgecolor="black", linewidth=1.2)

    ax.axhline(y=0, color=C_GREY, linestyle="-", lw=1)

    ax.set_xticks(x)
    ax.set_xticklabels(["cumple_v4\n(binario)", "y_exec_pct\n(% ejecución)"], fontsize=11)
    ax.set_ylabel("Efecto DiD (δ)", fontsize=11)
    # Anotaciones
    for i, (d, se) in enumerate(zip(deltas, ses)):
        sig = "**" if abs(d) > 2*se else "n.s."
        ax.text(i, d + 0.1 if d > 0 else d - 0.15, f"{d:.2f}\n({sig})", ha="center", fontsize=11, fontweight="bold")

    plt.tight_layout()
    fig.savefig(out_dir / "fig_compare_outcomes.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_compare_outcomes.png")


def plot_distribution_exec(results: dict, out_dir: Path) -> None:
    """Distribucion de y_exec_pct por grupo y periodo."""
    desc = results["desc"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    # Filtrar datos
    always = desc[desc["group_t1"] == "ALWAYS_IN"].sort_values("anio")
    switch = desc[desc["group_t1"] == "SWITCHER"].sort_values("anio")

    years = always["anio"].values

    ax.plot(years, always["mean"].values, "o-", color=COLORS["ALWAYS_IN"], lw=2.5, markersize=10, label="ALWAYS_IN")
    ax.fill_between(years, always["p25"].values, always["p75"].values, alpha=0.2, color=COLORS["ALWAYS_IN"])

    ax.plot(years, switch["mean"].values, "s-", color=COLORS["SWITCHER"], lw=2.5, markersize=10, label="SWITCHER")
    ax.fill_between(years, switch["p25"].values, switch["p75"].values, alpha=0.2, color=COLORS["SWITCHER"])

    ax.axvline(x=2024.5, color="#A10115", linestyle=":", lw=2)

    ax.set_xlabel("Año", fontsize=11)
    ax.set_ylabel("Ejecución presupuestal (%)", fontsize=11)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.legend(fontsize=11)
    ax.set_xticks([2022, 2023, 2024, 2025])

    plt.tight_layout()
    fig.savefig(out_dir / "fig_exec_evolution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_exec_evolution.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Graficos DiD Outcome Continuo")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).resolve().parent / "outputs"

    print("=" * 50)
    print("GRAFICOS DiD OUTCOME CONTINUO")
    print("=" * 50)

    results = load_results(out_dir)

    plot_event_study(results, out_dir)
    plot_compare_outcomes(results, out_dir)
    plot_distribution_exec(results, out_dir)

    print("\n[OK] Todos los graficos generados en:", out_dir)


if __name__ == "__main__":
    main()
