import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"
RUN_HISTORY_PATH = OUTPUT_DIR / "run_history.jsonl"


def find_week_dir() -> Path:
    week_key = os.getenv("WEEK_KEY", "").strip()

    if week_key:
        week_dir = OUTPUT_DIR / week_key
        if not week_dir.exists():
            raise RuntimeError(f"WEEK_KEY folder does not exist: {week_dir}")
        return week_dir

    week_dirs = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]

    if not week_dirs:
        raise RuntimeError("No output week folders found")

    return sorted(week_dirs, key=lambda p: p.name)[-1]


def load_manifest(week_dir: Path) -> Dict[str, Any]:
    manifest_path = week_dir / "distribution_manifest.json"

    if not manifest_path.exists():
        raise RuntimeError(f"Missing distribution manifest: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_history_record(
    manifest: Dict[str, Any],
    client: Dict[str, Any],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "recorded_at": now,
        "week": manifest.get("week"),
        "generated_at": manifest.get("generated_at"),
        "distribution_manifest_created_at": manifest.get("distribution_manifest_created_at"),
        "last_updated_at": manifest.get("last_updated_at"),

        "client_id": client.get("client_id"),
        "company_name": client.get("company_name"),
        "final_status": client.get("delivery_status"),
        "error": client.get("error"),
        "last_error": client.get("last_error"),

        "retry_count": client.get("retry_count", 0),
        "retry_after": client.get("retry_after"),
        "uploaded_at": client.get("uploaded_at"),
        "published_at": client.get("published_at"),
        "webhook_sent_at": client.get("webhook_sent_at"),
        "confirmed_at": client.get("confirmed_at"),
        "retry_started_at": client.get("retry_started_at"),
        "retry_resolved_at": client.get("retry_resolved_at"),

        "package_zip": client.get("package_zip"),
        "pdf": client.get("pdf"),
        "markdown": client.get("markdown"),
        "meta": client.get("meta"),

        "drive_zip_url": client.get("drive_zip_url"),
        "drive_pdf_url": client.get("drive_pdf_url"),
        "drive_markdown_url": client.get("drive_markdown_url"),
        "notion_url": client.get("notion_url"),

        "webhook_sent": client.get("webhook_sent", False),
        "email_sent": client.get("email_sent", False),
    }


def write_history(records: List[Dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with RUN_HISTORY_PATH.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"Appended {len(records)} records to {RUN_HISTORY_PATH}")


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    if not clients:
        raise RuntimeError("No clients found in distribution manifest")

    records = [
        build_history_record(manifest, client)
        for client in clients
    ]

    write_history(records)

    print("Run history write complete.")


if __name__ == "__main__":
    main()
