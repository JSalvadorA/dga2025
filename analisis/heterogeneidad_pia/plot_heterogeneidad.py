"""
Graficos Heterogeneidad PIA: efecto diferencial por tamano presupuestal.

Genera 3 figuras:
  1. Cleveland dot plot: beta_post_2025 por quintil PIA (separados)
  2. Interaction coefficient plot: diferencial vs Q1 (base)
  3. Before/After panel: tasas pre vs post por quintil

Cada figura se exporta en dos resoluciones:
  - *_latex.png: 6.5x4 in, 300dpi
  - *_linkedin.png: 1200x630px
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

C_MAIN = "#1B4F72"
C_ACCENT = "#E74C3C"
C_GRADIENT = ["#AED6F1", "#5DADE2", "#2E86C1", "#1B4F72", "#0B2F4A"]
C_PRE = "#BDC3C7"
C_POST = "#1B4F72"
C_DELTA = "#27AE60"

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
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    fig.set_size_inches(12, 6.3)
    for ax in fig.get_axes():
        if ax.get_title():
            ax.title.set_fontsize(16)
        ax.xaxis.label.set_fontsize(13)
        ax.yaxis.label.set_fontsize(13)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontsize(12)
    fig.savefig(FIGS / f"{name}_linkedin.png", dpi=100, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def plot_quintile_effects() -> None:
    """Cleveland dot plot: efecto post_2025 por quintil PIA."""
    df = pd.read_csv(OUT / "by_quintile_pia.csv")
    desc = pd.read_csv(OUT / "quintile_descriptives.csv")

    quintiles = df["quintile"].tolist()
    betas = df["beta_post_2025"].tolist()
    ses = df["se_post_2025"].tolist()

    # Add PIA median info for labels
    medians = desc["pia_median"].tolist()
    labels = [f"{q}\n(PIA med: S/.{m / 1e6:.1f}M)" for q, m in zip(quintiles, medians)]

    y_pos = np.arange(len(quintiles))
    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    # Horizontal CI bars
    ax.hlines(y_pos, ci_lo, ci_hi, color=C_GRADIENT, linewidth=3, zorder=2)

    # Points with gradient
    for i, (yp, b) in enumerate(zip(y_pos, betas)):
        ax.scatter(b, yp, color=C_GRADIENT[i], s=120, zorder=3,
                   edgecolors="white", linewidth=2)

    # Value annotations (offset to avoid overlap with bands)
    for i, (yp, b, s) in enumerate(zip(y_pos, betas, ses)):
        t_stat = b / s
        sig = "***" if abs(t_stat) > 2.576 else "**" if abs(t_stat) > 1.96 else ""
        x_text = min(b + 0.02, 0.83)
        y_text = yp - 0.22 if yp > 0 else yp + 0.22
        ax.text(
            x_text, y_text, f"{b:.1%}{sig}",
            va="center", fontsize=9, fontweight="bold", color=C_GRADIENT[i],
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7),
            clip_on=False,
        )

    ax.axvline(0, color="grey", linewidth=0.8, alpha=0.5, linestyle="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Efecto post-2025 en prob(cumple_v4)")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_xlim(0.55, 0.85)
    ax.invert_yaxis()

    fig.tight_layout()
    save_dual(fig, "fig7_quintile_effects")
    print("[OK] fig7_quintile_effects")


def plot_interactions() -> None:
    """Coefficient plot: interacciones post_2025 x quintil (diferencial vs Q1)."""
    df = pd.read_csv(OUT / "interactions_pia.csv")
    row = df.iloc[0]

    quintiles = ["Q1\n(base)", "Q2", "Q3", "Q4", "Q5"]
    betas = [0,
             row["beta_post_x_Q2"],
             row["beta_post_x_Q3"],
             row["beta_post_x_Q4"],
             row["beta_post_x_Q5"]]
    ses = [0,
           row["se_post_x_Q2"],
           row["se_post_x_Q3"],
           row["se_post_x_Q4"],
           row["se_post_x_Q5"]]

    x = np.arange(len(quintiles))
    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    ax.axhline(0, color="grey", linewidth=0.8, alpha=0.6, linestyle="-")

    # CI bars
    ax.vlines(x, ci_lo, ci_hi, color="#AED6F1", linewidth=4, zorder=2)
    # Points
    colors_pts = [C_PRE] + [C_MAIN if abs(b / s) > 1.96 else C_PRE
                             for b, s in zip(betas[1:], ses[1:])]
    ax.scatter(x, betas, color=colors_pts, s=100, zorder=3,
               edgecolors="white", linewidth=1.5)

    # Significance annotations
    for i in range(1, len(betas)):
        t_stat = betas[i] / ses[i] if ses[i] > 0 else 0
        if abs(t_stat) > 1.96:
            sig = "**" if abs(t_stat) > 2.576 else "*"
            ax.text(x[i], ci_hi[i] + 0.005, sig, ha="center",
                    fontsize=12, fontweight="bold", color=C_ACCENT)

    # Base effect annotation
    base_beta = row["beta_post_2025"]
    ax.text(0, -0.06, f"Efecto base Q1:\n+{base_beta:.1%}",
            ha="center", fontsize=9, color=C_MAIN, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#EBF5FB", edgecolor="none"))

    ax.set_xticks(x)
    ax.set_xticklabels(quintiles, fontsize=10)
    ax.set_xlabel("Quintil PIA (2024)")
    ax.set_ylabel("Diferencial vs Q1 (pp)")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))

    fig.tight_layout()
    save_dual(fig, "fig8_interactions")
    print("[OK] fig8_interactions")


def plot_before_after() -> None:
    """Panel: tasas pre vs post por quintil (barras agrupadas)."""
    df = pd.read_csv(OUT / "by_quintile_pia.csv")

    quintiles = df["quintile"].tolist()
    pre = df["raw_pre_mean"].tolist()
    post = df["raw_post_mean"].tolist()
    delta = df["raw_delta"].tolist()

    x = np.arange(len(quintiles))
    width = 0.35

    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    bars_pre = ax.bar(x - width / 2, pre, width, label="Pre (2022-2024)",
                      color=C_PRE, edgecolor="white", linewidth=0.8, zorder=3)
    bars_post = ax.bar(x + width / 2, post, width, label="Post (2025)",
                       color=C_POST, edgecolor="white", linewidth=0.8, zorder=3)

    # Delta annotations
    for i, (xp, d, p) in enumerate(zip(x, delta, post)):
        ax.annotate(
            f"+{d:.0%}",
            xy=(xp + width / 2, p),
            xytext=(xp + width / 2, p + 0.03),
            fontsize=9, fontweight="bold", color=C_DELTA,
            ha="center",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(quintiles, fontsize=10)
    ax.set_xlabel("Quintil PIA (2024)")
    ax.set_ylabel("Tasa cumple_v4")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)

    fig.tight_layout()
    save_dual(fig, "fig9_before_after")
    print("[OK] fig9_before_after")


if __name__ == "__main__":
    plot_quintile_effects()
    plot_interactions()
    plot_before_after()
    print(f"\nFiguras guardadas en: {FIGS}")
