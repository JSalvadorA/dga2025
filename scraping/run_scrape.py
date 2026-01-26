from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import RAW_DIR, PADRON_DIR, setup_logging
from padron import build_index, load_padron_csv
from routes import CATEGORY_BY_ROUTE, ROUTES
from scraper import run_scrape
from utils import parse_years

# Logger se configura en main() con el año como sufijo
logger = None


def main() -> int:
    global logger

    parser = argparse.ArgumentParser(
        description="Scrapeo MEF con filtrado por padrón.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Scrapear municipalidades 2022-2025
  python run_scrape.py --route MUNICIPALIDADES --years 2022 2023 2024 2025

  # Scrapear sectores sin filtro de padrón
  python run_scrape.py --route SECTORES --years 2024 --no-padron

  # Debug: solo 2 items por nivel
  python run_scrape.py --route GOBIERNOS_REGIONALES --years 2024 --max-items 2

  # Forzar re-scrape (ignorar checkpoints)
  python run_scrape.py --route MUNICIPALIDADES --years 2024 --no-resume
        """,
    )
    parser.add_argument("--route", required=True, choices=list(ROUTES.keys()),
                        help="Ruta a scrapear")
    parser.add_argument("--years", nargs="*", default=[],
                        help="Años a procesar (ej: 2022 2023 2024 2025)")
    parser.add_argument("--padron", default=str(PADRON_DIR / "padron_largo.csv"),
                        help="Ruta al CSV del padrón")
    parser.add_argument("--no-padron", action="store_true",
                        help="No filtrar por padrón (extraer todo)")
    parser.add_argument("--siga-no", action="store_true",
                        help="Filtrar por SIGA=NO en lugar de SIGA=SI")
    parser.add_argument("--max-items", type=int, default=None,
                        help="Limitar items por nivel (para debug)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignorar checkpoints y forzar re-scrape")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directorio de salida (default: outputs/raw)")
    args = parser.parse_args()

    years = parse_years(args.years) if args.years else []
    if not years:
        print("ERROR: Debes indicar --years")
        return 1

    # Configurar logger con sufijo del año (si es un solo año)
    log_suffix = f"_{years[0]}" if len(years) == 1 else ""
    logger = setup_logging("run_scrape", suffix=log_suffix)

    # Determinar filtro SIGA
    siga_filter = "NO" if args.siga_no else "SI"

    logger.info("=" * 60)
    logger.info("Configuración:")
    logger.info("  Ruta: %s", args.route)
    logger.info("  Años: %s", years)
    logger.info("  Padrón: %s", "Desactivado" if args.no_padron else args.padron)
    logger.info("  Filtro SIGA: %s", "Desactivado" if args.no_padron else siga_filter)
    logger.info("  Resume: %s", "No" if args.no_resume else "Sí")
    logger.info("=" * 60)

    padron_index = None
    category = None
    if not args.no_padron:
        padron_path = Path(args.padron)
        if not padron_path.exists():
            logger.error("No existe el padrón: %s", padron_path)
            logger.error("Ejecuta primero: python padron_export.py")
            return 1
        rows = load_padron_csv(padron_path)
        padron_index = build_index(rows, siga_filter=siga_filter)
        category = CATEGORY_BY_ROUTE[args.route]

        # Mostrar resumen del padrón
        for year in years:
            year_data = padron_index.get(year, {})
            cat_count = len(year_data.get(category, set()))
            all_count = len(year_data.get("_all", set()))
            logger.info("  Padrón %d: %d UEs en '%s' (%d total SIGA=%s)", year, cat_count, category, all_count, siga_filter)

    output_dir = Path(args.output_dir) if args.output_dir else RAW_DIR

    # Sufijo para el log (si es un solo año, usar ese año)
    log_suffix = f"_{years[0]}" if len(years) == 1 else ""

    try:
        run_scrape(
            route_name=args.route,
            years=years,
            output_dir=output_dir,
            padron_index=padron_index,
            category=category,
            max_items=args.max_items,
            resume=not args.no_resume,
            log_suffix=log_suffix,
        )
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrumpido por usuario (Ctrl+C)")
        return 130
    except Exception as e:
        logger.exception("Error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
