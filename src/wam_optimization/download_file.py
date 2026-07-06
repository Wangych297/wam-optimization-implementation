import argparse
import hashlib
import sys
import time
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    dest = Path(args.dest)
    log_path = Path(args.log)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    def log(message: str) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
            f.flush()

    log(f"START url={args.url} dest={dest}")
    headers = {"User-Agent": "Mozilla/5.0 CodexResearchDownloader/1.0"}
    request = urllib.request.Request(args.url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            hasher = hashlib.sha256()
            last_report = 0.0
            with tmp.open("wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_report >= 10:
                        if total:
                            pct = downloaded * 100.0 / total
                            log(f"PROGRESS {downloaded}/{total} bytes ({pct:.2f}%)")
                        else:
                            log(f"PROGRESS {downloaded} bytes")
                        last_report = now
        tmp.replace(dest)
        log(f"DONE bytes={downloaded} sha256={hasher.hexdigest()}")
        return 0
    except Exception as exc:
        log(f"ERROR {exc!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
