from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

SCRAPEO_DIR = Path(__file__).resolve().parent
IND22_DIR = SCRAPEO_DIR.parent
DGA_ROOT = IND22_DIR.parent

OUTPUT_DIR = SCRAPEO_DIR / "outputs"
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"
PADRON_DIR = OUTPUT_DIR / "padron"
LOG_DIR = OUTPUT_DIR / "logs"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"

URL = "https://apps5.mineco.gob.pe/transparencia/mensual/"

GLOBAL_SELECTORS = {
    "year_dropdown": "ctl00_CPH1_DrpYear",
    "main_frame": "frame0",
}

DEFAULT_YEARS = [2022, 2023, 2024, 2025]

CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
HEADLESS = os.getenv("SCRAPEO_HEADLESS", "0") == "1"

DB_ENV_PATH = DGA_ROOT / "db" / "postgres" / ".env"

# Configuración de retry
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # segundos (backoff exponencial: 2, 4, 8)
PAGE_LOAD_TIMEOUT = 30  # segundos
ELEMENT_TIMEOUT = 15  # segundos
MIN_SLEEP_BETWEEN_REQUESTS = 2  # segundos mínimo entre requests


def setup_logging(name: str = "scraper", suffix: str = "") -> logging.Logger:
    """
    Configura logging a consola y archivo.

    Args:
        name: Nombre del logger
        suffix: Sufijo para el archivo (ej: "_2024" para diferenciar por año)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Nombre único del logger y archivo
    logger_name = f"{name}{suffix}"
    log_file = LOG_DIR / f"{timestamp}_{logger_name}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger

    # Handler consola (menos verbose para paralelo)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(f"%(asctime)s | {suffix or name} | %(message)s", "%H:%M:%S")
    console_handler.setFormatter(console_fmt)

    # Handler archivo
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Log iniciado: %s", log_file)
    return logger
