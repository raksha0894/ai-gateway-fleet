import os, time, random
import httpx

GATEWAY = os.getenv("GATEWAY_URL", "http://gateway:8081")

while True:
    payload = {
        "robot_id": "robot-1",
        "version": "0.1.0",
        "cpu": round(random.random()*100,2),
        "mem": round(random.random()*100,2),
        "healthy": True
    }

    try:
        httpx.post(f"{GATEWAY}/metrics", json=payload, timeout=2)
        print("sent:", payload)
    except:
        print("gateway offline")

    time.sleep(5)
