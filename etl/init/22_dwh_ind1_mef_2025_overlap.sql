-- DWH IND1 (MEF 2025): UnificaciÃ³n v1/v2 por filas + flags de overlap.
--
-- Reglas:
-- - NO usar CENTRO_COSTO como grano.
-- - Mantener ambas fuentes (v1/v2) y exponer flags para detectar overlap.
-- - Canonizar: UE (SEC_EJEC) + ID_SIGA_12 + FASE + TIPO_BIEN + montos/medidas.

CREATE OR REPLACE VIEW dwh_ind1.mef_2025_union AS
SELECT
  2025::INT AS ano_eje,
  regexp_replace(regexp_replace(coalesce(c.sec_ejec, ''), '\s+', '', 'g'), '[^0-9]', '', 'g') AS sec_ejec,
  upper(trim(coalesce(c.fase_programacion, ''))) AS fase_programacion,
  CASE upper(trim(coalesce(c.fase_programacion, '')))
    WHEN 'IDENTIFICACION' THEN 1
    WHEN 'CLASIFICACION Y PRIORIZACION' THEN 2
    WHEN 'CIERRE CLASIFICACION Y PRIORIZACION' THEN 2
    WHEN 'CONSOLIDACION Y APROBACION' THEN 3
    WHEN 'CIERRE CONSOLIDADO APROBACION' THEN 3
    ELSE NULL
  END AS fase_codigo,
  upper(trim(coalesce(c.tipo_bien, ''))) AS tipo_bien,
  dwh.build_id_siga_12(c.grupo::TEXT, c.clase::TEXT, c.familia::TEXT, c.item::TEXT) AS id_siga_12,
  c.precio_unit,
  c.cant_total,
  c.mnto_total,
  trim(coalesce(c.region, '')) AS region,
  trim(coalesce(c.nombre_pliego, '')) AS nombre_pliego,
  trim(coalesce(c.ejecutora_dsc, '')) AS nombre_ejecutora,
  'v2'::TEXT AS source_version,
  'raw.cmn_mef_2025'::TEXT AS source_table
FROM raw.cmn_mef c
WHERE c.ano_eje = 2025

UNION ALL

SELECT
  2025::INT AS ano_eje,
  regexp_replace(regexp_replace(coalesce(c.sec_ejec, ''), '\s+', '', 'g'), '[^0-9]', '', 'g') AS sec_ejec,
  upper(trim(coalesce(c.fase_programacion, ''))) AS fase_programacion,
  CASE upper(trim(coalesce(c.fase_programacion, '')))
    WHEN 'IDENTIFICACION' THEN 1
    WHEN 'CLASIFICACION Y PRIORIZACION' THEN 2
    WHEN 'CIERRE CLASIFICACION Y PRIORIZACION' THEN 2
    WHEN 'CONSOLIDACION Y APROBACION' THEN 3
    WHEN 'CIERRE CONSOLIDADO APROBACION' THEN 3
    ELSE NULL
  END AS fase_codigo,
  upper(trim(coalesce(c.tipo_bien, ''))) AS tipo_bien,
  dwh.build_id_siga_12(c.grupo_bien::TEXT, c.clase_bien::TEXT, c.familia_bien::TEXT, c.item_bien::TEXT) AS id_siga_12,
  c.precio_unit,
  c.a2025_canttotal AS cant_total,
  c.a2025_montototal AS mnto_total,
  trim(coalesce(c.region, '')) AS region,
  trim(coalesce(c.nombre_pliego, '')) AS nombre_pliego,
  trim(coalesce(c.ejecutora_nombre, '')) AS nombre_ejecutora,
  'v1'::TEXT AS source_version,
  'raw.cmn_mef_2025_v1'::TEXT AS source_table
FROM raw.cmn_mef_2025_v1 c;


CREATE OR REPLACE VIEW dwh_ind1.mef_2025_union_flagged AS
WITH base AS (
  SELECT
    *,
    md5(
      concat_ws(
        '|',
        ano_eje::TEXT,
        sec_ejec,
        coalesce(fase_codigo::TEXT, ''),
        tipo_bien,
        id_siga_12,
        coalesce(precio_unit::TEXT, ''),
        coalesce(cant_total::TEXT, ''),
        coalesce(mnto_total::TEXT, '')
      )
    ) AS overlap_key_exact,
    md5(
      concat_ws(
        '|',
        ano_eje::TEXT,
        sec_ejec,
        coalesce(fase_codigo::TEXT, ''),
        tipo_bien,
        id_siga_12
      )
    ) AS overlap_key_business
  FROM dwh_ind1.mef_2025_union
),
stats_exact AS (
  SELECT
    overlap_key_exact,
    bool_or(source_version = 'v1') AS has_v1,
    bool_or(source_version = 'v2') AS has_v2,
    count(*)::BIGINT AS n_rows_exact
  FROM base
  GROUP BY 1
),
stats_business AS (
  SELECT
    overlap_key_business,
    count(*) FILTER (WHERE source_version = 'v1')::BIGINT AS n_rows_v1,
    count(*) FILTER (WHERE source_version = 'v2')::BIGINT AS n_rows_v2,
    count(*)::BIGINT AS n_rows_total
  FROM base
  GROUP BY 1
)
SELECT
  b.*,
  (e.has_v1 AND e.has_v2) AS flag_overlap_exact,
  e.n_rows_exact,
  (coalesce(s.n_rows_v1, 0) > 0 AND coalesce(s.n_rows_v2, 0) > 0) AS flag_overlap_business,
  coalesce(s.n_rows_v1, 0)::BIGINT AS n_rows_v1,
  coalesce(s.n_rows_v2, 0)::BIGINT AS n_rows_v2,
  coalesce(s.n_rows_total, 0)::BIGINT AS n_rows_total
FROM base b
JOIN stats_exact e USING (overlap_key_exact)
JOIN stats_business s USING (overlap_key_business);

