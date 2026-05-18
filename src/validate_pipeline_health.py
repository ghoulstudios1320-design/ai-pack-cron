import json
import os
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


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
    path = week_dir / "distribution_manifest.json"
    if not path.exists():
        raise RuntimeError(f"Missing distribution manifest: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    clients: List[Dict[str, Any]] = manifest.get("clients", [])
    client_count = int(manifest.get("client_count", 0) or 0)

    errors = []

    if client_count != len(clients):
        errors.append(f"client_count mismatch: manifest={client_count}, actual={len(clients)}")

    if manifest.get("drive_uploaded_client_count") != client_count:
        errors.append("Drive uploaded count does not match client count")

    if manifest.get("drive_upload_failed_client_count") != 0:
        errors.append("Drive upload failures detected")

    if manifest.get("notion_published_client_count") != client_count:
        errors.append("Notion published count does not match client count")

    if manifest.get("notion_publish_failed_client_count") != 0:
        errors.append("Notion publish failures detected")

    if manifest.get("webhook_sent_client_count") != client_count:
        errors.append("Webhook sent count does not match client count")

    if manifest.get("webhook_failed_client_count") != 0:
        errors.append("Webhook failures detected")

    if manifest.get("still_retry_pending_client_count") != 0:
        errors.append("Retry pending clients remain")

    for client in clients:
        client_id = client.get("client_id", "unknown")

        if client.get("delivery_status") != "confirmed":
            errors.append(f"{client_id}: final status is {client.get('delivery_status')}")

        if client.get("error"):
            errors.append(f"{client_id}: error still present: {client.get('error')}")

        required_fields = [
            "drive_zip_url",
            "drive_pdf_url",
            "drive_markdown_url",
            "notion_url",
            "uploaded_at",
            "published_at",
            "webhook_sent_at",
            "confirmed_at",
        ]

        for field in required_fields:
            if not client.get(field):
                errors.append(f"{client_id}: missing {field}")

    if errors:
        print("PIPELINE HEALTH CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("PIPELINE HEALTH CHECK PASSED")
    print(f"Week: {manifest.get('week')}")
    print(f"Clients confirmed: {client_count}")


if __name__ == "__main__":
    main()
