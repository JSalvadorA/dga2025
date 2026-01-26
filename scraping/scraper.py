from __future__ import annotations

import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from config import (
    GLOBAL_SELECTORS,
    URL,
    CHROMEDRIVER_PATH,
    HEADLESS,
    CHECKPOINT_DIR,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    PAGE_LOAD_TIMEOUT,
    ELEMENT_TIMEOUT,
    MIN_SLEEP_BETWEEN_REQUESTS,
    setup_logging,
)
from routes import FILE_CONFIGS, ROUTES
from utils import ensure_dirs

# Logger global (se reconfigura en run_scrape con sufijo de año)
logger = None


def _get_logger(suffix: str = ""):
    """Obtiene o crea logger con sufijo opcional."""
    global logger
    if logger is None:
        logger = setup_logging("scraper", suffix=suffix)
    return logger


def _sleep_random(base: float = MIN_SLEEP_BETWEEN_REQUESTS) -> None:
    """Sleep con jitter para evitar detección."""
    delay = base + random.uniform(0.5, 1.5)
    time.sleep(delay)


def _retry_on_failure(func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Ejecuta función con retry y backoff exponencial."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (TimeoutException, WebDriverException, StaleElementReferenceException) as e:
            last_exception = e
            delay = RETRY_DELAY_BASE * (2 ** attempt)
            logger.warning(
                "Intento %d/%d falló: %s. Reintentando en %ds...",
                attempt + 1, max_retries, str(e)[:100], delay
            )
            time.sleep(delay)
    logger.error("Todos los intentos fallaron. Última excepción: %s", last_exception)
    raise last_exception


class Scraper:
    def __init__(
        self,
        *,
        headless: bool = False,
        driver_path: Optional[str] = None,
        max_items: Optional[int] = None,
    ):
        self.headless = headless
        self.driver_path = driver_path
        self.max_items = max_items
        self.driver = self._initialize_driver()
        logger.info("Scraper inicializado (headless=%s)", headless)

    def _initialize_driver(self) -> webdriver.Chrome:
        if self.driver_path:
            service = Service(executable_path=self.driver_path)
        else:
            service = Service()
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if self.headless:
            options.add_argument("--headless=new")
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    def close(self) -> None:
        if self.driver:
            self.driver.quit()
            logger.info("Driver cerrado")

    def navigate_to_url(self, url: str) -> None:
        logger.debug("Navegando a: %s", url)
        _retry_on_failure(self.driver.get, url)
        self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])

    def switch_to_frame(self, frame_name: str, timeout: int = ELEMENT_TIMEOUT) -> None:
        self.driver.switch_to.default_content()
        WebDriverWait(self.driver, timeout).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, frame_name))
        )
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

    def click_on_element(self, element_id: str, retries: int = MAX_RETRIES) -> None:
        for attempt in range(retries):
            try:
                element = WebDriverWait(self.driver, ELEMENT_TIMEOUT).until(
                    EC.element_to_be_clickable((By.ID, element_id))
                )
                element.click()
                return
            except StaleElementReferenceException:
                if attempt == retries - 1:
                    raise
                _sleep_random(0.5)

    def click_by_text(self, text: str, retries: int = MAX_RETRIES) -> None:
        """Hace clic en un elemento de tabla que contenga el texto especificado."""
        # XPath que busca celdas TD en tabla Data que contengan el texto
        xpath = f"//table[@class='Data']//td[contains(text(), '{text}')]"
        for attempt in range(retries):
            try:
                element = WebDriverWait(self.driver, ELEMENT_TIMEOUT).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                logger.debug("Encontrado elemento por texto '%s': %s", text, element.get_attribute("id"))
                element.click()
                return
            except StaleElementReferenceException:
                if attempt == retries - 1:
                    raise
                _sleep_random(0.5)
            except TimeoutException:
                if attempt == retries - 1:
                    logger.error("No se encontró elemento con texto '%s' (xpath: %s)", text, xpath)
                    raise
                _sleep_random(1.0)

    def select_dropdown_option(self, element_id: str, option_value: str | int, retries: int = MAX_RETRIES) -> None:
        for attempt in range(retries):
            try:
                select_element = WebDriverWait(self.driver, ELEMENT_TIMEOUT).until(
                    EC.element_to_be_clickable((By.ID, element_id))
                )
                select = Select(select_element)
                select.select_by_value(str(option_value))
                return
            except StaleElementReferenceException:
                if attempt == retries - 1:
                    raise
                _sleep_random(0.5)

    def extract_table_data(self) -> List[List[str]]:
        rows = []
        filas = self.driver.find_elements(By.CSS_SELECTOR, "table.Data tr[id^='tr']")
        for fila in filas:
            cells = fila.find_elements(By.TAG_NAME, "td")[1:]
            values = [cell.text.strip() for cell in cells]
            if values:
                rows.append(values)
        return rows

    def get_final_headers(self, table_id: str) -> List[str]:
        tabla = self.driver.find_element(By.ID, table_id)
        fila_superior = tabla.find_elements(By.XPATH, ".//tr[1]/td | .//tr[1]/th")
        fila_inferior = tabla.find_elements(By.XPATH, ".//tr[2]/td | .//tr[2]/th")
        headers: List[str] = []
        idx_inferior = 0

        for i, celda in enumerate(fila_superior):
            if i == 0 and not celda.text.strip():
                continue
            colspan = celda.get_attribute("colspan")
            if colspan:
                for _ in range(int(colspan)):
                    headers.append(fila_inferior[idx_inferior].text.strip())
                    idx_inferior += 1
            else:
                headers.append(celda.text.strip())
        return headers

    def navigate_levels(
        self,
        route_config: Dict[str, Dict],
        current_level: str,
        table_headers: List[str],
        context: Optional[Dict[str, str]] = None,
        context_order: Optional[List[str]] = None,
    ) -> List[List[str]]:
        if context is None:
            context = {}
        if context_order is None:
            context_order = []

        extracted: List[List[str]] = []
        level_config = route_config["levels"][current_level]
        button = level_config.get("button")
        button_text = level_config.get("button_text")
        list_xpath = level_config.get("list_xpath")
        name_xpath = level_config.get("name_xpath")
        next_level = level_config.get("next_level")
        table_id = level_config.get("table_id")

        # Priorizar selección por texto sobre ID
        if button_text:
            self.click_by_text(button_text)
            self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
            _sleep_random()
        elif button:
            self.click_on_element(button)
            self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
            _sleep_random()

        if list_xpath:
            elements = self.driver.find_elements(By.XPATH, list_xpath)
            limit = len(elements) if self.max_items is None else min(len(elements), self.max_items)
            logger.debug("Nivel %s: %d elementos encontrados (procesando %d)", current_level, len(elements), limit)

            for i in range(limit):
                try:
                    elements = self.driver.find_elements(By.XPATH, list_xpath)
                    element = elements[i]
                    element_name = element.find_element(By.XPATH, name_xpath).text.strip()
                    context[current_level] = element_name
                    if current_level not in context_order:
                        context_order.append(current_level)

                    logger.info("  [%s] %d/%d: %s", current_level, i + 1, limit, element_name)

                    self.click_on_element(f"tr{i}")
                    self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
                    _sleep_random()

                    if next_level:
                        extracted.extend(
                            self.navigate_levels(
                                route_config,
                                next_level,
                                table_headers,
                                context,
                                context_order,
                            )
                        )

                    self.driver.back()
                    self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
                    _sleep_random()

                except Exception as e:
                    logger.error("Error en elemento %d (%s): %s", i, context.get(current_level, "?"), e)
                    # Intentar recuperar
                    try:
                        self.driver.back()
                        self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
                    except Exception:
                        pass
                    continue
        else:
            if next_level:
                extracted.extend(
                    self.navigate_levels(
                        route_config,
                        next_level,
                        table_headers,
                        context,
                        context_order,
                    )
                )
            else:
                if table_id:
                    if not table_headers:
                        table_headers.extend(self.get_final_headers(table_id))
                    table_data = self.extract_table_data()
                    for row in table_data:
                        ordered_context = [context[level] for level in context_order]
                        extracted.append(ordered_context + row)
        return extracted

    def extract_data_by_year(self, year: int, route_name: str, table_headers: List[str]) -> List[List[str]]:
        logger.info("Extrayendo año %d, ruta %s", year, route_name)
        self.select_dropdown_option(GLOBAL_SELECTORS["year_dropdown"], year)
        self.switch_to_frame(GLOBAL_SELECTORS["main_frame"])
        _sleep_random()

        route_config = ROUTES[route_name]
        first_level = min(route_config["levels"].keys(), key=lambda lvl: int(lvl.split("_")[1]))
        data = self.navigate_levels(route_config, first_level, table_headers)
        logger.info("Año %d: %d filas extraídas", year, len(data))
        return [[year] + row for row in data]


def _find_header_index(headers: List[str], patterns: List[str]) -> Optional[int]:
    for idx, header in enumerate(headers):
        text = header.strip().upper()
        for pat in patterns:
            if pat in text:
                return idx
    return None


def extract_sec_ejec_from_text(text: str, padron_set: Optional[set[str]] = None) -> str:
    """Extrae SEC_EJEC de texto, priorizando matches contra padrón."""
    if not text:
        return ""
    # Buscar patrones de 3-6 dígitos (SEC_EJEC típico)
    tokens = re.findall(r"\b(\d{3,6})\b", text)
    if padron_set:
        for tok in tokens:
            if tok in padron_set:
                return tok
    if tokens:
        # Preferir el más largo si no hay match en padrón
        return max(tokens, key=len)
    return ""


def extract_sec_ejec(route_name: str, headers: List[str], row: List[str], padron_set: Optional[set[str]]) -> str:
    if route_name == "MUNICIPALIDADES":
        idx = _find_header_index(headers, ["MUNICIPALIDAD"])
    else:
        idx = _find_header_index(headers, ["UNIDAD EJECUTORA"])

    if idx is None or idx >= len(row):
        return ""
    return extract_sec_ejec_from_text(row[idx], padron_set)


def save_csv(path: Path, headers: List[str], rows: List[List[str]]) -> None:
    ensure_dirs(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    logger.info("CSV guardado: %s (%d filas)", path.name, len(rows))


# =============================================================================
# CHECKPOINT FUNCTIONS
# =============================================================================

def _checkpoint_path(route_name: str, year: int) -> Path:
    ensure_dirs(CHECKPOINT_DIR)
    return CHECKPOINT_DIR / f"checkpoint_{route_name}_{year}.json"


def load_checkpoint(route_name: str, year: int) -> Optional[Dict]:
    """Carga checkpoint si existe."""
    path = _checkpoint_path(route_name, year)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info("Checkpoint cargado: %s (filas=%d)", path.name, len(data.get("rows", [])))
            return data
    return None


def save_checkpoint(route_name: str, year: int, headers: List[str], rows: List[List[str]], completed: bool = False) -> None:
    """Guarda checkpoint."""
    path = _checkpoint_path(route_name, year)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"headers": headers, "rows": rows, "completed": completed}, f)
    logger.debug("Checkpoint guardado: %s", path.name)


def clear_checkpoint(route_name: str, year: int) -> None:
    """Elimina checkpoint después de completar."""
    path = _checkpoint_path(route_name, year)
    if path.exists():
        path.unlink()
        logger.debug("Checkpoint eliminado: %s", path.name)


# =============================================================================
# MAIN SCRAPE FUNCTION
# =============================================================================

def run_scrape(
    *,
    route_name: str,
    years: List[int],
    output_dir: Path,
    padron_index: Optional[Dict[int, Dict[str, set[str]]]] = None,
    category: Optional[str] = None,
    max_items: Optional[int] = None,
    resume: bool = True,
    log_suffix: str = "",
) -> None:
    """
    Ejecuta scraping para una ruta y años especificados.

    Args:
        route_name: Nombre de la ruta (MUNICIPALIDADES, SECTORES, GOBIERNOS_REGIONALES)
        years: Lista de años a scrapear
        output_dir: Directorio de salida
        padron_index: Índice de padrón para filtrar
        category: Categoría para filtrar en padrón
        max_items: Limitar items por nivel (debug)
        resume: Si True, intenta resumir desde checkpoint
        log_suffix: Sufijo para el logger (ej: "_2024")
    """
    global logger
    logger = setup_logging("scraper", suffix=log_suffix)

    logger.info("=" * 60)
    logger.info("Iniciando scrape: %s | años=%s", route_name, years)
    logger.info("=" * 60)

    scraper = Scraper(headless=HEADLESS, driver_path=CHROMEDRIVER_PATH, max_items=max_items)
    try:
        scraper.navigate_to_url(URL)

        for year in years:
            logger.info("-" * 40)
            logger.info("Procesando año %d", year)

            # Verificar checkpoint
            checkpoint = load_checkpoint(route_name, year) if resume else None
            if checkpoint and checkpoint.get("completed"):
                logger.info("Año %d ya completado (checkpoint). Saltando.", year)
                continue

            table_headers: List[str] = []
            rows = scraper.extract_data_by_year(year, route_name, table_headers)

            base_headers = FILE_CONFIGS[route_name]["ENCABEZADOS_BASE"]
            full_headers = base_headers + table_headers

            # Filtrar por padrón si aplica
            sec_set = None
            if padron_index and category:
                sec_set = padron_index.get(year, {}).get(category)
                if sec_set:
                    logger.info("Filtrando por padrón: %d UEs en categoría '%s'", len(sec_set), category)

            if sec_set:
                filtered: List[List[str]] = []
                for row in rows:
                    sec = extract_sec_ejec(route_name, table_headers, row[len(base_headers):], sec_set)
                    if sec and sec in sec_set:
                        filtered.append(row + [sec])
                logger.info("Filtrado: %d -> %d filas", len(rows), len(filtered))
                rows = filtered
                full_headers = full_headers + ["SEC_EJEC_EXTRACTED"]

            # Guardar resultado
            out_path = output_dir / f"{route_name}_{year}.csv"
            save_csv(out_path, full_headers, rows)

            # Marcar completado
            save_checkpoint(route_name, year, full_headers, rows, completed=True)

    except Exception as e:
        logger.exception("Error fatal en scrape: %s", e)
        raise
    finally:
        scraper.close()

    logger.info("=" * 60)
    logger.info("Scrape completado")
    logger.info("=" * 60)
