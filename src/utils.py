import os, json, datetime as dt, re
from pathlib import Path

def iso_week_stamp():
    today = dt.date.today()
    year, week, _ = today.isocalendar()
    return year, week

def ensure_output_dir():
    year, week = iso_week_stamp()
    out = Path("output") / f"{year}-W{week:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out, year, week

def load_sa_credentials():
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    return json.loads(raw)

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def read_file(p: str) -> str:
    return Path(p).read_text(encoding="utf-8")

def write_file(p: str, content: str):
    Path(p).write_text(content, encoding="utf-8")
