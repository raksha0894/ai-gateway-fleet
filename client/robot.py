import os, time, json, hashlib, tarfile, subprocess
import httpx
import random
from common.downloader import download_with_resume

GATEWAY = os.getenv("GATEWAY_URL", "http://gateway:8081")

STATE = "/app/state"
COSIGN_PUB = os.getenv("COSIGN_PUB", "/app/cosign.pub")
DOWNLOAD_TIMEOUT = float(os.getenv("DOWNLOAD_TIMEOUT", "30"))
MANIFEST_TIMEOUT = float(os.getenv("MANIFEST_TIMEOUT", "5"))

CUR = f"{STATE}/current"
NEW = f"{STATE}/new"
OLD = f"{STATE}/old"
os.makedirs(STATE, exist_ok=True)

OTA_POLL_SECONDS = int(os.getenv("OTA_POLL_SECONDS", "30"))
METRICS_SECONDS = int(os.getenv("METRICS_SECONDS", "10"))

# Track versions that triggered a rollback during this session
FAILED_VERSIONS = set()


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def current_version() -> str:
    ver_file = os.path.join(CUR, "version.txt")
    if os.path.exists(ver_file):
        return open(ver_file, "r", encoding="utf-8").read().strip()
    return "1.92.4"


def write_current_version(v: str) -> None:
    os.makedirs(CUR, exist_ok=True)
    open(os.path.join(CUR, "version.txt"), "w", encoding="utf-8").write(v)


def verify_blob(artifact_path: str, bundle_path: str) -> None:
    # Requires cosign installed in robot container
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


def safe_rmtree(path: str) -> None:
    if os.path.exists(path):
        subprocess.call(["rm", "-rf", path])


def install_tarball(tgz_path: str) -> None:
    # 1. Prepare NEW directory
    safe_rmtree(NEW)
    os.makedirs(NEW, exist_ok=True)

    log(f"DEBUG: Extracting {tgz_path}...")
    with tarfile.open(tgz_path, "r:gz") as t:
        # filter='data' stops the crash/loop at line 35
        t.extractall(NEW, filter='data') 

    # 2. ACTIVATE (Move to CURRENT so we have an OLD to roll back to)
    log("DEBUG: Activating version (Moving NEW -> CURRENT)...")
    safe_rmtree(OLD)
    if os.path.exists(CUR):
        os.rename(CUR, OLD)
    os.rename(NEW, CUR)

    # 3. THE LIVE TEST (This is what you just ran manually)
    app_sh_cur = os.path.join(CUR, "app.sh")
    try:
        log(f"DEBUG: Running self-test at {app_sh_cur}")
        # MUST use check_call to trigger the 'except' block on failure
        subprocess.check_call(["bash", app_sh_cur, "--self-test"], timeout=10)
        log("SUCCESS: Healthcheck passed.")
    except subprocess.CalledProcessError:
        # 4. PERFORM ROLLBACK
        FAILED_VERSIONS.add(httpx.get(f"{GATEWAY}/manifest", timeout=MANIFEST_TIMEOUT).json()["version"])
        log("CRITICAL: Self-test failed! TRIGGERING ROLLBACK...")
        if os.path.exists(OLD):
            safe_rmtree(CUR)
            os.rename(OLD, CUR)
            log("ROLLBACK COMPLETE: Restored previous version.")
        else:
            log("ROLLBACK FAILED: No OLD version found.")
        
        # Raise this so version.txt is NOT updated
        raise RuntimeError("Update failed healthcheck and was rolled back.")

def rollback_to_old() -> bool:
    if not os.path.exists(OLD):
        return False
    safe_rmtree(CUR)
    os.rename(OLD, CUR)
    return True


def try_update(client: httpx.Client) -> str:
    m = client.get(f"{GATEWAY}/manifest", timeout=MANIFEST_TIMEOUT).json()

    version = m["version"]
    if version == current_version():
        return version
    
    if version in FAILED_VERSIONS:
        # Skip the update silently to avoid log spam
        return current_version()

    artifact = m["artifact"]
    bundle = m["bundle"]
    expected_sha = m["sha256"]

    art_path = f"{STATE}/{artifact}"
    bun_path = f"{STATE}/{bundle}"

    # download artifact + bundle
    download_with_resume(f"{GATEWAY}/artifact/{artifact}", art_path, timeout=30)
    download_with_resume(f"{GATEWAY}/artifact/{bundle}", bun_path, timeout=30)

    # checksum and signature
    if sha256_file(art_path) != expected_sha:
        raise RuntimeError("checksum mismatch")

    verify_blob(art_path, bun_path)

    # This call now handles directory swapping and rollback internally
    install_tarball(art_path)

    # persist version only after successful install
    write_current_version(version)
    log(f"UPDATED TO {version}")

    return version


# ---- main loop ----
version = current_version()
last_ota = 0.0
last_metrics = 0.0
backoff = 2
max_backoff = 60

client = httpx.Client()
installing = False

while True:
    now = time.time()

    if now - last_ota >= OTA_POLL_SECONDS:
        last_ota = now
        try:
            newv = None
            newv = try_update(client)
            if newv != version:
                installing = True
                try:
                    version = newv
                    backoff = 2
                finally:
                    installing = False
        except Exception as e:
            if newv is not None:
                FAILED_VERSIONS.add(newv)
                if rollback_to_old():
                    version = current_version()
                    log("Emergency manual rollback applied.")
            
            time.sleep(backoff)
            backoff = min(max_backoff, backoff * 2)

    if now - last_metrics >= METRICS_SECONDS:
        last_metrics = now
        payload = {
            "robot_id": "robot-1",
            "version": version,
            "cpu": round(random.random() * 100, 2),
            "mem": round(random.random() * 100, 2),
            "healthy": True,
        }
        try:
            r = client.post(f"{GATEWAY}/metrics", json=payload, timeout=2)
            log(f"metrics sent: {r.status_code} {payload}")
        except Exception as e:
            log(f"metrics failed: {e}")

    time.sleep(0.2)
