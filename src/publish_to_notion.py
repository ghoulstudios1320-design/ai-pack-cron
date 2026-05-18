import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"

NOTION_VERSION = "2022-06-28"


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


def has_notion_secrets() -> bool:
    return bool(
        os.getenv("NOTION_API_KEY", "").strip()
        and os.getenv("NOTION_DATABASE_ID", "").strip()
    )


def build_mock_notion_url(week: str, client_id: str) -> str:
    return f"https://notion.mock.local/{week}/{client_id}"


def publish_mock(client: Dict[str, Any], week: str) -> None:
    client["notion_url"] = build_mock_notion_url(
        week,
        client["client_id"],
    )

    client["published_at"] = datetime.now(timezone.utc).isoformat()
    client["delivery_status"] = "published"
    client["notion_publish_mode"] = "mock"
    client["error"] = None


def notion_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def create_notion_page(
    api_key: str,
    database_id: str,
    week: str,
    client: Dict[str, Any],
) -> Dict[str, Any]:

    payload = {
        "parent": {
            "database_id": database_id,
        },
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": f"{client['company_name']} - {week}"
                        }
                    }
                ]
            },
            "Client ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": client["client_id"]
                        }
                    }
                ]
            },
            "Week": {
                "rich_text": [
                    {
                        "text": {
                            "content": week
                        }
                    }
                ]
            },
            "Status": {
                "select": {
                    "name": client["delivery_status"]
                }
            },
            "PDF URL": {
                "url": client.get("drive_pdf_url")
            },
            "ZIP URL": {
                "url": client.get("drive_zip_url")
            },
            "Markdown URL": {
                "url": client.get("drive_markdown_url")
            },
        }
    }

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers(api_key),
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def publish_real(
    client: Dict[str, Any],
    week: str,
    api_key: str,
    database_id: str,
) -> None:

    result = create_notion_page(
        api_key,
        database_id,
        week,
        client,
    )

    client["notion_url"] = result.get("url")
    client["notion_page_id"] = result.get("id")

    client["published_at"] = datetime.now(timezone.utc).isoformat()
    client["delivery_status"] = "published"
    client["notion_publish_mode"] = "real"
    client["error"] = None


def process_client(
    client: Dict[str, Any],
    week: str,
    use_real_notion: bool,
    api_key: Optional[str] = None,
    database_id: Optional[str] = None,
) -> bool:

    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    status = client.get("delivery_status")

    if status != "uploaded":
        print(f"Skipping {client_id}: status={status}")
        return False

    try:
        if use_real_notion:
            publish_real(
                client,
                week,
                api_key,
                database_id,
            )
        else:
            publish_mock(client, week)

        print(f"Published to Notion: {client_id}")
        return True

    except Exception as e:
        client["delivery_status"] = "publish_failed"
        client["error"] = str(e)
        client["notion_publish_mode"] = "real" if use_real_notion else "mock"
        client["publish_failed_at"] = datetime.now(timezone.utc).isoformat()

        print(f"Notion publish failed for {client_id}: {e}")
        return True


def main() -> None:
    week_dir = find_week_dir()
    week = week_dir.name

    manifest = load_manifest(week_dir)

    use_real_notion = has_notion_secrets()

    api_key = os.getenv("NOTION_API_KEY", "").strip()
    database_id = os.getenv("NOTION_DATABASE_ID", "").strip()

    if use_real_notion:
        print("Notion credentials detected: real publish mode")
    else:
        print("Notion credentials not found: mock publish mode")

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    changed_count = 0
    published_count = 0
    failed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)

        changed = process_client(
            client,
            week,
            use_real_notion,
            api_key=api_key,
            database_id=database_id,
        )

        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("delivery_status") == "published":
            published_count += 1

        if client.get("delivery_status") == "publish_failed":
            failed_count += 1

    manifest["notion_publish_completed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    manifest["notion_publish_mode"] = (
        "real" if use_real_notion else "mock"
    )

    manifest["notion_published_client_count"] = published_count
    manifest["notion_publish_failed_client_count"] = failed_count
    manifest["notion_publish_changed_client_count"] = changed_count

    save_manifest(week_dir, manifest)

    print(f"Notion published clients: {published_count}")
    print(f"Notion failed clients: {failed_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
