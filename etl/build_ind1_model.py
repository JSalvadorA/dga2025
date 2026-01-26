from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

try:
    import psycopg  # psycopg v3
except Exception:
    psycopg = None

try:
    import psycopg2  # psycopg2-binary
except Exception:
    psycopg2 = None


def _load_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return {}
    values = dotenv_values(env_path)
    return {str(k): str(v) for k, v in values.items() if v is not None}


def _connect(
    *,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
):
    if psycopg is not None:
        conn = psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        return conn, conn.cursor()
    if psycopg2 is not None:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        return conn, conn.cursor()
    raise SystemExit("No encontro psycopg ni psycopg2 en el entorno.")


def _split_sql(sql_text: str) -> list[str]:
    return [stmt.strip() for stmt in sql_text.split(";") if stmt.strip()]


DDL = r"""
CREATE SCHEMA IF NOT EXISTS dwh_ind1;
CREATE SCHEMA IF NOT EXISTS mart_ind1;

DROP TABLE IF EXISTS dwh_ind1.dim_tiempo;
CREATE UNLOGGED TABLE dwh_ind1.dim_tiempo AS
SELECT DISTINCT anio
FROM (
  SELECT ano_eje::int AS anio FROM raw.cmn_mef WHERE ano_eje <= 2024
  UNION
  SELECT COALESCE(ano_eje, anno)::int AS anio
  FROM raw.cmn_mef_2025_v1
  WHERE COALESCE(ano_eje, anno) = 2025
  UNION
  SELECT ano_eje::int AS anio FROM raw.cmn_minedu
  UNION
  SELECT 2025::int AS anio WHERE EXISTS (SELECT 1 FROM raw.padron_nov2025)
) t
ORDER BY 1;

DROP TABLE IF EXISTS dwh_ind1.dim_fase;
CREATE UNLOGGED TABLE dwh_ind1.dim_fase (
  fase_codigo smallint PRIMARY KEY,
  fase_nombre text NOT NULL
);
INSERT INTO dwh_ind1.dim_fase (fase_codigo, fase_nombre) VALUES
(1, 'IDENTIFICACION'),
(2, 'CLASIFICACION Y PRIORIZACION'),
(3, 'CONSOLIDACION Y APROBACION');

DROP TABLE IF EXISTS dwh_ind1.dim_fuente;
CREATE UNLOGGED TABLE dwh_ind1.dim_fuente (
  fuente text PRIMARY KEY
);
INSERT INTO dwh_ind1.dim_fuente (fuente) VALUES ('MEF'), ('MINEDU');

DROP TABLE IF EXISTS dwh_ind1.dim_ue;
CREATE UNLOGGED TABLE dwh_ind1.dim_ue AS
WITH padron AS (
  SELECT
    regexp_replace(coalesce(sec_ejec,''), '\D', '', 'g') AS sec_ejec,
    nullif(trim(nombre_ejecutora),'') AS nombre_ejecutora,
    nullif(trim(region),'') AS region
  FROM raw.padron_historico
  UNION ALL
  SELECT
    regexp_replace(coalesce(sec_ejec,''), '\D', '', 'g'),
    nullif(trim(nombre_ejecutora),''),
    nullif(trim(region),'')
  FROM raw.padron_nov2025
),
cmn AS (
  SELECT
    regexp_replace(coalesce(sec_ejec,''), '\D', '', 'g') AS sec_ejec,
    nullif(trim(ejecutora_dsc),'') AS nombre_ejecutora,
    nullif(trim(region),'') AS region
  FROM raw.cmn_mef
  WHERE ano_eje <= 2024
  UNION ALL
  SELECT
    regexp_replace(coalesce(sec_ejec,''), '\D', '', 'g'),
    nullif(trim(ejecutora_nombre), ''),
    nullif(trim(region), '')
  FROM raw.cmn_mef_2025_v1
  WHERE COALESCE(ano_eje, anno) = 2025
  UNION ALL
  SELECT
    regexp_replace(coalesce(sec_ejec,''), '\D', '', 'g'),
    nullif(trim(ejecutora_nombre),''),
    nullif(trim(region),'')
  FROM raw.cmn_minedu
),
u AS (
  SELECT * FROM padron
  UNION ALL
  SELECT * FROM cmn
)
SELECT
  sec_ejec,
  max(nombre_ejecutora) AS nombre_ejecutora,
  max(region) AS region
FROM u
WHERE sec_ejec <> ''
GROUP BY sec_ejec;

DROP TABLE IF EXISTS dwh_ind1.fact_cmn_fase;
CREATE UNLOGGED TABLE dwh_ind1.fact_cmn_fase AS
SELECT
  ano_eje::int AS anio,
  sec_ejec,
  fase_codigo,
  fuente,
  1::smallint AS flag_registro
FROM dwh_ind1.cmn_lite;

CREATE UNIQUE INDEX fact_cmn_fase_pk
  ON dwh_ind1.fact_cmn_fase (anio, sec_ejec, fase_codigo, fuente);

CREATE INDEX fact_cmn_fase_sec
  ON dwh_ind1.fact_cmn_fase (anio, sec_ejec);

CREATE INDEX dim_ue_sec
  ON dwh_ind1.dim_ue (sec_ejec);

ANALYZE dwh_ind1.dim_ue;
ANALYZE dwh_ind1.fact_cmn_fase;

CREATE OR REPLACE VIEW mart_ind1.indicador1_por_anio_variante AS
SELECT * FROM dwh_ind1.indicador1_por_anio_variante;
"""


def main() -> int:
    env = _load_env()
    host = os.getenv("PGHOST") or env.get("PGHOST") or "localhost"
    port = int(os.getenv("PGPORT") or env.get("PGPORT") or 5432)
    dbname = os.getenv("PGDATABASE") or env.get("POSTGRES_DB") or "postgres"
    user = os.getenv("PGUSER") or env.get("POSTGRES_USER") or "postgres"
    password = os.getenv("PGPASSWORD") or env.get("POSTGRES_PASSWORD") or ""

    conn, cur = _connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )

    try:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.views
            WHERE table_schema = 'dwh_ind1' AND table_name = 'cmn_lite'
            """
        )
        if cur.fetchone() is None:
            raise SystemExit("No existe dwh_ind1.cmn_lite. Ejecuta primero los SQL de vistas base.")

        cur.execute("SET statement_timeout = 0;")
        for stmt in _split_sql(DDL):
            cur.execute(stmt)

        print("[OK] Modelado Ind1 creado: dim_tiempo, dim_fase, dim_fuente, dim_ue, fact_cmn_fase, view mart.")
        return 0
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
