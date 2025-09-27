import os, json
from pathlib import Path
from urllib.parse import urlparse

def main():
    url = os.environ.get("WEBHOOK_URL", "").strip()
    token = os.environ.get("WEBHOOK_TOKEN", "").strip()

    # Basic URL sanity (avoids silent failures)
    p = urlparse(url)
    if not (url and p.scheme in ("http", "https") and p.netloc):
        print("WEBHOOK_URL missing or invalid; skipping notify_webhook.")
        return

    out = sorted(Path("output").glob("*"))[-1]
    drive = {}
    dl = out / "drive_links.json"
    if dl.exists():
        drive = json.loads(dl.read_text(encoding="utf-8"))
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))

    payload = {
        "title": meta["title"],
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
