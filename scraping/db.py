from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

try:
    import psycopg
except Exception:
    psycopg = None

try:
    import psycopg2
except Exception:
    psycopg2 = None

from config import DB_ENV_PATH


def _load_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values = dotenv_values(env_path)
    return {str(k): str(v) for k, v in values.items() if v is not None}


def connect():
    env = _load_env(DB_ENV_PATH)
    host = env.get("PGHOST", "localhost")
    port = int(env.get("PGPORT", 5432))
    dbname = env.get("POSTGRES_DB", "postgres")
    user = env.get("POSTGRES_USER", "postgres")
    password = env.get("POSTGRES_PASSWORD", "")

    if psycopg is not None:
        conn = psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        return conn
    if psycopg2 is not None:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        return conn

    raise SystemExit("No encontro psycopg ni psycopg2 en el entorno.")
