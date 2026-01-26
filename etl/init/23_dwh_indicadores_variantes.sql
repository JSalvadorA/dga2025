-- =============================================================================
-- DWH: Variantes de indicadores para análisis
-- Fecha: 2025-01-09
-- =============================================================================

-- =============================================================================
-- INDICADOR 2: VARIANTES DE DESVIO POR UE
-- =============================================================================
--
-- Indicadores disponibles (todos en porcentaje):
--   - ind_cobertura_pct: Indicador actual (binario: % items con ejecución)
--   - ind_desvio_v1_mezcla_pct: 100 * (sum_prog - sum_ejec) / sum_prog
--   - ind_desvio_v2_todos_pct: 100 * sum(desv_i) / sum(prog_i) para todos los items
--   - ind_desvio_v3_sin_ceros_pct: 100 * sum(desv_i) / sum(prog_i) excluyendo items con desv=0
--
-- Donde desv_i = prog_i - ejec_i para cada item
-- Valores negativos = sobreejecución, positivos = subejecución
-- =============================================================================

DROP VIEW IF EXISTS dwh_replica.indicador_desvio_por_ue;

CREATE OR REPLACE VIEW dwh_replica.indicador_desvio_por_ue AS
WITH item_level AS (
  SELECT
    p.ano_eje,
    p.sec_ejec,
    p.id_siga_12,
    p.n_reg_prog,
    COALESCE(e.n_reg_ejec, 0) as n_reg_ejec,
    (p.n_reg_prog - COALESCE(e.n_reg_ejec, 0)) as desv_item
  FROM dwh_replica.programado_panel p
  LEFT JOIN dwh_replica.fact_ejecutado e
    ON e.ano_eje = p.ano_eje
    AND e.sec_ejec = p.sec_ejec
    AND e.id_siga_12 = p.id_siga_12
    AND e.estado_siaf_norm = 'APROBADO'
),
agregado_ue AS (
  SELECT
    ano_eje,
    sec_ejec,
    -- Contadores
    COUNT(*) as n_items,
    SUM(CASE WHEN n_reg_ejec > 0 THEN 1 ELSE 0 END)::bigint as n_items_con_ejec,
    SUM(CASE WHEN n_reg_ejec = 0 THEN 1 ELSE 0 END)::bigint as n_items_sin_ejec,
    SUM(CASE WHEN desv_item != 0 THEN 1 ELSE 0 END)::bigint as n_items_con_desvio,
    SUM(CASE WHEN desv_item = 0 THEN 1 ELSE 0 END)::bigint as n_items_sin_desvio,
    -- Sumas totales
    SUM(n_reg_prog)::bigint as sum_prog,
    SUM(n_reg_ejec)::bigint as sum_ejec,
    -- Suma de desvios (todos)
    SUM(desv_item)::bigint as sum_desv_todos,
    -- Suma de desvios (solo donde desv != 0)
    SUM(CASE WHEN desv_item != 0 THEN desv_item ELSE 0 END)::bigint as sum_desv_no_cero,
    -- Suma de prog solo donde desv != 0
    SUM(CASE WHEN desv_item != 0 THEN n_reg_prog ELSE 0 END)::bigint as sum_prog_con_desvio
  FROM item_level
  GROUP BY ano_eje, sec_ejec
)
SELECT
  a.ano_eje,
  a.sec_ejec,
  u.region,
  u.nombre_pliego,
  u.nombre_ejecutora,
  -- Contadores
  a.n_items,
  a.n_items_con_ejec,
  a.n_items_sin_ejec,
  a.n_items_con_desvio,
  a.n_items_sin_desvio,
  -- Sumas
  a.sum_prog,
  a.sum_ejec,
  a.sum_desv_todos,
  a.sum_desv_no_cero,
  a.sum_prog_con_desvio,
  -- INDICADOR COBERTURA (actual - binario)
  ROUND(100.0 * a.n_items_con_ejec / NULLIF(a.n_items, 0), 4) as ind_cobertura_pct,
  -- VARIANTE 1: Desvio mezcla en porcentaje
  CASE
    WHEN a.sum_prog > 0 THEN ROUND(100.0 * (a.sum_prog - a.sum_ejec)::numeric / a.sum_prog, 4)
    ELSE NULL
  END as ind_desvio_v1_mezcla_pct,
  -- VARIANTE 2: Desvio todos en porcentaje
  CASE
    WHEN a.sum_prog > 0 THEN ROUND(100.0 * a.sum_desv_todos::numeric / a.sum_prog, 4)
    ELSE NULL
  END as ind_desvio_v2_todos_pct,
  -- VARIANTE 3: Desvio sin ceros en porcentaje
  CASE
    WHEN a.sum_prog_con_desvio > 0 THEN ROUND(100.0 * a.sum_desv_no_cero::numeric / a.sum_prog_con_desvio, 4)
    ELSE NULL
  END as ind_desvio_v3_sin_ceros_pct,
  -- Clasificacion estado
  CASE
    WHEN a.sum_ejec = 0 THEN 'SIN_EJECUCION'
    WHEN a.sum_ejec < a.sum_prog THEN 'SUBEJECUCION'
    WHEN a.sum_ejec = a.sum_prog THEN 'EJECUCION_EXACTA'
    WHEN a.sum_ejec > a.sum_prog THEN 'SOBREEJECUCION'
  END as estado_ejecucion
FROM agregado_ue a
JOIN dwh_replica.universo_panel u
  ON u.ano_eje = a.ano_eje AND u.sec_ejec = a.sec_ejec;


-- =============================================================================
-- INDICADOR 1: DETALLE NUMERADOR VARIANTE 4
-- =============================================================================
--
-- Muestra los registros CMN individuales por UE para las UEs que entran
-- en el numerador de la variante 4 (tienen las 3 fases en al menos una fuente
-- Y están en el padrón con SIGA=SI)
-- =============================================================================

DROP VIEW IF EXISTS dwh_ind1.detalle_numerador_v4;

CREATE OR REPLACE VIEW dwh_ind1.detalle_numerador_v4 AS
WITH
-- UEs que tienen las 3 fases en al menos una fuente
ues_3_fases_por_fuente AS (
  SELECT
    ano_eje,
    sec_ejec,
    fuente,
    COUNT(DISTINCT fase_codigo) as n_fases
  FROM dwh_ind1.cmn_lite
  WHERE fase_codigo IN (1, 2, 3)
  GROUP BY ano_eje, sec_ejec, fuente
  HAVING COUNT(DISTINCT fase_codigo) = 3
),
-- Union de UEs con 3 fases (MEF o MINEDU)
union_v4 AS (
  SELECT DISTINCT ano_eje, sec_ejec
  FROM ues_3_fases_por_fuente
),
-- Padron SIGA=SI
padron_si AS (
  SELECT anio as ano_eje, sec_ejec, categoria
  FROM dwh_ind1.padron_largo
  WHERE siga_implementado = 'SI'
),
-- UEs del numerador V4 (union intersect padron_si)
numerador_v4 AS (
  SELECT
    u.ano_eje,
    u.sec_ejec,
    p.categoria,
    'NUMERADOR_V4' as status
  FROM union_v4 u
  INNER JOIN padron_si p ON p.ano_eje = u.ano_eje AND p.sec_ejec = u.sec_ejec
)
-- Detalle de registros CMN para UEs del numerador
SELECT
  n.ano_eje,
  n.sec_ejec,
  n.categoria,
  c.fase_codigo,
  c.fase_programacion,
  c.fuente,
  COUNT(*) as n_registros_cmn
FROM numerador_v4 n
JOIN dwh_ind1.cmn_lite_trace c
  ON c.ano_eje = n.ano_eje
  AND c.sec_ejec = n.sec_ejec
  AND c.fase_codigo IS NOT NULL
GROUP BY n.ano_eje, n.sec_ejec, n.categoria, c.fase_codigo, c.fase_programacion, c.fuente
ORDER BY n.ano_eje, n.sec_ejec, c.fase_codigo, c.fuente;


-- =============================================================================
-- CONSULTAS DE EJEMPLO
-- =============================================================================
--
-- Indicador 2 - Desvío por UE:
--   SELECT * FROM dwh_replica.indicador_desvio_por_ue
--   WHERE ano_eje = 2022 AND sec_ejec = '864';
--
-- Indicador 2 - Detalle items para una UE:
--   SELECT
--     p.id_siga_12,
--     p.n_reg_prog as prog,
--     COALESCE(e.n_reg_ejec, 0) as ejec,
--     (p.n_reg_prog - COALESCE(e.n_reg_ejec, 0)) as desv
--   FROM dwh_replica.programado_panel p
--   LEFT JOIN dwh_replica.fact_ejecutado e
--     ON e.ano_eje = p.ano_eje
--     AND e.sec_ejec = p.sec_ejec
--     AND e.id_siga_12 = p.id_siga_12
--     AND e.estado_siaf_norm = 'APROBADO'
--   WHERE p.ano_eje = 2022 AND p.sec_ejec = '864';
--
-- Indicador 1 - Detalle V4 para una UE:
--   SELECT * FROM dwh_ind1.detalle_numerador_v4
--   WHERE ano_eje = 2022 AND sec_ejec = '1000';
--
-- =============================================================================
