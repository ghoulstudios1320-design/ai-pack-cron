# src/notify_webhook.py
import os, json, time
from pathlib import Path
import requests

WEBHOOK_URL   = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")  # <- add this secret in GH

def _post_with_retry(url, json_payload, tries=5, base_delay=1.0):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, json=json_payload, timeout=20)
            if r.status_code in (200, 202):
                return r
            last = r
        except requests.RequestException as e:
            last = e
        time.sleep(base_delay * (2 ** i))
    if isinstance(last, requests.Response):
        last.raise_for_status()
    raise RuntimeError(f"Webhook failed after {tries} attempts: {last}")

def main():
    if not WEBHOOK_URL:
        print("No WEBHOOK_URL set; skipping.")
        return

    out_dirs = sorted(Path("output").glob("20*-W*"))
    if not out_dirs:
        raise RuntimeError("No output folder found")
    out = out_dirs[-1]

    drive = {}
    dl = out / "drive_links.json"
    if dl.exists():
        drive = json.loads(dl.read_text(encoding="utf-8"))

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    week = int(out.name.split("-W")[1])
    year = int(out.name.split("-W")[0])

    payload = {
        "token": WEBHOOK_TOKEN,           # ← Make will check this
        "auth": WEBHOOK_TOKEN,            # ← redundancy for your OR filter
        "title": meta.get("title", f"Week {week} ({year})"),
        "week": week,
        "year": year,
        "pdf_url": drive.get("pdf_url", ""),
        "md_url":  drive.get("md_url",  ""),
    }

    r = _post_with_retry(WEBHOOK_URL, payload)
    print("Webhook status:", r.status_code)
    print("Webhook notified.")

if __name__ == "__main__":
    main()
