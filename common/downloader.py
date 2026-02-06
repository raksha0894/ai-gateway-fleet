import os
import httpx


def download_with_resume(url: str, dest: str, timeout: int = 30):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

    tmp = dest + ".part"
    headers = {}
    mode = "wb"

    if os.path.exists(tmp):
        start = os.path.getsize(tmp)
        headers["Range"] = f"bytes={start}-"
        mode = "ab"
        print(f"[download] Resuming from {start} bytes", flush=True)
    else:
        print("[download] Starting fresh download", flush=True)

    with httpx.stream("GET", url, headers=headers, timeout=timeout) as r:
        r.raise_for_status()

        if r.status_code not in (200, 206):
            raise RuntimeError(f"Unexpected HTTP {r.status_code}")

        # Range requested but not honored → restart cleanly
        if "Range" in headers and r.status_code == 200:
            mode = "wb"
            print("[download] Server ignored Range; restarting download", flush=True)

        with open(tmp, mode) as f:
            for chunk in r.iter_bytes():
                if chunk:
                    f.write(chunk)
            f.flush()
            os.fsync(f.fileno())

    os.replace(tmp, dest)
    print(f"[download] Completed: {dest}", flush=True)


def cleanup_part_files(directory: str):
    for name in os.listdir(directory):
        if name.endswith(".part"):
            path = os.path.join(directory, name)
            try:
                os.remove(path)
                print("[download] Removed temp:", path, flush=True)
            except Exception as e:
                print("[download] Failed removing", path, e, flush=True)