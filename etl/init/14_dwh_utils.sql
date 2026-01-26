-- Utilidades compartidas (DWH).

CREATE OR REPLACE FUNCTION dwh.zfill_text(v TEXT, width INT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
  SELECT lpad(
    CASE
      WHEN regexp_replace(trim(coalesce(v, '')), '\.0$', '') = '' THEN '0'
      ELSE regexp_replace(trim(coalesce(v, '')), '\.0$', '')
    END,
    width,
    '0'
  );
$$;


CREATE OR REPLACE FUNCTION dwh.build_id_siga_12(grupo TEXT, clase TEXT, familia TEXT, item TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
  SELECT
    dwh.zfill_text(grupo, 2)
    || dwh.zfill_text(clase, 2)
    || dwh.zfill_text(familia, 4)
    || dwh.zfill_text(item, 4);
$$;

