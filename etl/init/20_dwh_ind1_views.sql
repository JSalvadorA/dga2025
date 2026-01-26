-- DWH IND1: vistas base (no materializadas) para reproducir el "lite"
-- del pipeline portable y habilitar exploración en SQL.
--
-- Grano del lite: (ano_eje, sec_ejec, fase_codigo, fuente).

CREATE OR REPLACE VIEW dwh_ind1.cmn_lite_trace AS
SELECT
  c.ano_eje::INT AS ano_eje,
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
  'MEF'::TEXT AS fuente,
  'v2'::TEXT AS source_version,
  'raw.cmn_mef'::TEXT AS source_table
FROM raw.cmn_mef c
WHERE c.ano_eje <= 2024

UNION ALL

SELECT
  COALESCE(c.ano_eje, c.anno)::INT AS ano_eje,
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
  'MEF'::TEXT AS fuente,
  'v1'::TEXT AS source_version,
  'raw.cmn_mef_2025_v1'::TEXT AS source_table
FROM raw.cmn_mef_2025_v1 c
WHERE COALESCE(c.ano_eje, c.anno) = 2025

UNION ALL

SELECT
  c.ano_eje::INT AS ano_eje,
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
  'MINEDU'::TEXT AS fuente,
  'std'::TEXT AS source_version,
  'raw.cmn_minedu'::TEXT AS source_table
FROM raw.cmn_minedu c;


CREATE OR REPLACE VIEW dwh_ind1.cmn_lite AS
SELECT DISTINCT
  ano_eje,
  sec_ejec,
  fase_codigo,
  fuente
FROM dwh_ind1.cmn_lite_trace
WHERE
  sec_ejec <> ''
  AND fase_codigo IS NOT NULL;
