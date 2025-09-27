import os
import json
from pathlib import Path
from urllib.parse import urlparse

def main():
    url = os.environ.get("WEBHOOK_URL", "").strip()
    token = os.environ.get("WEBHOOK_TOKEN", "").strip()

    # Basic URL sanity
    p = urlparse(url)
    if not (url and p.scheme in ("http", "https") and p.netloc):
        print("WEBHOOK_URL missing or invalid; skipping notify_webhook.")
        return

    # Locate the newest weekly output folder
    out_dirs = sorted(Path("output").glob("*"))
    if not out_dirs:
        print("No output folder found; notify_webhook skipped.")
        return
    out = out_dirs[-1]

    # Read drive links (if present) and meta
    drive = {}
    dl = out / "drive_links.json"
    if dl.exists():
        drive = json.loads(dl.read_text(encoding="utf-8"))

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))

    payload = {
        "title": meta.get("title", f"{out.name}"),
        "week": int(out.name.split("-W")[1]),
        "year": int(out.name.split("-W")[0]),
        "pdf_url": drive.get("pdf_url", ""),
        "md_url":  drive.get("md_url", ""),
    }

    import requests
    headers = {"x-webhook-token": token} if token else {}
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    print(f"Webhook status: {r.status_code}")
    r.raise_for_status()
    print("Webhook notified.")

if __name__ == "__main__":
    main()
