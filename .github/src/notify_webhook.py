import os, json, requests
from pathlib import Path
from src.utils import ensure_output_dir

WEBHOOK_URL = os.environ.get("WEBHOOK_URL","")

def main():
    if not WEBHOOK_URL:
        print("No WEBHOOK_URL set; skipping.")
        return
    out_dir, year, week = ensure_output_dir()
    drive = json.loads((out_dir/"drive_links.json").read_text(encoding="utf-8"))
    notion = json.loads((out_dir/"notion_urls.json").read_text(encoding="utf-8"))
    payload = {
        "title": f"Week {week} ({year}) Pack",
        "week": week,
        "year": year,
        "pdf_url": drive["pdf_url"],
        "md_url": drive["md_url"],
        "seo_url": notion["seo_url"]
    }
    r = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    r.raise_for_status()
    print("Webhook notified.")

if __name__ == "__main__":
    main()
