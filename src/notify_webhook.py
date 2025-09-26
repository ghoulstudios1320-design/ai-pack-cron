import os, json
from pathlib import Path

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

def main():
    if not WEBHOOK_URL:
        print("No WEBHOOK_URL set; skipping.")
        return
    import requests
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
    r = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    r.raise_for_status()
    print("Webhook notified.")

if __name__ == "__main__":
    main()
