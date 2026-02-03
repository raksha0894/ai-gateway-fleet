from fastapi import FastAPI, Request

app = FastAPI()
METRICS = []

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
