import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()
METRICS = []

# Central OTA directory (mounted from host: ./dashboard/ota)
OTA_DIR = "/app/ota"

@app.post("/ingest")
async def ingest(req: Request):
    data = await req.json()
    METRICS.append(data)
    return {"ok": True, "count": len(METRICS)}

@app.get("/status")
def status():
    return {
        "total": len(METRICS),
        "latest": METRICS[-5:]
    }

# ---- OTA endpoints (central server) ----

@app.get("/ota/manifest.json")
def ota_manifest():
    p = os.path.join(OTA_DIR, "manifest.json")
    if not os.path.exists(p):
        raise HTTPException(404, "manifest not found")
    return FileResponse(p)


@app.get("/ota/{name}")
def ota_file(name: str):
    p = os.path.join(OTA_DIR, name)
    if not os.path.exists(p):
        raise HTTPException(404, "file not found")
    return FileResponse(p)
