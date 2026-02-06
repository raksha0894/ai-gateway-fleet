import os
import time, shutil
import json
import sqlite3
import asyncio
import hashlib
import subprocess
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from cache_manager import gc_cache_once
from common.downloader import download_with_resume

app = FastAPI()

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://dashboard:8080")

DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "metrics.db")
os.makedirs(DATA_DIR, exist_ok=True)

CACHE_DIR = "/app/cache"
os.makedirs(CACHE_DIR, exist_ok=True)
GC_INTERVAL = int(os.getenv("CACHE_GC_INTERVAL", "300"))  # 5 min

# ---- Central OTA source (dashboard) ----
OTA_SOURCE_URL = os.getenv("OTA_SOURCE_URL", "http://dashboard:8080/ota")
POLL_SECONDS = int(os.getenv("OTA_POLL_SECONDS", "30"))

# ---- Cosign verification ----
COSIGN_PUB = "/app/cosign.pub"

# ---- Autoflush metrics enablement ----
AUTO_FLUSH = os.getenv("AUTO_FLUSH", "false").lower() == "true"
FLUSH_INTERVAL_SECONDS = int(os.getenv("FLUSH_INTERVAL_SECONDS", "5"))
FLUSH_BATCH_SIZE = int(os.getenv("FLUSH_BATCH_SIZE", "200"))

_flush_lock = asyncio.Lock()

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
    try:
        conn.execute(
            "INSERT INTO metrics(ts, payload) VALUES(?, ?)",
            (ts, json.dumps(data)),
        )
        conn.commit()
        buffered = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    finally:
        conn.close()

    return {"ok": True, "buffered": buffered}

@app.post("/flush")
async def flush():
     return await flush_once()

async def flush_once(limit: int = None):
    limit = limit or FLUSH_BATCH_SIZE

    async with _flush_lock:  # prevents auto + manual flush overlapping
        conn = db_conn()
        try:
            rows = conn.execute(
                "SELECT id, payload FROM metrics ORDER BY id LIMIT ?",
                (limit,)
            ).fetchall()

            remaining_before = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
            if not rows:
                return {"ok": True, "sent": 0, "remaining": remaining_before}

            sent_ids = []
            async with httpx.AsyncClient(timeout=5) as client:
                for mid, payload_json in rows:
                    payload = json.loads(payload_json)
                    r = await client.post(f"{DASHBOARD_URL}/ingest", json=payload)
                    r.raise_for_status()
                    sent_ids.append(mid)

            if sent_ids:
                conn.executemany("DELETE FROM metrics WHERE id = ?", [(i,) for i in sent_ids])
                conn.commit()

            remaining_after = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
            return {"ok": True, "sent": len(sent_ids), "remaining": remaining_after}

        except Exception as e:
            # If anything fails, keep rows (don’t delete)
            remaining = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
            return {"ok": False, "sent": 0, "remaining": remaining, "error": str(e)}
        finally:
            conn.close()
            
async def auto_flush_loop():
    while True:
        try:
            res = await flush_once()
            # log only when something happened or there was an error
            if res.get("sent", 0) > 0:
                print(f"[gateway] auto-flush sent={res['sent']} remaining={res['remaining']}", flush=True)
            elif res.get("ok") is False:
                print(f"[gateway] auto-flush failed: {res.get('error')}", flush=True)
        except Exception as e:
            print(f"[gateway] auto-flush loop error: {e}", flush=True)

        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_auto_flush():
    if AUTO_FLUSH:
        asyncio.create_task(auto_flush_loop())
        print("[gateway] auto-flush enabled", flush=True)

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

# -----------------------------
# OTA: helpers
# -----------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def cosign_verify_blob(artifact_path: str, bundle_path: str):
    subprocess.check_call(
        [
            "cosign",
            "verify-blob",
            "--key",
            COSIGN_PUB,
            "--bundle",
            bundle_path,
            artifact_path,
        ]
    )


# -----------------------------
# OTA: poll + sync (central -> gateway cache)
# -----------------------------
async def ota_sync_once():
    async with httpx.AsyncClient(timeout=20) as client:
        # 1) Fetch manifest from central
        r = await client.get(f"{OTA_SOURCE_URL}/manifest.json")
        r.raise_for_status()
        manifest = r.json()

        new_version = manifest["version"]
        artifact = manifest["artifact"]
        bundle = manifest["bundle"]
        expected_sha = manifest["sha256"]

        # 2) If cached version matches, skip
        cached_manifest_path = os.path.join(CACHE_DIR, "manifest.json")
        if os.path.exists(cached_manifest_path):
            try:
                cached = json.load(open(cached_manifest_path))
                if cached.get("version") == new_version:
                    return
            except Exception:
                pass

        # 3) Download artifact + bundle (with resume)

        art_path = os.path.join(CACHE_DIR, artifact)
        bun_path = os.path.join(CACHE_DIR, bundle)

        download_with_resume(
            f"{OTA_SOURCE_URL}/{artifact}",
            art_path,
            timeout=60
        )

        download_with_resume(
            f"{OTA_SOURCE_URL}/{bundle}",
            bun_path,
            timeout=60
        )

        # 4) Verify checksum
        actual_sha = sha256_file(art_path)
        if actual_sha != expected_sha:
            raise RuntimeError("gateway OTA sync: checksum mismatch")

        # 5) Verify signature (gateway-side)
        cosign_verify_blob(art_path, bun_path)

        # 6) Write manifest atomically
        cached_manifest_path = os.path.join(CACHE_DIR, "manifest.json")
        man_tmp = cached_manifest_path + ".tmp"
        with open(man_tmp, "w") as f:
            json.dump(manifest, f)
        os.replace(man_tmp, cached_manifest_path)

        print(f"[gateway] OTA cache updated to version {new_version}", flush=True)

async def ota_poll_loop():
    while True:
        try:
            await ota_sync_once()
        except Exception as e:
            print("[gateway] OTA poll failed:", e, flush=True)
        await asyncio.sleep(POLL_SECONDS)


@app.on_event("startup")
async def start_ota_poll():
    asyncio.create_task(ota_poll_loop())


@app.on_event("startup")
async def startup():
    async def gc_loop():
        while True:
            try:
                gc_cache_once()
            except Exception as e:
                print("[gateway] cache GC failed:", e, flush=True)
            await asyncio.sleep(GC_INTERVAL)

    asyncio.create_task(gc_loop())