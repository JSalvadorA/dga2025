from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable

from utils import normalize_sec_ejec


def load_padron_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sec = normalize_sec_ejec(row.get("sec_ejec", ""))
            row["sec_ejec"] = sec
            rows.append(row)
    return rows


def build_index(
    rows: Iterable[dict[str, str]],
    only_siga_si: bool = True,
    siga_filter: str | None = None,
) -> Dict[int, Dict[str, set[str]]]:
    """
    Construye índice de SEC_EJEC por año y categoría.

    Args:
        rows: Filas del padrón con campos sec_ejec, anio, siga_implementado, categoria
        only_siga_si: Si True, solo incluye UEs con SIGA=SI (default: True). Ignorado si siga_filter está definido.
        siga_filter: Filtro explícito: "SI", "NO", o None (sin filtro). Tiene prioridad sobre only_siga_si.

    Returns:
        Dict[año, Dict[categoría, set[sec_ejec]]]
    """
    index: Dict[int, Dict[str, set[str]]] = {}
    for row in rows:
        sec = normalize_sec_ejec(row.get("sec_ejec", ""))
        if not sec:
            continue
        try:
            year = int(row.get("anio", ""))
        except ValueError:
            continue

        # Filtrar por SIGA implementado
        siga = (row.get("siga_implementado", "") or "").strip().upper()

        # siga_filter tiene prioridad sobre only_siga_si
        if siga_filter is not None:
            if siga != siga_filter.upper():
                continue
        elif only_siga_si and siga != "SI":
            continue

        category = (row.get("categoria", "") or "").strip()
        year_map = index.setdefault(year, {})
        year_map.setdefault("_all", set()).add(sec)
        if category:
            year_map.setdefault(category, set()).add(sec)
    return index
