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


def build_fake_notion_url(client_id: str, week: str) -> str:
    return f"https://notion.mock.local/{week}/{client_id}"


def process_client(client: Dict[str, Any], week: str) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    status = client.get("delivery_status")

    if status != "uploaded":
        print(f"Skipping {client_id}: status={status}")
        return False

    if not client.get("drive_pdf_url") or not client.get("drive_zip_url"):
        client["delivery_status"] = "publish_failed"
        client["error"] = "Missing Drive URLs required for Notion publish"
        print(f"Publish failed for {client_id}: missing Drive URLs")
        return True

    client["notion_url"] = build_fake_notion_url(client_id, week)
    client["delivery_status"] = "published"
    client["published_at"] = datetime.now(timezone.utc).isoformat()
    client["error"] = None

    print(f"Simulated Notion publish for: {client_id}")
    return True


def main() -> None:
    week_dir = find_week_dir()
    week = week_dir.name

    manifest = load_manifest(week_dir)
    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    published_count = 0
    changed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)

        changed = process_client(client, week)

        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("delivery_status") == "published":
            published_count += 1

    manifest["simulated_notion_publish_completed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    manifest["simulated_published_client_count"] = published_count
    manifest["simulated_notion_changed_client_count"] = changed_count

    save_manifest(week_dir, manifest)

    print(f"Simulated Notion publishes completed: {published_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
