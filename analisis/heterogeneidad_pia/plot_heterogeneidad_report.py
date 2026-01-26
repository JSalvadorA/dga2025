"""
Version reporte: ajusta el tamanio/ratio de la figura 7 para que
no domine la pagina del informe.

Genera:
  - fig7_quintile_effects_latex.png
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


def save_report(fig, name: str) -> None:
    """Guarda en formato LaTeX (reporte)."""
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)


def plot_quintile_effects() -> None:
    """Cleveland dot plot: efecto post_2025 por quintil PIA (compacto)."""
    df = pd.read_csv(OUT / "by_quintile_pia.csv")

    quintiles = df["quintile"].tolist()
    betas = df["beta_post_2025"].tolist()
    ses = df["se_post_2025"].tolist()

    y_pos = np.arange(len(quintiles))
    ci_lo = [b - 1.96 * s for b, s in zip(betas, ses)]
    ci_hi = [b + 1.96 * s for b, s in zip(betas, ses)]

    # Menor altura para reducir tamaño en PDF al escalar a \textwidth
    fig, ax = plt.subplots(figsize=(6.5, 4))

    # Horizontal CI bars
    ax.hlines(y_pos, ci_lo, ci_hi, color=C_GRADIENT, linewidth=3, zorder=2)

    # Points with gradient
    for i, (yp, b) in enumerate(zip(y_pos, betas)):
        ax.scatter(b, yp, color=C_GRADIENT[i], s=70, zorder=3,
                   edgecolors="white", linewidth=1.2)

    # Value annotations (compact, offset to avoid overlap)
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
    ax.set_yticklabels(quintiles, fontsize=10)
    ax.set_xlabel("Efecto post-2025 en prob(cumple_v4)")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.set_xlim(0.55, 0.85)
    ax.invert_yaxis()

    fig.tight_layout()
    save_report(fig, "fig7_quintile_effects")
    print("[OK] fig7_quintile_effects")


if __name__ == "__main__":
    plot_quintile_effects()
    print(f"\nFiguras guardadas en: {FIGS}")
