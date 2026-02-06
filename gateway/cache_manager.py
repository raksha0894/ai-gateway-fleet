import os
import glob
import json
import re

CACHE_DIR = "/app/cache"

MAX_VERSIONS = int(os.getenv("CACHE_KEEP_LAST", "3"))      # keep last N
MAX_CACHE_MB = int(os.getenv("CACHE_MAX_MB", "500"))       # max MB

# matches app-v1.2.3.tar.gz
ART_RE = re.compile(r"^app-v(\d+)\.(\d+)\.(\d+)\.tar\.gz$")

def ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)

def file_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)

def get_cache_size_mb():
    total = 0.0
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        if os.path.isfile(path):
            total += file_size_mb(path)
    return total

def get_active_version_from_manifest():
    """Active version = manifest.json version (the one robots should install)."""
    p = os.path.join(CACHE_DIR, "manifest.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r") as f:
            m = json.load(f)
        return m.get("version")
    except Exception:
        return None

def safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print("[gateway] failed to remove", path, e, flush=True)

def parse_semver_from_filename(path):
    """Return (major, minor, patch) if filename matches app-vX.Y.Z.tar.gz else None."""
    base = os.path.basename(path)
    m = ART_RE.match(base)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

def gc_cache_once():
    """
    Policy (bounded cache, single directory):
      1) Always keep manifest.json
      2) Always keep the artifact+bundle referenced by manifest version (if present)
      3) Keep newest MAX_VERSIONS artifacts by semver (fallback: mtime)
      4) Delete older artifacts + their bundles
      5) Delete any *.part temp files
      6) Enforce MAX_CACHE_MB by deleting oldest non-active versions
    """
    ensure_cache()
    print("[gateway] running cache GC...", flush=True)

    active_ver = get_active_version_from_manifest()

    # Find OTA artifacts
    ota_files = glob.glob(os.path.join(CACHE_DIR, "app-v*.tar.gz"))

    # Sort by semver if possible; else by mtime
    parsed = [(f, parse_semver_from_filename(f)) for f in ota_files]
    if all(v is not None for _, v in parsed):
        parsed.sort(key=lambda x: x[1], reverse=True)  # newest version first
        ota_files_sorted = [f for f, _ in parsed]
    else:
        ota_files_sorted = sorted(ota_files, key=lambda f: os.path.getmtime(f), reverse=True)

    keep = set()

    # Keep active version (if present)
    if active_ver:
        active_art = os.path.join(CACHE_DIR, f"app-v{active_ver}.tar.gz")
        active_bun = active_art + ".bundle"
        if os.path.exists(active_art):
            keep.add(active_art)
        if os.path.exists(active_bun):
            keep.add(active_bun)

    # Keep newest N artifacts (+ their bundles)
    kept_artifacts = 0
    for art in ota_files_sorted:
        if kept_artifacts >= MAX_VERSIONS:
            break
        keep.add(art)
        bun = art + ".bundle"
        if os.path.exists(bun):
            keep.add(bun)
        kept_artifacts += 1

    # Delete old artifacts/bundles not in keep
    deleted = []
    for art in ota_files_sorted:
        bun = art + ".bundle"
        if art not in keep:
            safe_remove(art)
            deleted.append(os.path.basename(art))
        if bun not in keep:
            safe_remove(bun)
            deleted.append(os.path.basename(bun))

    # Delete temp files
    for tmp in glob.glob(os.path.join(CACHE_DIR, "*.part")):
        safe_remove(tmp)
        deleted.append(os.path.basename(tmp))

    # Enforce size cap (delete oldest artifacts until under MAX_CACHE_MB)
    def cache_ok():
        return get_cache_size_mb() <= MAX_CACHE_MB

    if not cache_ok():
        # oldest first now
        if all(parse_semver_from_filename(f) is not None for f in ota_files):
            # sort oldest semver first
            ota_oldest = sorted(ota_files, key=lambda f: parse_semver_from_filename(f))
        else:
            ota_oldest = sorted(ota_files, key=lambda f: os.path.getmtime(f))

        for art in ota_oldest:
            if cache_ok():
                break

            # never delete active version
            if active_ver and f"app-v{active_ver}.tar.gz" == os.path.basename(art):
                continue

            bun = art + ".bundle"
            if os.path.exists(art):
                safe_remove(art)
                deleted.append(os.path.basename(art))
            if os.path.exists(bun):
                safe_remove(bun)
                deleted.append(os.path.basename(bun))

    print(
        f"[gateway] GC done. active={active_ver} size={get_cache_size_mb():.2f}MB deleted={len(deleted)}",
        flush=True
    )
    return {"active": active_ver, "deleted": deleted, "size_mb": round(get_cache_size_mb(), 2)}