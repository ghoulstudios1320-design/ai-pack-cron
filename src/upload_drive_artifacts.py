import json
import os
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


def build_mock_drive_url(client_id: str, file_path: str) -> str:
    return f"https://drive.mock.local/{client_id}/{Path(file_path).name}"


def upload_mock(client: Dict[str, Any]) -> None:
    client_id = client["client_id"]

    client["drive_zip_url"] = build_mock_drive_url(client_id, client["package_zip"])
    client["drive_pdf_url"] = build_mock_drive_url(client_id, client["pdf"])
    client["drive_markdown_url"] = build_mock_drive_url(client_id, client["markdown"])
    client["drive_upload_mode"] = "mock"
    client["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    client["delivery_status"] = "uploaded"
    client["error"] = None


def has_drive_secrets() -> bool:
    return bool(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        and os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    )


def upload_real_placeholder(client: Dict[str, Any]) -> None:
    """
    Placeholder real adapter boundary.

    This intentionally does not call Google yet. It proves the pipeline can detect
    Drive credentials and fail safely instead of silently pretending upload worked.
    We will replace this with actual Google Drive API upload next.
    """
    raise RuntimeError(
        "Drive credentials detected, but real Drive upload implementation is not connected yet."
    )


def process_client(client: Dict[str, Any], week_dir: Path, use_real_drive: bool) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    status = client.get("delivery_status")
    if status != "ready_for_upload":
        print(f"Skipping {client_id}: status={status}")
        return False

    try:
        if use_real_drive:
            upload_real_placeholder(client)
        else:
            upload_mock(client)

        print(f"Drive upload completed for: {client_id}")
        return True

    except Exception as e:
        client["delivery_status"] = "upload_failed"
        client["error"] = str(e)
        client["drive_upload_mode"] = "real"
        client["upload_failed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Drive upload failed for {client_id}: {e}")
        return True


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    use_real_drive = has_drive_secrets()

    if use_real_drive:
        print("Drive credentials detected: real upload mode")
    else:
        print("Drive credentials not found: mock upload mode")

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    changed_count = 0
    uploaded_count = 0
    failed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)
        changed = process_client(client, week_dir, use_real_drive)
        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("delivery_status") == "uploaded":
            uploaded_count += 1

        if client.get("delivery_status") == "upload_failed":
            failed_count += 1

    manifest["drive_upload_completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["drive_upload_mode"] = "real" if use_real_drive else "mock"
    manifest["drive_uploaded_client_count"] = uploaded_count
    manifest["drive_upload_failed_client_count"] = failed_count
    manifest["drive_upload_changed_client_count"] = changed_count

    save_manifest(week_dir, manifest)

    print(f"Drive uploaded clients: {uploaded_count}")
    print(f"Drive failed clients: {failed_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
