"""
TSIRD Gazetteer API
Endpoint: GET /gazetteer?q=<search text>
Returns bilingual woreda/tabia search results from PostGIS.
"""
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

app = FastAPI(title="TSIRD Gazetteer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DB_DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@tsird-postgis:5432/{os.environ['POSTGRES_DB']}"
)

SEARCH_SQL = """
WITH q AS (SELECT trim($1) AS query),
woredas AS (
  SELECT
    'woreda' AS type,
    "WEREDA"    AS name_en,
    woreda_tig  AS name_ti,
    ARRAY[
      ST_XMin(ST_Envelope(geometry)),
      ST_YMin(ST_Envelope(geometry)),
      ST_XMax(ST_Envelope(geometry)),
      ST_YMax(ST_Envelope(geometry))
    ] AS bbox,
    CASE
      WHEN lower("WEREDA") = lower((SELECT query FROM q))
        OR lower(woreda_tig) = lower((SELECT query FROM q)) THEN 1
      WHEN lower("WEREDA") LIKE lower((SELECT query FROM q)) || '%'
        OR lower(woreda_tig) LIKE lower((SELECT query FROM q)) || '%' THEN 2
      ELSE 3
    END AS rank
  FROM tigray_woredas_ws
  WHERE "WEREDA" ILIKE '%' || (SELECT query FROM q) || '%'
     OR woreda_tig ILIKE '%' || (SELECT query FROM q) || '%'
),
tabias AS (
  SELECT
    'tabia' AS type,
    "TABIA"    AS name_en,
    tabia_tig  AS name_ti,
    ARRAY[
      ST_XMin(ST_Envelope(geometry)),
      ST_YMin(ST_Envelope(geometry)),
      ST_XMax(ST_Envelope(geometry)),
      ST_YMax(ST_Envelope(geometry))
    ] AS bbox,
    CASE
      WHEN lower("TABIA") = lower((SELECT query FROM q))
        OR lower(tabia_tig) = lower((SELECT query FROM q)) THEN 1
      WHEN lower("TABIA") LIKE lower((SELECT query FROM q)) || '%'
        OR lower(tabia_tig) LIKE lower((SELECT query FROM q)) || '%' THEN 2
      ELSE 3
    END AS rank
  FROM tigray_tabias_ws
  WHERE "TABIA" ILIKE '%' || (SELECT query FROM q) || '%'
     OR tabia_tig ILIKE '%' || (SELECT query FROM q) || '%'
)
SELECT type, name_en, name_ti, bbox
FROM (SELECT * FROM woredas UNION ALL SELECT * FROM tabias) s
ORDER BY rank, name_en
LIMIT 15
"""

@app.get("/gazetteer")
async def gazetteer(q: str = Query(..., min_length=1, max_length=100)):
    try:
        conn = await asyncpg.connect(DB_DSN)
        rows = await conn.fetch(SEARCH_SQL, q.strip())
        await conn.close()
        results = []
        for row in rows:
            bbox = list(row["bbox"]) if row["bbox"] else None
            results.append({
                "type": row["type"],
                "name_en": row["name_en"] or "",
                "name_ti": row["name_ti"] or "",
                "bbox": bbox
            })
        return results
    except Exception as e:
        import logging
        logging.error(f"Gazetteer query error: {e}")
        return []

@app.get("/health")
async def health():
    return {"status": "ok"}
