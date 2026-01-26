"""
Gr\u00e1ficos Oaxaca-Blinder: Descomposici\u00f3n del salto en cumple_v4.

Genera 2 figuras:
  1. Waterfall multi-anual: Composici\u00f3n vs Comportamiento por transici\u00f3n
  2. Donut/Pie: Share del salto 2024->2025

Cada figura se exporta en dos resoluciones:
  - *_latex.png: 6.5x4 in, 300dpi
  - *_linkedin.png: 1200x630px
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# --- Config ---
OUT = Path(__file__).resolve().parent / "outputs"
FIGS = OUT / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

C_BEHAVIOR = "#1B4F72"
C_COMPOSITION = "#F39C12"
C_TOTAL = "#2C3E50"
C_ACCENT = "#E74C3C"
C_POSITIVE = "#27AE60"
C_NEGATIVE = "#E74C3C"

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


def save_dual_share(fig, name: str) -> None:
    """Guarda Donut/Pie con ancho consistente para el informe."""
    # Mantener el lienzo completo para evitar que "tight" achique el ancho
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, pad_inches=0.0)
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


def plot_waterfall_multiyear() -> None:
    """Stacked bar: comportamiento vs composicion por transicion anual."""
    df = pd.read_csv(OUT / "multi_year_decomposition.csv")

    periods = df["period"].tolist()
    behavior = df["delta_behavior_pp"].tolist()
    composition = df["delta_composition_pp"].tolist()
    total = df["delta_total_pp"].tolist()

    x = np.arange(len(periods))
    width = 0.35

    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    # Stacked bars: behavior + composition
    bars_b = ax.bar(x - width / 2, behavior, width, label="Comportamiento",
                    color=C_BEHAVIOR, edgecolor="white", linewidth=0.8, zorder=3)
    bars_c = ax.bar(x + width / 2, composition, width, label="Composici\u00f3n",
                    color=C_COMPOSITION, edgecolor="white", linewidth=0.8, zorder=3)

    # Total markers
    ax.scatter(x, total, color=C_TOTAL, s=100, marker="D", zorder=4,
               edgecolors="white", linewidth=1.5, label="Delta total")

    # Reference line
    ax.axhline(0, color="grey", linewidth=0.8, alpha=0.6)

    # Annotations for 2024->2025
    ax.annotate(
        f"+{behavior[2]:.1f} pp\n(79%)",
        xy=(x[2] - width / 2, behavior[2]),
        xytext=(x[2] - width / 2 - 0.3, behavior[2] + 5),
        fontsize=9, fontweight="bold", color=C_BEHAVIOR,
        arrowprops=dict(arrowstyle="->", color=C_BEHAVIOR, lw=1),
    )
    ax.annotate(
        f"+{composition[2]:.1f} pp\n(21%)",
        xy=(x[2] + width / 2, composition[2]),
        xytext=(x[2] + width / 2 + 0.2, composition[2] + 8),
        fontsize=9, fontweight="bold", color=C_COMPOSITION,
        arrowprops=dict(arrowstyle="->", color=C_COMPOSITION, lw=1),
    )

    ax.set_xticks(x)
    ax.set_xticklabels(periods, fontsize=10)
    ax.set_ylabel("Puntos porcentuales (pp)")
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)

    # Highlight the 2024->2025 background
    ax.axvspan(x[2] - 0.6, x[2] + 0.6, color="#EBF5FB", alpha=0.4, zorder=0)

    fig.tight_layout()
    save_dual(fig, "fig4_waterfall_multiyear")
    print("[OK] fig4_waterfall_multiyear")


def plot_share_2025() -> None:
    """Donut chart: share del salto 2024->2025."""
    agg = pd.read_csv(OUT / "aggregate_decomposition.csv")

    share_b = float(agg["share_behavior"].iloc[0])
    share_c = float(agg["share_composition"].iloc[0])
    delta = float(agg["delta_total_pp"].iloc[0])

    # Compacto para el informe (reduce altura al escalar a \textwidth)
    fig, ax = plt.subplots(figsize=(6.5, 3.6))

    sizes = [share_b, share_c]
    labels = [f"Comportamiento\n({share_b:.0%})", f"Composici\u00f3n\n({share_c:.0%})"]
    colors = [C_BEHAVIOR, C_COMPOSITION]
    explode = (0.02, 0.02)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct=lambda pct: f"{pct * delta / 100:.1f} pp",
        pctdistance=0.68, startangle=90, labeldistance=1.05,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9),
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight("bold")

    # Center text
    ax.text(0, 0, f"$\\Delta$ = +{delta:.1f} pp", ha="center", va="center",
            fontsize=12, fontweight="bold", color=C_TOTAL)

    fig.tight_layout(pad=0.2)
    save_dual_share(fig, "fig5_share_2025")
    print("[OK] fig5_share_2025")


def plot_rates_evolution() -> None:
    """Evoluci\u00f3n de tasas r_A y r_E que alimentan la descomposici\u00f3n."""
    df = pd.read_csv(OUT / "multi_year_decomposition.csv")

    # Build rate series for ALWAYS_IN
    r_ai = [df.iloc[0]["r_base"]]  # 2022
    for _, row in df.iterrows():
        r_ai.append(row["r_target_AI"])
    years_ai = [2022, 2023, 2024, 2025]

    # ENTRY rates (available from 2023 onward as target)
    r_entry = [np.nan, df.iloc[0]["r_target_ENTRY"], df.iloc[1]["r_target_ENTRY"], df.iloc[2]["r_target_ENTRY"]]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    ax.plot(years_ai, r_ai, color=C_BEHAVIOR, marker="o", markersize=8,
            linewidth=2.5, label="ALWAYS_IN", zorder=3)
    ax.plot(years_ai, r_entry, color=C_COMPOSITION, marker="s", markersize=8,
            linewidth=2.5, label="ENTRY/SWITCHER", linestyle="--", zorder=3)

    # Shade post
    ax.axvspan(2024.5, 2025.5, color="#EBF5FB", alpha=0.5, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=1, alpha=0.6)

    # Annotations
    ax.annotate(f"{r_ai[-1]:.1%}", xy=(2025, r_ai[-1]),
                xytext=(2025.1, r_ai[-1] + 0.02), fontsize=10,
                color=C_BEHAVIOR, fontweight="bold")
    ax.annotate(f"{r_entry[-1]:.1%}", xy=(2025, r_entry[-1]),
                xytext=(2025.1, r_entry[-1] - 0.05), fontsize=10,
                color=C_COMPOSITION, fontweight="bold")

    ax.set_xticks(years_ai)
    ax.set_xlabel("A\u00f1o")
    ax.set_ylabel("Tasa cumple_v4")
    ax.set_ylim(-0.05, 1.0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)

    fig.tight_layout()
    save_dual(fig, "fig6_rates_evolution")
    print("[OK] fig6_rates_evolution")


if __name__ == "__main__":
    plot_waterfall_multiyear()
    plot_share_2025()
    plot_rates_evolution()
    print(f"\nFiguras guardadas en: {FIGS}")
