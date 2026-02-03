import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DASHBOARD = os.getenv("DASHBOARD_URL", "http://dashboard:8080")
BUFFER = []

@app.post("/metrics")
async def metrics(req: Request):
    data = await req.json()
    BUFFER.append(data)
    return {"buffered": len(BUFFER)}

@app.post("/flush")
async def flush():
    sent = 0
    async with httpx.AsyncClient() as client:
        for item in list(BUFFER):
            await client.post(f"{DASHBOARD}/ingest", json=item)
            BUFFER.remove(item)
            sent += 1
    return {"sent": sent}
