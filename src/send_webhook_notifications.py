import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved manifest: {manifest_path}")


def build_payload(client: Dict[str, Any], week: str) -> Dict[str, Any]:
    return {
        "week": week,
        "client_id": client.get("client_id"),
        "company_name": client.get("company_name"),
        "delivery_status": client.get("delivery_status"),
        "package_zip": client.get("package_zip"),
        "pdf": client.get("pdf"),
        "markdown": client.get("markdown"),
        "drive_zip_url": client.get("drive_zip_url"),
        "drive_pdf_url": client.get("drive_pdf_url"),
        "drive_markdown_url": client.get("drive_markdown_url"),
        "notion_url": client.get("notion_url"),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "whoa-trucking-pack-webhook/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "response_body": body[:1000],
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": e.code,
            "response_body": body[:1000],
        }
    except Exception as e:
        return {
            "ok": False,
            "status_code": None,
            "response_body": str(e),
        }


def process_client(client: Dict[str, Any], week: str, webhook_url: Optional[str]) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    if client.get("delivery_status") not in ["published", "notified", "confirmed"]:
        print(f"Skipping {client_id}: status={client.get('delivery_status')}")
        return False

    payload = build_payload(client, week)

    if not webhook_url:
        client["webhook_sent"] = True
        client["webhook_mode"] = "mock"
        client["webhook_sent_at"] = datetime.now(timezone.utc).isoformat()
        client["webhook_payload_preview"] = payload

        if client.get("delivery_status") == "published":
            client["delivery_status"] = "notified"

        print(f"Mock webhook recorded for: {client_id}")
        return True

    result = post_json(webhook_url, payload)

    client["webhook_mode"] = "real"
    client["webhook_sent_at"] = datetime.now(timezone.utc).isoformat()
    client["webhook_status_code"] = result.get("status_code")
    client["webhook_response_preview"] = result.get("response_body")
    client["webhook_payload_preview"] = payload

    if result.get("ok"):
        client["webhook_sent"] = True
        client["error"] = None

        if client.get("delivery_status") == "published":
            client["delivery_status"] = "notified"

        print(f"Webhook sent for: {client_id}")
        return True

    client["webhook_sent"] = False
    client["delivery_status"] = "notify_failed"
    client["error"] = f"Webhook failed: {result.get('status_code')} {result.get('response_body')}"
    print(f"Webhook failed for: {client_id}")
    return True


def main() -> None:
    week_dir = find_week_dir()
    week = week_dir.name
    webhook_url = os.getenv("WEBHOOK_URL", "").strip() or None

    if webhook_url:
        print("WEBHOOK_URL found: sending real webhooks")
    else:
        print("No WEBHOOK_URL set: using mock webhook mode")

    manifest = load_manifest(week_dir)
    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    changed_count = 0
    sent_count = 0
    failed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)
        changed = process_client(client, week, webhook_url)
        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("webhook_sent"):
            sent_count += 1

        if client.get("delivery_status") == "notify_failed":
            failed_count += 1

    manifest["webhook_notifications_completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["webhook_changed_client_count"] = changed_count
    manifest["webhook_sent_client_count"] = sent_count
    manifest["webhook_failed_client_count"] = failed_count
    manifest["webhook_mode"] = "real" if webhook_url else "mock"

    save_manifest(week_dir, manifest)

    print(f"Webhook sent clients: {sent_count}")
    print(f"Webhook failed clients: {failed_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
