-- Se ejecuta SOLO la primera vez que se inicializa el volumen de Postgres.
-- Si quieres re-ejecutar, debes borrar el volumen (pgdata) o usar otro volumen.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS dwh_ind1;
CREATE SCHEMA IF NOT EXISTS dwh_cl2;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS raw.ingestion_log (
  ingestion_id BIGSERIAL PRIMARY KEY,
  dataset TEXT NOT NULL,
  source_path TEXT NOT NULL,
  year INT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ NULL,
  status TEXT NOT NULL DEFAULT 'started',
  rows_loaded BIGINT NULL,
  notes TEXT NULL
);
