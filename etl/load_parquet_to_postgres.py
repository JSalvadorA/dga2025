from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import psycopg
from dotenv import dotenv_values
from psycopg import sql


@dataclass(frozen=True)
class PgTarget:
    schema: str
    table: str


def _repo_root() -> Path:
    # db/postgres/etl/load_parquet_to_postgres.py -> repo root is 3 levels up
    return Path(__file__).resolve().parents[3]


def _load_compose_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return {}
    values = dotenv_values(env_path)
    return {str(k): str(v) for k, v in values.items() if v is not None}


def _parse_target(value: str) -> PgTarget:
    if "." not in value:
        raise ValueError("Formato esperado: schema.tabla (ej: raw.cmn_mef)")
    schema, table = value.split(".", 1)
    schema = schema.strip()
    table = table.strip()
    if not schema or not table:
        raise ValueError("Formato esperado: schema.tabla (ej: raw.cmn_mef)")
    return PgTarget(schema=schema, table=table)


def _resolve_dataset_path_and_table(dataset: str, year: int) -> tuple[Path, PgTarget, int | None]:
    root = _repo_root()
    dataset = dataset.lower().strip()

    if dataset == "cmn_mef":
        if year in (2022, 2023, 2024):
            return (
                root / f"ind22_26/parquet_by_year/CMN_SIGA_MEF_{year}.parquet",
                PgTarget(schema="raw", table="cmn_mef"),
                year,
            )
        if year == 2025:
            return (
                root / "ind22_26/parquet_by_year_siaf_rp_2025/CMN_SIGA_MEF_2025_v2.parquet",
                PgTarget(schema="raw", table="cmn_mef"),
                year,
            )
        raise ValueError("cmn_mef: year debe ser 2022-2025")

    if dataset == "cmn_mef_2025_v1":
        if year and year != 2025:
            raise ValueError("cmn_mef_2025_v1: year debe ser 2025")
        return (
            root / "ind22_26/parquet_by_year_siaf_rp_2025/CMN_SIGA_MEF_2025.parquet",
            PgTarget(schema="raw", table="cmn_mef_2025_v1"),
            None,
        )

    if dataset == "cmn_minedu":
        if year not in (2022, 2023, 2024, 2025):
            raise ValueError("cmn_minedu: year debe ser 2022-2025")
        return (
            root / f"ind22_26/parquet_cmn_minedu/cmn_minedu_{year}.parquet",
            PgTarget(schema="raw", table="cmn_minedu"),
            year,
        )

    raise ValueError("dataset inválido. Usa: cmn_mef | cmn_mef_2025_v1 | cmn_minedu")


def _connect(args: argparse.Namespace, compose_env: dict[str, str]) -> psycopg.Connection:
    host = args.host or os.getenv("PGHOST") or "localhost"
    port = int(args.port or os.getenv("PGPORT") or 5432)

    dbname = args.dbname or os.getenv("PGDATABASE") or compose_env.get("POSTGRES_DB") or "postgres"
    user = args.user or os.getenv("PGUSER") or compose_env.get("POSTGRES_USER") or "postgres"
    password = args.password or os.getenv("PGPASSWORD") or compose_env.get("POSTGRES_PASSWORD") or ""

    return psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password)


def _fetch_table_columns(cur: psycopg.Cursor, target: PgTarget) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (target.schema, target.table),
    )
    return [r[0] for r in cur.fetchall()]


def _truncate(cur: psycopg.Cursor, target: PgTarget, partition_year: int | None) -> None:
    if partition_year is None:
        cur.execute(
            sql.SQL("TRUNCATE TABLE {}.{}").format(
                sql.Identifier(target.schema),
                sql.Identifier(target.table),
            )
        )
        return

    partition = f"{target.table}_{partition_year}"
    cur.execute(
        sql.SQL("TRUNCATE TABLE {}.{}").format(
            sql.Identifier(target.schema),
            sql.Identifier(partition),
        )
    )


def _try_ingestion_log_start(
    conn: psycopg.Connection,
    *,
    dataset: str,
    source_path: str,
    year: int | None,
    notes: str | None = None,
) -> int | None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.ingestion_log (dataset, source_path, year, status, notes)
                VALUES (%s, %s, %s, 'started', %s)
                RETURNING ingestion_id
                """,
                (dataset, source_path, year, notes),
            )
            ingestion_id = cur.fetchone()[0]
        conn.commit()
        return int(ingestion_id)
    except Exception as exc:
        conn.rollback()
        print(f"[WARN] No pude registrar raw.ingestion_log (start): {exc}", file=sys.stderr)
        return None


def _try_ingestion_log_finish(
    conn: psycopg.Connection,
    *,
    ingestion_id: int | None,
    status: str,
    rows_loaded: int | None,
    notes: str | None = None,
) -> None:
    if ingestion_id is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE raw.ingestion_log
                SET finished_at = now(),
                    status = %s,
                    rows_loaded = %s,
                    notes = %s
                WHERE ingestion_id = %s
                """,
                (status, rows_loaded, notes, ingestion_id),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[WARN] No pude actualizar raw.ingestion_log ({status}): {exc}", file=sys.stderr)


def _run_copy(
    conn: psycopg.Connection,
    parquet_path: Path,
    target: PgTarget,
    batch_size: int,
    analyze: bool,
    only_columns: list[str],
) -> int:
    parquet_schema = pq.read_schema(parquet_path)
    parquet_cols = parquet_schema.names
    parquet_cols_lc = {c.lower(): c for c in parquet_cols}

    with conn.cursor() as cur:
        pg_cols = _fetch_table_columns(cur, target)
        pg_cols_lc = {c.lower(): c for c in pg_cols}

        if only_columns:
            requested_lc = [c.strip().lower() for c in only_columns if c.strip()]
            missing_in_pg = [c for c in requested_lc if c not in pg_cols_lc]
            if missing_in_pg:
                raise RuntimeError(
                    "Requested columns not in target "
                    f"{target.schema}.{target.table}: {', '.join(sorted(set(missing_in_pg)))}"
                )

            missing_in_parquet = [c for c in requested_lc if c not in parquet_cols_lc]
            if missing_in_parquet:
                raise RuntimeError(
                    "Requested columns not in parquet "
                    f"{parquet_path.name}: {', '.join(sorted(set(missing_in_parquet)))}"
                )

            copy_cols = [pg_cols_lc[c] for c in requested_lc]
        else:
            copy_cols = [c for c in pg_cols if c.lower() in parquet_cols_lc]
        if not copy_cols:
            raise RuntimeError(
                f"No hay columnas en común entre {target.schema}.{target.table} y {parquet_path.name}"
            )

        parquet_select_cols = [parquet_cols_lc[c.lower()] for c in copy_cols]

        copy_stmt = sql.SQL(
            "COPY {}.{} ({}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t')"
        ).format(
            sql.Identifier(target.schema),
            sql.Identifier(target.table),
            sql.SQL(", ").join(sql.Identifier(c) for c in copy_cols),
        )

        write_opts = pacsv.WriteOptions(include_header=False, quoting_style="needed", delimiter="\t")
        total_rows = 0
        t0 = time.time()

        cur.execute("SET statement_timeout = 0;")

        pf = pq.ParquetFile(parquet_path)
        with cur.copy(copy_stmt) as copy:
            for batch in pf.iter_batches(batch_size=batch_size, columns=parquet_select_cols):
                table = pa.Table.from_batches([batch])
                out = pa.BufferOutputStream()
                pacsv.write_csv(table, out, write_options=write_opts)
                copy.write(out.getvalue().to_pybytes())

                total_rows += batch.num_rows
                if total_rows and total_rows % 1_000_000 == 0:
                    elapsed = time.time() - t0
                    rate = int(total_rows / max(elapsed, 0.001))
                    print(f"  ... {total_rows:,} filas | ~{rate:,} filas/s", file=sys.stderr)

        if analyze:
            cur.execute(
                sql.SQL("ANALYZE {}.{}").format(
                    sql.Identifier(target.schema),
                    sql.Identifier(target.table),
                )
            )

    return total_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga incremental Parquet -> Postgres usando COPY (streaming por batches)."
    )

    # Conveniencia (recomendado para este repo)
    parser.add_argument(
        "--dataset",
        choices=["cmn_mef", "cmn_mef_2025_v1", "cmn_minedu"],
        help="Dataset con rutas default del repo (usa --year).",
    )
    parser.add_argument("--year", type=int, default=0, help="Anio (ej: 2022).")

    # Modo genérico
    parser.add_argument("--file", type=str, default="", help="Ruta al .parquet (override).")
    parser.add_argument("--table", type=str, default="", help="Destino schema.tabla (override).")

    # Conexión (host script -> Postgres expuesto por docker compose)
    parser.add_argument("--host", type=str, default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--dbname", type=str, default="")
    parser.add_argument("--user", type=str, default="")
    parser.add_argument("--password", type=str, default="")

    parser.add_argument("--batch-size", type=int, default=20_000)
    parser.add_argument(
        "--columns",
        type=str,
        default="",
        help="Comma-separated columns to load (smaller/faster).",
    )
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE antes de cargar (tabla o partición).")
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Ejecuta ANALYZE al terminar (útil antes de consultas pesadas).",
    )

    args = parser.parse_args()

    parquet_path: Path
    target: PgTarget
    partition_year: int | None

    if args.dataset:
        year = int(args.year or 0)
        if args.dataset != "cmn_mef_2025_v1" and not year:
            raise SystemExit("--dataset requiere --year (excepto cmn_mef_2025_v1)")
        parquet_path, target, partition_year = _resolve_dataset_path_and_table(args.dataset, year)
    else:
        if not args.file or not args.table:
            raise SystemExit("Usa --dataset/--year o, en modo genérico, --file y --table.")
        parquet_path = Path(args.file).expanduser().resolve()
        target = _parse_target(args.table)
        partition_year = int(args.year) if args.year else None

    if not parquet_path.exists():
        raise SystemExit(f"No existe: {parquet_path}")

    compose_env = _load_compose_env()
    with _connect(args, compose_env) as conn:
        with conn.cursor() as cur:
            if args.truncate:
                _truncate(cur, target, partition_year)
        conn.commit()

        dataset_label = args.dataset or f"{target.schema}.{target.table}"
        log_year: int | None = None
        if args.dataset == "cmn_mef_2025_v1":
            log_year = 2025
        elif partition_year is not None:
            log_year = int(partition_year)
        elif int(args.year or 0) > 0:
            log_year = int(args.year)

        ingestion_id = _try_ingestion_log_start(
            conn,
            dataset=dataset_label,
            source_path=str(parquet_path),
            year=log_year,
            notes=f"target={target.schema}.{target.table}",
        )

        print(f"[START] {parquet_path.name} -> {target.schema}.{target.table}", file=sys.stderr)
        try:
            only_columns = [c.strip() for c in (args.columns or "").split(",") if c.strip()]
            rows = _run_copy(
                conn,
                parquet_path=parquet_path,
                target=target,
                batch_size=int(args.batch_size),
                analyze=bool(args.analyze),
                only_columns=only_columns,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            _try_ingestion_log_finish(
                conn,
                ingestion_id=ingestion_id,
                status="failed",
                rows_loaded=None,
                notes=str(exc),
            )
            raise

        _try_ingestion_log_finish(
            conn,
            ingestion_id=ingestion_id,
            status="success",
            rows_loaded=rows,
        )
        print(f"[OK] filas cargadas: {rows:,}", file=sys.stderr)


if __name__ == "__main__":
    main()
