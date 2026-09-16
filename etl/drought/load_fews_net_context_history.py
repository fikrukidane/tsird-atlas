"""Retain listed FEWS NET Ethiopia native-FSC GeoJSON snapshots as provider context."""
import hashlib, json, os, urllib.request
from datetime import date
import psycopg2

ISSUES = (date(2026, 1, 1), date(2026, 2, 1), date(2026, 4, 1), date(2026, 6, 1), date(2026, 7, 1))
BASE = "https://fdw.fews.net/api/ipcphasemap/country/ET/{:%Y-%m-%d}.geojson"
def dsn(): return " ".join(("host=tsird-postgis","port=5432",f"dbname={os.environ['POSTGRES_DB']}",f"user={os.environ['POSTGRES_USER']}",f"password={os.environ['POSTGRES_PASSWORD']}"))
def main():
  outcomes=[]
  with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
    for issued in ISSUES:
      url=BASE.format(issued); req=urllib.request.Request(url,headers={"User-Agent":"TSIRD-Atlas-provider-context/1.0"})
      try:
        with urllib.request.urlopen(req,timeout=45) as r: payload=json.loads(r.read().decode())
        features=payload.get("features") or []
        if not features: raise ValueError("empty feature collection")
        run_id=f"fews-net-ethiopia-{issued:%Y%m%d}"
        cur.execute("""INSERT INTO tsird.drought_fews_net_context_run(run_id,issued_at,source_url,source_note)
          VALUES(%s,%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET source_url=excluded.source_url""",
          (run_id,issued,url,"FEWS NET provider context; native FSC geography; not a TSIRD or Tabia classification"))
        cur.execute("DELETE FROM tsird.drought_fews_net_context_feature WHERE run_id=%s",(run_id,))
        for i, feature in enumerate(features):
          geom=json.dumps(feature.get("geometry")); props=feature.get("properties") or {}
          fid=str(feature.get("id") or props.get("id") or hashlib.sha1(geom.encode()).hexdigest()[:16] or i)
          cur.execute("""INSERT INTO tsird.drought_fews_net_context_feature(run_id,feature_id,geometry,properties)
            VALUES(%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s::jsonb)""",(run_id,fid,geom,json.dumps(props)))
        outcomes.append({"run_id":run_id,"status":"retained","features":len(features)})
      except Exception as exc: outcomes.append({"issued_at":issued.isoformat(),"status":"unavailable","reason":type(exc).__name__})
    print(json.dumps({"source":"FEWS NET","outcomes":outcomes}))
if __name__ == '__main__': main()
