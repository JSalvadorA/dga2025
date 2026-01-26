"""
Grafico de transicion 2024->2025 (flujo de entidades entre estados).

Usa datos de la base PostgreSQL exportados como constantes
(de la query de transicion ejecutada previamente).

Genera:
  - fig10_transition_latex.png
  - fig10_transition_linkedin.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as FancyBboxPatch
import numpy as np

# --- Config ---
FIGS = Path(__file__).resolve().parent / "outputs" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

# Datos de la transicion (de query SQL viabilidad_RD)
# status_2024 -> status_2025: n
FLOWS = {
    ("cumple", "cumple"): 605,
    ("cumple", "no_cumple"): 150,
    ("no_cumple", "cumple"): 1104,
    ("no_cumple", "no_cumple"): 314,
}

C_MAIN = "#1B4F72"
C_ACCENT = "#E74C3C"
C_GREEN = "#27AE60"
C_GREY = "#95A5A6"
C_LIGHT_GREEN = "#A9DFBF"
C_LIGHT_RED = "#F5B7B1"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "DejaVu Sans", "Arial"],
    "font.size": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def save_dual(fig, name: str) -> None:
    fig.savefig(FIGS / f"{name}_latex.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    fig.set_size_inches(12, 6.3)
    fig.savefig(FIGS / f"{name}_linkedin.png", dpi=100, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def plot_transition() -> None:
    """Diagrama de flujo horizontal mostrando transiciones."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # --- Left side (2024) ---
    # cumple_2024: 605+150 = 755
    # no_cumple_2024: 1104+314 = 1418
    total = 755 + 1418  # 2173

    left_cumple_h = 755 / total * 7
    left_nocumple_h = 1418 / total * 7

    # Right side (2025)
    # cumple_2025: 605+1104 = 1709
    # no_cumple_2025: 150+314 = 464
    right_cumple_h = 1709 / total * 7
    right_nocumple_h = 464 / total * 7

    left_x = 1.5
    right_x = 8.5
    bar_w = 1.0
    base_y = 1.5

    # Left bars
    ax.barh(base_y + left_nocumple_h / 2, bar_w, left_nocumple_h,
            left=left_x - bar_w / 2, color=C_LIGHT_RED, edgecolor="white", linewidth=1.5)
    ax.barh(base_y + left_nocumple_h + 0.2 + left_cumple_h / 2, bar_w, left_cumple_h,
            left=left_x - bar_w / 2, color=C_LIGHT_GREEN, edgecolor="white", linewidth=1.5)

    # Right bars
    ax.barh(base_y + right_nocumple_h / 2, bar_w, right_nocumple_h,
            left=right_x - bar_w / 2, color=C_LIGHT_RED, edgecolor="white", linewidth=1.5)
    ax.barh(base_y + right_nocumple_h + 0.2 + right_cumple_h / 2, bar_w, right_cumple_h,
            left=right_x - bar_w / 2, color=C_LIGHT_GREEN, edgecolor="white", linewidth=1.5)

    # Labels
    ax.text(left_x, base_y + left_nocumple_h + 0.2 + left_cumple_h / 2,
            f"Cumple\n(n={755})", ha="center", va="center", fontsize=9,
            fontweight="bold", color=C_GREEN)
    ax.text(left_x, base_y + left_nocumple_h / 2,
            f"No cumple\n(n={1418})", ha="center", va="center", fontsize=9,
            fontweight="bold", color=C_ACCENT)

    ax.text(right_x, base_y + right_nocumple_h + 0.2 + right_cumple_h / 2,
            f"Cumple\n(n={1709})", ha="center", va="center", fontsize=9,
            fontweight="bold", color=C_GREEN)
    ax.text(right_x, base_y + right_nocumple_h / 2,
            f"No cumple\n(n={464})", ha="center", va="center", fontsize=9,
            fontweight="bold", color=C_ACCENT)

    # Year headers
    ax.text(left_x, 9.2, "2024", ha="center", fontsize=14, fontweight="bold", color=C_MAIN)
    ax.text(right_x, 9.2, "2025", ha="center", fontsize=14, fontweight="bold", color=C_MAIN)

    # Flow arrows
    arrow_props = dict(arrowstyle="->,head_width=0.3,head_length=0.15",
                       connectionstyle="arc3,rad=0.15", linewidth=1.5)

    # Main flow: no_cumple -> cumple (1104) - THE BIG JUMP
    mid_left_nc = base_y + left_nocumple_h * 0.7
    mid_right_c = base_y + right_nocumple_h + 0.2 + right_cumple_h * 0.3
    ax.annotate("", xy=(right_x - bar_w / 2 - 0.1, mid_right_c),
                xytext=(left_x + bar_w / 2 + 0.1, mid_left_nc),
                arrowprops=dict(**arrow_props, color=C_GREEN, lw=3))
    ax.text(5, mid_left_nc + 0.8, "1,104\n(saltan!)", ha="center",
            fontsize=11, fontweight="bold", color=C_GREEN,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=C_GREEN, linewidth=1.5))

    # cumple -> cumple (605)
    mid_left_c = base_y + left_nocumple_h + 0.2 + left_cumple_h * 0.5
    mid_right_c2 = base_y + right_nocumple_h + 0.2 + right_cumple_h * 0.75
    ax.annotate("", xy=(right_x - bar_w / 2 - 0.1, mid_right_c2),
                xytext=(left_x + bar_w / 2 + 0.1, mid_left_c),
                arrowprops=dict(**arrow_props, color=C_GREY, lw=1.5))
    ax.text(5, mid_left_c + 0.3, "605", ha="center", fontsize=9, color=C_GREY)

    # cumple -> no_cumple (150)
    mid_right_nc = base_y + right_nocumple_h * 0.7
    mid_left_c_low = base_y + left_nocumple_h + 0.2 + left_cumple_h * 0.2
    ax.annotate("", xy=(right_x - bar_w / 2 - 0.1, mid_right_nc),
                xytext=(left_x + bar_w / 2 + 0.1, mid_left_c_low),
                arrowprops=dict(**arrow_props, color=C_ACCENT, lw=1))
    ax.text(5.5, mid_left_c_low - 1.0, "150", ha="center", fontsize=8, color=C_ACCENT)

    # no_cumple -> no_cumple (314)
    mid_left_nc_low = base_y + left_nocumple_h * 0.3
    mid_right_nc_low = base_y + right_nocumple_h * 0.3
    ax.annotate("", xy=(right_x - bar_w / 2 - 0.1, mid_right_nc_low),
                xytext=(left_x + bar_w / 2 + 0.1, mid_left_nc_low),
                arrowprops=dict(**arrow_props, color=C_GREY, lw=1))
    ax.text(5, mid_left_nc_low - 0.3, "314", ha="center", fontsize=8, color=C_GREY)

    # Summary box
    pct_jump = 1104 / 1418 * 100
    ax.text(5, 0.5, f"78% de las no-cumplidoras en 2024 pasaron a cumplir en 2025",
            ha="center", fontsize=9, style="italic", color=C_MAIN,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=C_LIGHT_GREEN, alpha=0.3, edgecolor="none"))

    fig.tight_layout()
    save_dual(fig, "fig10_transition")
    print("[OK] fig10_transition")


if __name__ == "__main__":
    plot_transition()
    print(f"\nFiguras guardadas en: {FIGS}")
