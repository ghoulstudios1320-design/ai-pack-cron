import json
import os
from datetime import datetime, timezone
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
    manifest_path = week_dir / "distribution_manifest.json"

    if not manifest_path.exists():
        raise RuntimeError(f"Missing distribution manifest: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(week_dir: Path, manifest: Dict[str, Any]) -> None:
    manifest_path = week_dir / "distribution_manifest.json"

    manifest["last_updated_at"] = datetime.now(timezone.utc).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Saved manifest: {manifest_path}")


def build_mock_payload(client: Dict[str, Any], week: str) -> Dict[str, Any]:
    return {
        "week": week,
        "client_id": client.get("client_id"),
        "company_name": client.get("company_name"),
        "delivery_status": client.get("delivery_status"),
        "drive_zip_url": client.get("drive_zip_url"),
        "drive_pdf_url": client.get("drive_pdf_url"),
        "drive_markdown_url": client.get("drive_markdown_url"),
        "notion_url": client.get("notion_url"),
    }


def process_client(client: Dict[str, Any], week: str) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    status = client.get("delivery_status")

    if status != "published":
        print(f"Skipping {client_id}: status={status}")
        return False

    if not client.get("notion_url"):
        client["delivery_status"] = "notify_failed"
        client["error"] = "Missing Notion URL required for webhook notification"
        print(f"Notify failed for {client_id}: missing Notion URL")
        return True

    payload = build_mock_payload(client, week)

    client["webhook_sent"] = True
    client["webhook_sent_at"] = datetime.now(timezone.utc).isoformat()
    client["webhook_payload_preview"] = payload
    client["delivery_status"] = "notified"
    client["error"] = None

    print(f"Simulated webhook notify for: {client_id}")
    return True


def main() -> None:
    week_dir = find_week_dir()
    week = week_dir.name

    manifest = load_manifest(week_dir)
    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    notified_count = 0
    changed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)

        changed = process_client(client, week)

        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("delivery_status") == "notified":
            notified_count += 1

    manifest["simulated_webhook_notify_completed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    manifest["simulated_notified_client_count"] = notified_count
    manifest["simulated_webhook_changed_client_count"] = changed_count

    save_manifest(week_dir, manifest)

    print(f"Simulated webhook notifications completed: {notified_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
