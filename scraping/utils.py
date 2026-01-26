from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def normalize_sec_ejec(value: str | int | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9]", "", text)
    return text


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def parse_years(values: Iterable[str]) -> list[int]:
    years: list[int] = []
    for item in values:
        item = str(item).strip()
        if not item:
            continue
        years.append(int(item))
    return years
