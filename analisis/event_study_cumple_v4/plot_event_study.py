"""
Graficos Event Study: cumple_v4 como outcome.

Genera 3 figuras:
  1. Coefficient Plot (Part A): year dummies en ALWAYS_IN
  2. Parallel Trends: tasas cumple_v4 por grupo y anio
  3. Coefficient Plot (Part B): contraste SWITCHER vs ALWAYS_IN

Cada figura se exporta en dos resoluciones:
  - *_latex.png: 6.5x4 in, 300dpi (para documentos LaTeX)
  - *_linkedin.png: 1200x630px, fuentes grandes (para publicacion)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

# --- Config ---
OUT = Path(__file__).resolve().parent / "outputs"
FIGS = OUT / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

# Paleta
C_MAIN = "#1B4F72"
C_ACCENT = "#E74C3C"
C_SECONDARY = "#27AE60"
C_GREY = "#BDC3C7"
C_LIGHT = "#EBF5FB"
C_CI = "#AED6F1"

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


def save_dual(fig, name: str) -> None:
    """Guarda en formato LaTeX y LinkedIn."""
    # LaTeX
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    # LinkedIn (1200x630)
    fig.set_size_inches(12, 6.3)
    for ax in fig.get_axes():
        ax.title.set_fontsize(16)
        ax.xaxis.label.set_fontsize(13)
        ax.yaxis.label.set_fontsize(13)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontsize(12)
    fig.savefig(FIGS / f"{name}_linkedin.png", dpi=100, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def plot_coeff_part_a() -> None:
    """Coefficient plot: year dummies (base=2022) en ALWAYS_IN."""
    df = pd.read_csv(OUT / "part_a_descriptive.csv")
    # Use spec A1 (best: no controls, pure year dummies)
    row = df[df["spec"] == "A1_year_dummies_FE_entity"].iloc[0]

    years = [2022, 2023, 2024, 2025]
    betas = [0, row["beta_d_2023"], row["beta_d_2024"], row["beta_d_2025"]]
    ses = [0, row["se_d_2023"], row["se_d_2024"], row["se_d_2025"]]

    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    # Shaded pre-period
    ax.axvspan(2021.8, 2024.5, color=C_LIGHT, alpha=0.6, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=1.2, alpha=0.7, zorder=1)

    # Zero reference line
    ax.axhline(0, color="grey", linewidth=0.8, linestyle="-", alpha=0.5)

    # CI bars
    ax.vlines(years, ci_lo, ci_hi, color=C_CI, linewidth=3, zorder=2)

    # Points
    ax.scatter(years, betas, color=C_MAIN, s=80, zorder=3, edgecolors="white", linewidth=1.5)

    # Annotations
    ax.annotate(
        f"+{betas[3]:.1%}",
        xy=(2025, betas[3]), xytext=(2025.15, betas[3] - 0.06),
        fontsize=11, fontweight="bold", color=C_MAIN,
        arrowprops=dict(arrowstyle="-", color=C_GREY, lw=0.8),
    )
    ax.text(2023.15, -0.04, "Pre-treatment", fontsize=9, color="grey", style="italic")
    ax.text(2024.65, -0.04, "Post", fontsize=9, color=C_ACCENT, style="italic")

    ax.set_xticks(years)
    ax.set_xlabel("Anio")
    ax.set_ylabel("Coeficiente (cambio en prob. cumple_v4)")
    ax.set_xlim(2021.5, 2025.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))

    fig.tight_layout()
    save_dual(fig, "fig1_coeff_partA")
    print("[OK] fig1_coeff_partA")


def plot_parallel_trends() -> None:
    """Tasas cumple_v4 por grupo y anio."""
    df = pd.read_csv(OUT / "descriptive_rates.csv")

    fig, ax = plt.subplots(figsize=(6.5, 4))

    groups = {"ALWAYS_IN": (C_MAIN, "o", "ALWAYS_IN (n=1284)"),
              "SWITCHER": (C_ACCENT, "s", "SWITCHER (n=607)")}

    for grp, (color, marker, label) in groups.items():
        sub = df[df["group_t1"] == grp].sort_values("anio")
        ax.plot(sub["anio"], sub["rate"], color=color, marker=marker,
                markersize=8, linewidth=2.2, label=label, zorder=3)

    # Shaded post
    ax.axvspan(2024.5, 2025.5, color="#FDEDEC", alpha=0.5, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=1, alpha=0.6)

    # Annotations
    ai_25 = df[(df["group_t1"] == "ALWAYS_IN") & (df["anio"] == 2025)]["rate"].values[0]
    sw_25 = df[(df["group_t1"] == "SWITCHER") & (df["anio"] == 2025)]["rate"].values[0]
    ax.annotate(f"{ai_25:.1%}", xy=(2025, ai_25), xytext=(2025.08, ai_25 + 0.02),
                fontsize=10, color=C_MAIN, fontweight="bold")
    ax.annotate(f"{sw_25:.1%}", xy=(2025, sw_25), xytext=(2025.08, sw_25 - 0.04),
                fontsize=10, color=C_ACCENT, fontweight="bold")

    ax.set_xticks([2022, 2023, 2024, 2025])
    ax.set_xlabel("Anio")
    ax.set_ylabel("Tasa de cumplimiento V4")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_ylim(-0.02, 1.0)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)

    fig.tight_layout()
    save_dual(fig, "fig2_parallel_trends")
    print("[OK] fig2_parallel_trends")


def plot_coeff_part_b() -> None:
    """Coefficient plot: contraste SWITCHER vs ALWAYS_IN."""
    df = pd.read_csv(OUT / "part_b_contrast.csv")
    # B2 is the best spec (controls + region-year FE)
    row = df[df["spec"] == "B2_contrast_controls_FE_region_year"].iloc[0]

    years = [2022, 2023, 2024, 2025]
    betas = [0, row["beta_switcher_2023"], row["beta_switcher_2024"], row["beta_switcher_2025"]]
    ses = [0,
           row["se_switcher_2023"] if pd.notna(row["se_switcher_2023"]) else 0,
           row["se_switcher_2024"],
           row["se_switcher_2025"]]

    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    ax.axvspan(2021.8, 2024.5, color=C_LIGHT, alpha=0.6, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=1.2, alpha=0.7, zorder=1)
    ax.axhline(0, color="grey", linewidth=0.8, linestyle="-", alpha=0.5)

    ax.vlines(years, ci_lo, ci_hi, color="#F5B7B1", linewidth=3, zorder=2)
    ax.scatter(years, betas, color=C_ACCENT, s=80, zorder=3, edgecolors="white", linewidth=1.5)

    # Annotation for 2025
    ax.annotate(
        f"{betas[3]:+.1%}\n(SWITCHER < ALWAYS_IN)",
        xy=(2025, betas[3]), xytext=(2024.3, betas[3] - 0.04),
        fontsize=9, color=C_ACCENT, fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color=C_ACCENT, lw=1.2),
    )

    ax.set_xticks(years)
    ax.set_xlabel("Anio")
    ax.set_ylabel("Diferencial SWITCHER - ALWAYS_IN")
    ax.set_xlim(2021.5, 2025.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))

    fig.tight_layout()
    save_dual(fig, "fig3_coeff_partB")
    print("[OK] fig3_coeff_partB")


if __name__ == "__main__":
    plot_coeff_part_a()
    plot_parallel_trends()
    plot_coeff_part_b()
    print(f"\nFiguras guardadas en: {FIGS}")
