#!/usr/bin/env python
"""
Ejecuta scraping en paralelo por año.

Uso:
    python run_parallel.py --route MUNICIPALIDADES --years 2022 2023 2024 2025
    python run_parallel.py --route SECTORES --years 2022 2023 2024 2025 --workers 2
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from config import setup_logging, PADRON_DIR

# Logger único para el proceso principal
logger = setup_logging("parallel", suffix="_main")


def run_single_year(route: str, year: int, padron_path: str, no_padron: bool, siga_no: bool) -> tuple[int, int, str]:
    """Ejecuta scraping para un año específico en subproceso."""
    cmd = [
        sys.executable,
        "run_scrape.py",
        "--route", route,
        "--years", str(year),
    ]
    if no_padron:
        cmd.append("--no-padron")
    else:
        cmd.extend(["--padron", padron_path])
        if siga_no:
            cmd.append("--siga-no")

    logger.info("Iniciando año %d: %s", year, " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0:
            return year, 0, "OK"
        else:
            return year, result.returncode, result.stderr[-500:] if result.stderr else "Error desconocido"
    except Exception as e:
        return year, 1, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraping paralelo por año")
    parser.add_argument("--route", required=True, choices=["MUNICIPALIDADES", "SECTORES", "GOBIERNOS_REGIONALES"])
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--padron", default=str(PADRON_DIR / "padron_largo.csv"))
    parser.add_argument("--no-padron", action="store_true")
    parser.add_argument("--siga-no", action="store_true", help="Filtrar por SIGA=NO en lugar de SIGA=SI")
    parser.add_argument("--workers", type=int, default=None, help="Número de workers (default: número de años)")
    args = parser.parse_args()

    years = args.years
    workers = args.workers or len(years)

    siga_filter = "NO" if args.siga_no else "SI"

    logger.info("=" * 60)
    logger.info("Scraping paralelo")
    logger.info("  Ruta: %s", args.route)
    logger.info("  Años: %s", years)
    logger.info("  Filtro SIGA: %s", "Desactivado" if args.no_padron else siga_filter)
    logger.info("  Workers: %d", workers)
    logger.info("=" * 60)

    results = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(run_single_year, args.route, year, args.padron, args.no_padron, args.siga_no): year
            for year in years
        }

        for future in as_completed(futures):
            year = futures[future]
            try:
                yr, code, msg = future.result()
                results[yr] = (code, msg)
                if code == 0:
                    logger.info("[OK] Año %d completado", yr)
                else:
                    logger.error("[ERROR] Año %d: %s", yr, msg)
            except Exception as e:
                results[year] = (1, str(e))
                logger.exception("Excepción en año %d: %s", year, e)

    # Resumen
    logger.info("=" * 60)
    logger.info("RESUMEN")
    for year in sorted(results.keys()):
        code, msg = results[year]
        status = "OK" if code == 0 else f"ERROR ({code})"
        logger.info("  %d: %s", year, status)

    failed = sum(1 for code, _ in results.values() if code != 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
