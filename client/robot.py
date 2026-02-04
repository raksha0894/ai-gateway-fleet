import os, time, json, hashlib, tarfile, subprocess
import httpx
import random

GATEWAY = os.getenv("GATEWAY_URL", "http://gateway:8081")

STATE = "/app/state"
CUR = f"{STATE}/current"
NEW = f"{STATE}/new"
OLD = f"{STATE}/old"
os.makedirs(STATE, exist_ok=True)

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_blob(artifact_path: str, bundle_path: str):
    subprocess.check_call([
        "cosign", "verify-blob",
        "--key", "/app/cosign.pub",
        "--bundle", bundle_path,
        artifact_path
    ])

def install_tarball(tgz_path: str):
    # stage NEW
    if os.path.exists(NEW):
        subprocess.call(["rm", "-rf", NEW])
    os.makedirs(NEW, exist_ok=True)

    with tarfile.open(tgz_path) as t:
        t.extractall(NEW)

    # basic health check: must contain app.sh
    if not os.path.exists(f"{NEW}/app.sh"):
        raise RuntimeError("healthcheck failed: app.sh missing")

    # atomic-ish switch with rollback folder
    if os.path.exists(OLD):
        subprocess.call(["rm", "-rf", OLD])
    if os.path.exists(CUR):
        os.rename(CUR, OLD)
    os.rename(NEW, CUR)

def try_update():
    m = httpx.get(f"{GATEWAY}/manifest", timeout=5).json()

    version = m["version"]
    if version == current_version():
        return version
    artifact = m["artifact"]
    bundle = m["bundle"]
    expected_sha = m["sha256"]

    art_path = f"{STATE}/{artifact}"
    bun_path = f"{STATE}/{bundle}"

    # download artifact + bundle
    r = httpx.get(f"{GATEWAY}/artifact/{artifact}", timeout=15)
    r.raise_for_status()
    open(art_path, "wb").write(r.content)

    r = httpx.get(f"{GATEWAY}/artifact/{bundle}", timeout=15)
    r.raise_for_status()
    open(bun_path, "wb").write(r.content)

    # checksum
    if sha256_file(art_path) != expected_sha:
        raise RuntimeError("checksum mismatch")

    # signature verification
    verify_blob(art_path, bun_path)

    # install
    install_tarball(art_path)

    return version

def current_version():
    ver_file = f"{CUR}/version.txt"
    if os.path.exists(ver_file):
        return open(ver_file).read().strip()
    return "0.0.0"

def write_version(v: str):
    os.makedirs(CUR, exist_ok=True)
    open(f"{CUR}/version.txt", "w").write(v)

version = current_version()
while True:
    # try OTA update
    try:
        newv = try_update()
        if newv != version:
            version = newv
            write_version(version)
            print("UPDATED TO", version)
    except Exception as e:
        print("update skipped:", e)

    # send metrics
    payload = {
        "robot_id": "robot-1",
        "version": version,
        "cpu": round(random.random()*100, 2),
        "mem": round(random.random()*100, 2),
        "healthy": True
    }
    try:
        r=httpx.post(f"{GATEWAY}/metrics", json=payload, timeout=2)
        print("metrics sent:", r.status_code, payload)
    except Exception as e:
        print("metrics failed:", e)

    time.sleep(10)


