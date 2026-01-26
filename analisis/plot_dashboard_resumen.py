"""
Dashboard resumen: Panel 2x2 combinando los 3 metodos.

Genera 1 figura con 4 subpaneles:
  (A) Tendencias paralelas por grupo (Event Study)
  (B) Coefficient plot year dummies (Event Study)
  (C) Descomposicion Kitagawa (Oaxaca-Blinder)
  (D) Efecto por quintil PIA (Heterogeneidad)

Exporta:
  - dashboard_resumen_latex.png: para documentos
  - dashboard_resumen_linkedin.png: 1200x1200px para redes sociales
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# --- Paths ---
BASE = Path(__file__).resolve().parent
ES_OUT = BASE / "event_study_cumple_v4" / "outputs"
OB_OUT = BASE / "oaxaca_blinder" / "outputs"
HE_OUT = BASE / "heterogeneidad_pia" / "outputs"
FIGS = BASE / "outputs" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

# --- Paleta ---
C_MAIN = "#1B4F72"
C_ACCENT = "#E74C3C"
C_SECONDARY = "#27AE60"
C_ORANGE = "#F39C12"
C_CI = "#AED6F1"
C_GREY = "#BDC3C7"
C_LIGHT = "#EBF5FB"
C_GRADIENT = ["#AED6F1", "#5DADE2", "#2E86C1", "#1B4F72", "#0B2F4A"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "DejaVu Sans", "Arial"],
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def panel_a(ax) -> None:
    """Tendencias paralelas por grupo."""
    df = pd.read_csv(ES_OUT / "descriptive_rates.csv")

    groups = {"ALWAYS_IN": (C_MAIN, "o"), "SWITCHER": (C_ACCENT, "s")}
    for grp, (color, marker) in groups.items():
        sub = df[df["group_t1"] == grp].sort_values("anio")
        ax.plot(sub["anio"], sub["rate"], color=color, marker=marker,
                markersize=6, linewidth=2, label=grp, zorder=3)

    ax.axvspan(2024.5, 2025.5, color="#FDEDEC", alpha=0.4, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=0.8, alpha=0.5)

    ax.set_xticks([2022, 2023, 2024, 2025])
    ax.set_ylabel("Tasa cumple_v4")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_ylim(-0.02, 1.0)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.8)


def panel_b(ax) -> None:
    """Coefficient plot Part A."""
    df = pd.read_csv(ES_OUT / "part_a_descriptive.csv")
    row = df[df["spec"] == "A1_year_dummies_FE_entity"].iloc[0]

    years = [2022, 2023, 2024, 2025]
    betas = [0, row["beta_d_2023"], row["beta_d_2024"], row["beta_d_2025"]]
    ses = [0, row["se_d_2023"], row["se_d_2024"], row["se_d_2025"]]
    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    ax.axvspan(2021.8, 2024.5, color=C_LIGHT, alpha=0.5, zorder=0)
    ax.axvline(2024.5, color=C_ACCENT, linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(0, color="grey", linewidth=0.6, alpha=0.5)

    ax.vlines(years, ci_lo, ci_hi, color=C_CI, linewidth=2.5, zorder=2)
    ax.scatter(years, betas, color=C_MAIN, s=50, zorder=3, edgecolors="white", linewidth=1.2)

    ax.annotate(f"+{betas[3]:.0%}", xy=(2025, betas[3]),
                xytext=(2025.1, betas[3] - 0.08), fontsize=9,
                fontweight="bold", color=C_MAIN)

    ax.set_xticks(years)
    ax.set_ylabel("Coef. (vs 2022)")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_xlim(2021.5, 2025.5)


def panel_c(ax) -> None:
    """Barras Kitagawa multi-year."""
    df = pd.read_csv(OB_OUT / "multi_year_decomposition.csv")

    periods = ["22$\\rightarrow$23", "23$\\rightarrow$24", "24$\\rightarrow$25"]
    behavior = df["delta_behavior_pp"].tolist()
    composition = df["delta_composition_pp"].tolist()

    x = np.arange(len(periods))
    width = 0.35

    ax.bar(x - width / 2, behavior, width, label="Comportamiento",
           color=C_MAIN, edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar(x + width / 2, composition, width, label="Composicion",
           color=C_ORANGE, edgecolor="white", linewidth=0.6, zorder=3)

    ax.axhline(0, color="grey", linewidth=0.6, alpha=0.5)

    # Highlight 2024->2025
    ax.axvspan(x[2] - 0.55, x[2] + 0.55, color=C_LIGHT, alpha=0.4, zorder=0)
    ax.text(x[2], behavior[2] + 2, f"+{behavior[2]:.0f}pp\n(79%)",
            ha="center", fontsize=8, fontweight="bold", color=C_MAIN)

    ax.set_xticks(x)
    ax.set_xticklabels(periods, fontsize=9)
    ax.set_ylabel("pp")
    ax.legend(loc="lower left", fontsize=7, framealpha=0.8)


def panel_d(ax) -> None:
    """Dot plot por quintil PIA."""
    df = pd.read_csv(HE_OUT / "by_quintile_pia.csv")

    quintiles = df["quintile"].tolist()
    betas = df["beta_post_2025"].tolist()
    ses = df["se_post_2025"].tolist()

    y_pos = np.arange(len(quintiles))
    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    ax.hlines(y_pos, ci_lo, ci_hi, color=C_GRADIENT, linewidth=2.5, zorder=2)
    for i, (yp, b) in enumerate(zip(y_pos, betas)):
        ax.scatter(b, yp, color=C_GRADIENT[i], s=70, zorder=3,
                   edgecolors="white", linewidth=1.2)
        ax.text(b + 0.012, yp, f"{b:.0%}", va="center",
                fontsize=8, fontweight="bold", color=C_GRADIENT[i])

    ax.axvline(0, color="grey", linewidth=0.6, alpha=0.4, linestyle="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(quintiles, fontsize=9)
    ax.set_xlabel("Efecto post-2025")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_xlim(0.55, 0.85)
    ax.invert_yaxis()


def main() -> None:
    # --- LaTeX version (6.5 x 6.5) ---
    fig = plt.figure(figsize=(6.5, 6.5))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    panel_a(ax_a)
    panel_b(ax_b)
    panel_c(ax_c)
    panel_d(ax_d)

    fig.savefig(FIGS / "dashboard_resumen_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.08)
    print("[OK] dashboard_resumen_latex.png")
    plt.close(fig)

    # --- LinkedIn version (1200x1200) ---
    plt.rcParams.update({"font.size": 11})
    fig = plt.figure(figsize=(12, 12))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    panel_a(ax_a)
    panel_b(ax_b)
    panel_c(ax_c)
    panel_d(ax_d)

    for ax in [ax_a, ax_b, ax_c, ax_d]:
        ax.xaxis.label.set_fontsize(12)
        ax.yaxis.label.set_fontsize(12)

    fig.savefig(FIGS / "dashboard_resumen_linkedin.png", dpi=100, bbox_inches="tight", pad_inches=0.15)
    print("[OK] dashboard_resumen_linkedin.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
    print(f"\nFiguras guardadas en: {FIGS}")
