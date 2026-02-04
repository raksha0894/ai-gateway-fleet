import os
import json
import sqlite3
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://dashboard:8080")

DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "metrics.db")
os.makedirs(DATA_DIR, exist_ok=True)

CACHE_DIR = "/app/cache"

def db_conn():
    # check_same_thread False is safe here because we open per request
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")  # better durability/concurrency
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    conn = db_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          payload TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

@app.post("/metrics")
async def metrics(req: Request):
    data = await req.json()
    ts = datetime.now(timezone.utc).isoformat()

    conn = db_conn()
    conn.execute(
        "INSERT INTO metrics(ts, payload) VALUES(?, ?)",
        (ts, json.dumps(data)),
    )
    conn.commit()

@app.post("/flush")
async def flush():
    """
    Sends buffered metrics to dashboard. If dashboard is down, nothing is deleted.
    """
    conn = db_conn()
    cur = conn.execute("SELECT id, payload FROM metrics ORDER BY id LIMIT 200")
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return {"ok": True, "sent": 0, "remaining": 0}

    sent = 0
    async with httpx.AsyncClient(timeout=5) as client:
        for mid, payload_json in rows:
            payload = json.loads(payload_json)
            try:
                r = await client.post(f"{DASHBOARD_URL}/ingest", json=payload)
                r.raise_for_status()
                conn.execute("DELETE FROM metrics WHERE id = ?", (mid,))
                conn.commit()
                sent += 1
            except Exception:
                # stop flushing on first failure; keep remaining buffered
                break

    cur = conn.execute("SELECT COUNT(*) FROM metrics")
    remaining = cur.fetchone()[0]
    conn.close()

    return {"ok": True, "sent": sent, "remaining": remaining}

@app.get("/manifest")
def get_manifest():
    p = os.path.join(CACHE_DIR, "manifest.json")
    if not os.path.exists(p):
        raise HTTPException(404, "manifest not found")
    return FileResponse(p)

@app.get("/artifact/{name}")
def get_artifact(name: str):
    p = os.path.join(CACHE_DIR, name)
    if not os.path.exists(p):
        raise HTTPException(404, "artifact not found")
    return FileResponse(p)
