"""
Graficos para DiD Clasico 2x2.

Genera:
1. Grafico de barras: tasas pre/post por grupo
2. Grafico DiD: visualizacion del efecto diferencial
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

# Estilo
C_MAIN = "#1B4F72"
C_ACCENT = "#A10115"
C_GREY = "#95A5A6"
COLORS = {"ALWAYS_IN": C_MAIN, "SWITCHER": C_ACCENT}

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
    """Carga resultados del DiD."""
    manual = pd.read_csv(out_dir / "did_manual.csv").iloc[0].to_dict()
    fe = pd.read_csv(out_dir / "fe_con_controles.csv").iloc[0].to_dict()
    return {"manual": manual, "fe": fe}


def plot_barras_pre_post(results: dict, out_dir: Path) -> None:
    """Grafico de barras: tasas pre/post por grupo."""
    m = results["manual"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    x = np.array([0, 1, 3, 4])
    heights = [
        m["always_in_pre"] * 100,
        m["always_in_post"] * 100,
        m["switcher_pre"] * 100,
        m["switcher_post"] * 100,
    ]
    colors = [COLORS["ALWAYS_IN"], COLORS["ALWAYS_IN"], COLORS["SWITCHER"], COLORS["SWITCHER"]]
    alphas = [0.5, 1.0, 0.5, 1.0]

    bars = ax.bar(x, heights, color=colors, edgecolor="black", linewidth=1.2)
    for bar, alpha in zip(bars, alphas):
        bar.set_alpha(alpha)

    # Etiquetas en barras
    for i, (xi, h) in enumerate(zip(x, heights)):
        ax.text(xi, h + 2, f"{h:.1f}%", ha="center", va="bottom", fontsize=12, fontweight="bold")

    # Flechas de diferencia
    ax.annotate(
        "", xy=(1, m["always_in_post"] * 100), xytext=(0, m["always_in_pre"] * 100),
        arrowprops=dict(arrowstyle="->", color=COLORS["ALWAYS_IN"], lw=2),
    )
    ax.text(0.5, (m["always_in_pre"] + m["always_in_post"]) / 2 * 100,
            f"+{m['always_in_diff']*100:.1f} pp", ha="center", fontsize=10, color=COLORS["ALWAYS_IN"])

    ax.annotate(
        "", xy=(4, m["switcher_post"] * 100), xytext=(3, m["switcher_pre"] * 100),
        arrowprops=dict(arrowstyle="->", color=COLORS["SWITCHER"], lw=2),
    )
    ax.text(3.5, (m["switcher_pre"] + m["switcher_post"]) / 2 * 100 + 5,
            f"+{m['switcher_diff']*100:.1f} pp", ha="center", fontsize=10, color=COLORS["SWITCHER"])

    ax.set_xticks(x)
    ax.set_xticklabels(["Pre\n(2022-24)", "Post\n(2025)", "Pre\n(2022-24)", "Post\n(2025)"], fontsize=11)
    ax.set_ylabel("Tasa cumple_v4 (%)", fontsize=12)
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    # Leyenda manual
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS["ALWAYS_IN"], label=f"ALWAYS_IN (n={int(m['n_always_in'])})"),
        Patch(facecolor=COLORS["SWITCHER"], label=f"SWITCHER (n={int(m['n_switcher'])})"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=11)

    # Caja DiD
    did_val = m["did_manual"] * 100
    ax.text(0.98, 0.05, f"DiD = {did_val:.1f} pp", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=14, fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="#E8F1FA", alpha=0.9))

    plt.tight_layout()
    fig.savefig(out_dir / "fig_did_barras_pre_post.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_did_barras_pre_post.png")


def plot_did_lines(results: dict, out_dir: Path) -> None:
    """Grafico de lineas: tendencias paralelas (hipoteticas) vs observadas."""
    m = results["manual"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    # Datos observados
    years = [2024, 2025]
    always_obs = [m["always_in_pre"] * 100, m["always_in_post"] * 100]
    switch_obs = [m["switcher_pre"] * 100, m["switcher_post"] * 100]

    # Lineas observadas
    ax.plot(years, always_obs, "o-", color=COLORS["ALWAYS_IN"], lw=2.5, markersize=10, label="ALWAYS_IN (observado)")
    ax.plot(years, switch_obs, "s-", color=COLORS["SWITCHER"], lw=2.5, markersize=10, label="SWITCHER (observado)")

    # Contrafactual: si SWITCHER hubiera seguido tendencia paralela
    switch_cf_post = m["switcher_pre"] * 100 + m["always_in_diff"] * 100
    ax.plot([2024, 2025], [m["switcher_pre"] * 100, switch_cf_post], "s--",
            color=COLORS["SWITCHER"], lw=1.5, markersize=8, alpha=0.5, label="SWITCHER (contrafactual)")

    # Flecha DiD
    ax.annotate(
        "", xy=(2025, m["switcher_post"] * 100), xytext=(2025, switch_cf_post),
        arrowprops=dict(arrowstyle="<->", color=COLORS["SWITCHER"], lw=2),
    )
    did_val = m["did_manual"] * 100
    ax.text(2025.05, (m["switcher_post"] * 100 + switch_cf_post) / 2,
            f"DiD\n{did_val:.1f} pp", ha="left", va="center", fontsize=11, color=COLORS["SWITCHER"], fontweight="bold")

    ax.set_xlim(2023.8, 2025.3)
    ax.set_ylim(-5, 105)
    ax.set_xticks([2024, 2025])
    ax.set_xticklabels(["Pre (2022-2024)", "Post (2025)"], fontsize=12)
    ax.set_ylabel("Tasa cumple_v4 (%)", fontsize=11)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.legend(loc="upper left", fontsize=10)

    plt.tight_layout()
    fig.savefig(out_dir / "fig_did_lines.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_did_lines.png")


def plot_salto_hero(results: dict, out_dir: Path) -> None:
    """Grafico hero: el salto 34% -> 74% para LinkedIn."""
    m = results["manual"]

    fig, ax = plt.subplots(figsize=(8.5, 5.0))

    # Calculo del indicador agregado (aproximado)
    # Usando pesos aproximados: ALWAYS_IN domina
    n_total_pre = m["n_always_in"] + m["n_switcher"]
    ind_pre = (m["n_always_in"] * m["always_in_pre"] + m["n_switcher"] * m["switcher_pre"]) / n_total_pre
    ind_post = (m["n_always_in"] * m["always_in_post"] + m["n_switcher"] * m["switcher_post"]) / n_total_pre

    years = [2022, 2023, 2024, 2025]
    # Valores aproximados del informe
    values = [33.3, 40.3, 34.7, 74.2]

    colors_bar = [C_GREY, C_GREY, C_GREY, C_ACCENT]
    bars = ax.bar(years, values, color=colors_bar, edgecolor="black", linewidth=1.5, width=0.6)

    # Etiquetas
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=14, fontweight="bold")

    # Flecha del salto
    ax.annotate(
        "", xy=(2025, 74), xytext=(2024, 35),
        arrowprops=dict(arrowstyle="-|>", color=C_ACCENT, lw=3, mutation_scale=20),
    )
    ax.text(2024.5, 55, "+40 pp", ha="center", va="center", fontsize=16, fontweight="bold", color=C_ACCENT,
            rotation=45)

    ax.set_ylim(0, 90)
    ax.set_ylabel("Indicador V4 (%)", fontsize=12)
    ax.set_xlabel("Año", fontsize=12)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    # Anotacion
    ax.text(0.02, 0.98, "Transición SIGA Escritorio -> SIGA Web",
            transform=ax.transAxes, ha="left", va="top", fontsize=11,
            style="italic", color=C_GREY)

    plt.tight_layout()
    fig.savefig(out_dir / "fig_salto_hero.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] fig_salto_hero.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Graficos DiD Clasico")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).resolve().parent / "outputs"

    print("=" * 50)
    print("GRAFICOS DiD CLASICO 2x2")
    print("=" * 50)

    results = load_results(out_dir)

    plot_barras_pre_post(results, out_dir)
    plot_did_lines(results, out_dir)
    plot_salto_hero(results, out_dir)

    print("\n[OK] Todos los graficos generados en:", out_dir)


if __name__ == "__main__":
    main()
