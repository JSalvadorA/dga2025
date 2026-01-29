from __future__ import annotations

import csv
from pathlib import Path

from config import PADRON_DIR
from db import connect
from utils import ensure_dirs, normalize_sec_ejec


def fetch_padron_historico(cur):
    cur.execute(
        """
        SELECT sec_ejec, nombre_ejecutora, region, provincia, distrito, categoria,
               ano_2022, ano_2023, ano_2024
        FROM raw.padron_historico
        """
    )
    return cur.fetchall()


def fetch_padron_2025(cur):
    cur.execute(
        """
        SELECT sec_ejec, nombre_ejecutora, region, provincia, distrito, categoria
        FROM raw.padron_nov2025
        """
    )
    return cur.fetchall()


def main() -> None:
    ensure_dirs(PADRON_DIR)
    out_path = PADRON_DIR / "padron_largo.csv"

    conn = connect()
    try:
        with conn.cursor() as cur:
            hist_rows = fetch_padron_historico(cur)
            rows_2025 = fetch_padron_2025(cur)
    finally:
        conn.close()

    fields = [
        "sec_ejec",
        "anio",
        "siga_implementado",
        "categoria",
        "nombre_ejecutora",
        "region",
        "provincia",
        "distrito",
        "fuente_padron",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for row in hist_rows:
            (
                sec_ejec,
                nombre_ejecutora,
                region,
                provincia,
                distrito,
                categoria,
                ano_2022,
                ano_2023,
                ano_2024,
            ) = row

            sec_norm = normalize_sec_ejec(sec_ejec)
            if not sec_norm:
                continue

            for year, status in ((2022, ano_2022), (2023, ano_2023), (2024, ano_2024)):
                status_norm = (str(status).strip().upper() if status is not None else "")
                if not status_norm:
                    continue
                writer.writerow(
                    {
                        "sec_ejec": sec_norm,
                        "anio": year,
                        "siga_implementado": status_norm,
                        "categoria": (categoria or "").strip(),
                        "nombre_ejecutora": (nombre_ejecutora or "").strip(),
                        "region": (region or "").strip(),
                        "provincia": (provincia or "").strip(),
                        "distrito": (distrito or "").strip(),
                        "fuente_padron": "padron_historico",
                    }
                )

        for row in rows_2025:
            sec_ejec, nombre_ejecutora, region, provincia, distrito, categoria = row
            sec_norm = normalize_sec_ejec(sec_ejec)
            if not sec_norm:
                continue
            writer.writerow(
                {
                    "sec_ejec": sec_norm,
                    "anio": 2025,
                    "siga_implementado": "SI",
                    "categoria": (categoria or "").strip(),
                    "nombre_ejecutora": (nombre_ejecutora or "").strip(),
                    "region": (region or "").strip(),
                    "provincia": (provincia or "").strip(),
                    "distrito": (distrito or "").strip(),
                    "fuente_padron": "padron_nov2025",
                }
            )

    print(f"[OK] padron exportado: {out_path}")


if __name__ == "__main__":
    main()
