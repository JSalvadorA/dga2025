-- DWH CL2: vistas base (no materializadas) para reproducir el pipeline portable
-- del Indicador Cl2 y habilitar análisis "what-if" del filtro ESTADO_SIAF.
--
-- Alineado al repo: ind22_26/scripts_portables_indCl2/
-- - Universo: preferir MINEDU si cumple F1-F3; si no, usar MEF si cumple.
-- - Programado: CMN, TIPO_BIEN='S', fase 3 (contiene "CONSOLIDACION"), por (SEC_EJEC, ID_SIGA_12).
-- - Ejecutado: OS, TIPO_BIEN='S', ESTADO_DEVENGADO='DEVENGADO', ESTADO_SIAF='APROBADO' (base),
--   pero se exponen vistas para todos los ESTADO_SIAF.

-- 1) Universo v4 (2022-2024)
CREATE OR REPLACE VIEW dwh_cl2.universo_v4_audit AS
WITH
mef_src AS (
  SELECT
    trim(coalesce(c.sec_ejec, '')) AS sec_ejec,
    c.ano_eje::INT AS ano_eje,
    count(*)::BIGINT AS mef_presente,
    count(DISTINCT
      CASE
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%IDENTIFICACION%' THEN 1
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CLASIFICACION%' THEN 2
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CONSOLIDACION%' THEN 3
        ELSE NULL
      END
    ) FILTER (WHERE c.fase_programacion IS NOT NULL)::BIGINT AS mef_n_fases,
    max(trim(coalesce(c.region, ''))) AS mef_region,
    max(trim(coalesce(c.nombre_pliego, ''))) AS mef_nombre_pliego,
    max(trim(coalesce(c.ejecutora_dsc, ''))) AS mef_nombre_ejecutora
  FROM raw.cmn_mef c
  WHERE
    c.ano_eje IN (2022, 2023, 2024)
    AND upper(trim(coalesce(c.tipo_bien, ''))) = 'S'
    AND trim(coalesce(c.sec_ejec, '')) <> ''
  GROUP BY 1, 2
),
minedu_src AS (
  SELECT
    trim(coalesce(c.sec_ejec, '')) AS sec_ejec,
    c.ano_eje::INT AS ano_eje,
    count(*)::BIGINT AS minedu_presente,
    count(DISTINCT
      CASE
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%IDENTIFICACION%' THEN 1
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CLASIFICACION%' THEN 2
        WHEN upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CONSOLIDACION%' THEN 3
        ELSE NULL
      END
    ) FILTER (WHERE c.fase_programacion IS NOT NULL)::BIGINT AS minedu_n_fases,
    max(trim(coalesce(c.region, ''))) AS minedu_region,
    max(trim(coalesce(c.nombre_pliego, ''))) AS minedu_nombre_pliego,
    max(trim(coalesce(c.ejecutora_nombre, ''))) AS minedu_nombre_ejecutora
  FROM raw.cmn_minedu c
  WHERE
    c.ano_eje IN (2022, 2023, 2024)
    AND upper(trim(coalesce(c.tipo_bien, ''))) = 'S'
    AND trim(coalesce(c.sec_ejec, '')) <> ''
  GROUP BY 1, 2
),
base AS (
  SELECT
    coalesce(mef.sec_ejec, minedu.sec_ejec) AS sec_ejec,
    coalesce(mef.ano_eje, minedu.ano_eje) AS ano_eje,

    coalesce(mef.mef_presente, 0)::BIGINT AS mef_presente,
    coalesce(minedu.minedu_presente, 0)::BIGINT AS minedu_presente,
    coalesce(mef.mef_n_fases, 0)::BIGINT AS mef_n_fases,
    coalesce(minedu.minedu_n_fases, 0)::BIGINT AS minedu_n_fases,

    (coalesce(mef.mef_n_fases, 0) = 3) AS mef_cumple_f123,
    (coalesce(minedu.minedu_n_fases, 0) = 3) AS minedu_cumple_f123,

    mef.mef_region,
    mef.mef_nombre_pliego,
    mef.mef_nombre_ejecutora,
    minedu.minedu_region,
    minedu.minedu_nombre_pliego,
    minedu.minedu_nombre_ejecutora
  FROM mef_src mef
  FULL JOIN minedu_src minedu
    ON mef.sec_ejec = minedu.sec_ejec
    AND mef.ano_eje = minedu.ano_eje
)
SELECT
  sec_ejec,
  ano_eje,

  mef_presente,
  mef_n_fases,
  mef_cumple_f123,

  minedu_presente,
  minedu_n_fases,
  minedu_cumple_f123,

  (mef_presente > 0) AS mef_en_fuente,
  (minedu_presente > 0) AS minedu_en_fuente,

  CASE
    WHEN minedu_cumple_f123 THEN 'MINEDU'
    WHEN mef_cumple_f123 THEN 'MEF'
    ELSE ''
  END AS fuente_cmn_usada,

  (minedu_cumple_f123 OR mef_cumple_f123) AS include_year,

  ((minedu_presente > 0) AND (NOT minedu_cumple_f123) AND mef_cumple_f123) AS flag_fallback_mef_por_minedu_incompleto,

  CASE
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MINEDU'
      THEN coalesce(minedu_region, 'SIN_REGION')
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MEF'
      THEN coalesce(mef_region, 'SIN_REGION')
    ELSE coalesce(minedu_region, mef_region, 'SIN_REGION')
  END AS region,

  CASE
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MINEDU'
      THEN coalesce(minedu_nombre_pliego, '')
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MEF'
      THEN coalesce(mef_nombre_pliego, '')
    ELSE coalesce(minedu_nombre_pliego, mef_nombre_pliego, '')
  END AS nombre_pliego,

  CASE
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MINEDU'
      THEN coalesce(minedu_nombre_ejecutora, '')
    WHEN (CASE WHEN minedu_cumple_f123 THEN 'MINEDU' WHEN mef_cumple_f123 THEN 'MEF' ELSE '' END) = 'MEF'
      THEN coalesce(mef_nombre_ejecutora, '')
    ELSE coalesce(minedu_nombre_ejecutora, mef_nombre_ejecutora, '')
  END AS nombre_ejecutora
FROM base
;


CREATE OR REPLACE VIEW dwh_cl2.universo_v4_raw AS
SELECT
  sec_ejec,
  ano_eje,
  region,
  nombre_pliego,
  nombre_ejecutora,
  fuente_cmn_usada,
  flag_fallback_mef_por_minedu_incompleto
FROM dwh_cl2.universo_v4_audit
WHERE include_year;


CREATE OR REPLACE VIEW dwh_cl2.universo_v4_panel_list AS
SELECT
  sec_ejec
FROM dwh_cl2.universo_v4_raw
GROUP BY sec_ejec
HAVING count(DISTINCT ano_eje) = 3;


CREATE OR REPLACE VIEW dwh_cl2.universo_v4_panel AS
SELECT u.*
FROM dwh_cl2.universo_v4_raw u
JOIN dwh_cl2.universo_v4_panel_list p USING (sec_ejec);


-- 2) Programado FASE3 (según fuente elegida en universo)
CREATE OR REPLACE VIEW dwh_cl2.programado_fase3_raw AS
WITH u AS (
  SELECT sec_ejec, ano_eje, fuente_cmn_usada
  FROM dwh_cl2.universo_v4_raw
)
SELECT
  c.ano_eje::INT AS ano_eje,
  trim(coalesce(c.sec_ejec, '')) AS sec_ejec,
  dwh.build_id_siga_12(c.grupo::TEXT, c.clase::TEXT, c.familia::TEXT, c.item::TEXT) AS id_siga_12,
  count(*)::BIGINT AS n_reg_prog
FROM raw.cmn_mef c
JOIN u
  ON u.ano_eje = c.ano_eje
  AND u.sec_ejec = trim(coalesce(c.sec_ejec, ''))
  AND u.fuente_cmn_usada = 'MEF'
WHERE
  upper(trim(coalesce(c.tipo_bien, ''))) = 'S'
  AND upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CONSOLIDACION%'
GROUP BY 1, 2, 3

UNION ALL

SELECT
  c.ano_eje::INT AS ano_eje,
  trim(coalesce(c.sec_ejec, '')) AS sec_ejec,
  dwh.build_id_siga_12(c.grupo::TEXT, c.clase::TEXT, c.familia::TEXT, c.item::TEXT) AS id_siga_12,
  count(*)::BIGINT AS n_reg_prog
FROM raw.cmn_minedu c
JOIN u
  ON u.ano_eje = c.ano_eje
  AND u.sec_ejec = trim(coalesce(c.sec_ejec, ''))
  AND u.fuente_cmn_usada = 'MINEDU'
WHERE
  upper(trim(coalesce(c.tipo_bien, ''))) = 'S'
  AND upper(trim(coalesce(c.fase_programacion, ''))) LIKE '%CONSOLIDACION%'
GROUP BY 1, 2, 3;


CREATE OR REPLACE VIEW dwh_cl2.programado_fase3_panel AS
SELECT p.*
FROM dwh_cl2.programado_fase3_raw p
JOIN dwh_cl2.universo_v4_panel_list u USING (sec_ejec);


-- 3) Ejecutado (OS) - exponer todos los estados, y vistas base con el filtro del indicador
CREATE OR REPLACE VIEW dwh_cl2.os_base_raw AS
SELECT
  o.ano_eje::INT AS ano_eje,
  trim(coalesce(o.sec_ejec, '')) AS sec_ejec,
  upper(trim(coalesce(o.tipo_bien, ''))) AS tipo_bien,
  upper(trim(coalesce(o.estado_devengado, ''))) AS estado_devengado,
  upper(trim(coalesce(o.estado_siaf, ''))) AS estado_siaf,
  dwh.build_id_siga_12(o.grupo_bien, o.clase_bien, o.familia_bien, o.item_bien) AS id_siga_12,
  o.moneda,
  o.valor_total_os,
  o.valor_ccosto
FROM raw.orden_servicio o
JOIN dwh_cl2.universo_v4_raw u
  ON u.ano_eje = o.ano_eje
  AND u.sec_ejec = trim(coalesce(o.sec_ejec, ''))
WHERE trim(coalesce(o.sec_ejec, '')) <> '';


CREATE OR REPLACE VIEW dwh_cl2.os_base_panel AS
SELECT o.*
FROM dwh_cl2.os_base_raw o
JOIN dwh_cl2.universo_v4_panel_list u USING (sec_ejec);


CREATE OR REPLACE VIEW dwh_cl2.ejecutado_servicio_estado_raw AS
SELECT
  ano_eje,
  sec_ejec,
  id_siga_12,
  tipo_bien,
  estado_devengado,
  estado_siaf,
  moneda,
  count(*)::BIGINT AS n_reg_ejec,
  sum(valor_total_os) AS sum_valor_total_os,
  sum(valor_ccosto) AS sum_valor_ccosto
FROM dwh_cl2.os_base_raw
WHERE id_siga_12 <> ''
GROUP BY 1, 2, 3, 4, 5, 6, 7;


CREATE OR REPLACE VIEW dwh_cl2.ejecutado_servicio_aprobado_devengado_raw AS
SELECT
  ano_eje,
  sec_ejec,
  id_siga_12,
  count(*)::BIGINT AS n_reg_ejec
FROM dwh_cl2.os_base_raw
WHERE
  tipo_bien = 'S'
  AND estado_devengado = 'DEVENGADO'
  AND estado_siaf = 'APROBADO'
  AND id_siga_12 <> ''
  AND id_siga_12 <> '000000000000'
GROUP BY 1, 2, 3;


CREATE OR REPLACE VIEW dwh_cl2.ejecutado_devengado_por_estado_siaf_raw AS
SELECT
  ano_eje,
  sec_ejec,
  id_siga_12,
  estado_siaf,
  count(*)::BIGINT AS n_reg_ejec
FROM dwh_cl2.os_base_raw
WHERE
  tipo_bien = 'S'
  AND estado_devengado = 'DEVENGADO'
  AND id_siga_12 <> ''
  AND id_siga_12 <> '000000000000'
GROUP BY 1, 2, 3, 4;


CREATE OR REPLACE VIEW dwh_cl2.ejecutado_servicio_aprobado_devengado_panel AS
SELECT e.*
FROM dwh_cl2.ejecutado_servicio_aprobado_devengado_raw e
JOIN dwh_cl2.universo_v4_panel_list u USING (sec_ejec);


-- 4) Indicador Cl2 (FASE3) - base y "what-if" por ESTADO_SIAF (devengado)
CREATE OR REPLACE VIEW dwh_cl2.indicador_por_ue_fase3_raw AS
WITH
prog_ids AS (
  SELECT DISTINCT
    ano_eje,
    sec_ejec,
    id_siga_12
  FROM dwh_cl2.programado_fase3_raw
  WHERE sec_ejec <> '' AND id_siga_12 <> ''
),
ejec AS (
  SELECT
    ano_eje,
    sec_ejec,
    id_siga_12,
    sum(n_reg_ejec)::BIGINT AS n_reg_ejec
  FROM dwh_cl2.ejecutado_servicio_aprobado_devengado_raw
  GROUP BY 1, 2, 3
),
merged AS (
  SELECT
    p.ano_eje,
    p.sec_ejec,
    p.id_siga_12,
    coalesce(e.n_reg_ejec, 0)::BIGINT AS n_reg_ejec,
    CASE WHEN coalesce(e.n_reg_ejec, 0) > 0 THEN 1 ELSE 0 END AS ejec_flag
  FROM prog_ids p
  LEFT JOIN ejec e
    ON e.ano_eje = p.ano_eje
    AND e.sec_ejec = p.sec_ejec
    AND e.id_siga_12 = p.id_siga_12
),
by_ue AS (
  SELECT
    ano_eje,
    sec_ejec,
    count(*)::BIGINT AS n_servicios_prog,
    sum(ejec_flag)::BIGINT AS n_servicios_con_ejec
  FROM merged
  GROUP BY 1, 2
)
SELECT
  'RAW'::TEXT AS universo,
  'FASE3'::TEXT AS variante,
  u.ano_eje,
  u.sec_ejec,
  u.region,
  u.nombre_pliego,
  u.nombre_ejecutora,
  coalesce(b.n_servicios_prog, 0)::BIGINT AS n_servicios_prog,
  coalesce(b.n_servicios_con_ejec, 0)::BIGINT AS n_servicios_con_ejec,
  (coalesce(b.n_servicios_prog, 0) - coalesce(b.n_servicios_con_ejec, 0))::BIGINT AS n_servicios_sin_ejec,
  CASE
    WHEN coalesce(b.n_servicios_prog, 0) > 0
      THEN 100.0 * coalesce(b.n_servicios_con_ejec, 0)::DOUBLE PRECISION / b.n_servicios_prog::DOUBLE PRECISION
    ELSE NULL
  END AS cumplimiento_pct
FROM dwh_cl2.universo_v4_raw u
LEFT JOIN by_ue b
  ON b.ano_eje = u.ano_eje
  AND b.sec_ejec = u.sec_ejec;


CREATE OR REPLACE VIEW dwh_cl2.indicador_por_ue_fase3_panel AS
SELECT i.*
FROM dwh_cl2.indicador_por_ue_fase3_raw i
JOIN dwh_cl2.universo_v4_panel_list u USING (sec_ejec);


CREATE OR REPLACE VIEW dwh_cl2.indicador_por_ue_fase3_por_estado_siaf_raw AS
WITH
prog_ids AS (
  SELECT DISTINCT
    ano_eje,
    sec_ejec,
    id_siga_12
  FROM dwh_cl2.programado_fase3_raw
  WHERE sec_ejec <> '' AND id_siga_12 <> ''
),
ejec_por_estado AS (
  SELECT
    ano_eje,
    sec_ejec,
    id_siga_12,
    estado_siaf,
    sum(n_reg_ejec)::BIGINT AS n_reg_ejec
  FROM dwh_cl2.ejecutado_devengado_por_estado_siaf_raw
  GROUP BY 1, 2, 3, 4
),
merged AS (
  SELECT
    p.ano_eje,
    p.sec_ejec,
    p.id_siga_12,
    e.estado_siaf,
    coalesce(e.n_reg_ejec, 0)::BIGINT AS n_reg_ejec,
    CASE WHEN coalesce(e.n_reg_ejec, 0) > 0 THEN 1 ELSE 0 END AS ejec_flag
  FROM prog_ids p
  LEFT JOIN ejec_por_estado e
    ON e.ano_eje = p.ano_eje
    AND e.sec_ejec = p.sec_ejec
    AND e.id_siga_12 = p.id_siga_12
),
by_ue_estado AS (
  SELECT
    ano_eje,
    sec_ejec,
    coalesce(estado_siaf, '') AS estado_siaf,
    count(*)::BIGINT AS n_servicios_prog,
    sum(ejec_flag)::BIGINT AS n_servicios_con_ejec
  FROM merged
  GROUP BY 1, 2, 3
)
SELECT
  'RAW'::TEXT AS universo,
  'FASE3'::TEXT AS variante,
  u.ano_eje,
  u.sec_ejec,
  u.region,
  u.nombre_pliego,
  u.nombre_ejecutora,
  b.estado_siaf,
  b.n_servicios_prog,
  b.n_servicios_con_ejec,
  (b.n_servicios_prog - b.n_servicios_con_ejec)::BIGINT AS n_servicios_sin_ejec,
  CASE
    WHEN b.n_servicios_prog > 0
      THEN 100.0 * b.n_servicios_con_ejec::DOUBLE PRECISION / b.n_servicios_prog::DOUBLE PRECISION
    ELSE NULL
  END AS cumplimiento_pct
FROM dwh_cl2.universo_v4_raw u
LEFT JOIN by_ue_estado b
  ON b.ano_eje = u.ano_eje
  AND b.sec_ejec = u.sec_ejec;
