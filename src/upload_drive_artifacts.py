import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


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


def get_drive_service():
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if not raw_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON")

    service_account_info = json.loads(raw_json)

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=DRIVE_SCOPES,
    )

    return build("drive", "v3", credentials=credentials)


def drive_escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_child_folder(service, parent_id: str, folder_name: str) -> Optional[str]:
    safe_name = drive_escape_query(folder_name)

    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )

    response = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = response.get("files", [])

    if not files:
        return None

    return files[0]["id"]


def create_child_folder(service, parent_id: str, folder_name: str) -> str:
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }

    folder = service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True,
    ).execute()

    return folder["id"]


def get_or_create_child_folder(service, parent_id: str, folder_name: str) -> str:
    existing_id = find_child_folder(service, parent_id, folder_name)

    if existing_id:
        print(f"Found Drive folder: {folder_name}")
        return existing_id

    folder_id = create_child_folder(service, parent_id, folder_name)
    print(f"Created Drive folder: {folder_name}")
    return folder_id


def delete_existing_file(service, parent_id: str, file_name: str) -> None:
    safe_name = drive_escape_query(file_name)

    query = (
        f"name = '{safe_name}' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )

    response = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=20,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    for file in response.get("files", []):
        service.files().delete(
            fileId=file["id"],
            supportsAllDrives=True,
        ).execute()
        print(f"Deleted existing Drive file: {file_name}")


def upload_file(service, parent_id: str, local_path: Path, mime_type: str) -> Dict[str, str]:
    if not local_path.exists() or not local_path.is_file():
        raise RuntimeError(f"Missing local file for Drive upload: {local_path}")

    delete_existing_file(service, parent_id, local_path.name)

    metadata = {
        "name": local_path.name,
        "parents": [parent_id],
    }

    media = MediaFileUpload(
        str(local_path),
        mimetype=mime_type,
        resumable=False,
    )

    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink, webContentLink",
        supportsAllDrives=True,
    ).execute()

    file_id = uploaded["id"]

    try:
        service.permissions().create(
            fileId=file_id,
            body={
                "role": "reader",
                "type": "anyone",
            },
            supportsAllDrives=True,
        ).execute()
    except Exception as e:
        print(f"Warning: could not make file public: {local_path.name}: {e}")

    file_info = service.files().get(
        fileId=file_id,
        fields="id, webViewLink, webContentLink",
        supportsAllDrives=True,
    ).execute()

    return {
        "id": file_info["id"],
        "webViewLink": file_info.get("webViewLink", ""),
        "webContentLink": file_info.get("webContentLink", ""),
    }


def upload_real(client: Dict[str, Any], week_dir: Path, service, root_drive_folder_id: str) -> None:
    week_key = week_dir.name
    client_id = client["client_id"]

    week_folder_id = get_or_create_child_folder(
        service,
        root_drive_folder_id,
        week_key,
    )

    client_folder_id = get_or_create_child_folder(
        service,
        week_folder_id,
        client_id,
    )

    package_path = week_dir / client["package_zip"]
    pdf_path = week_dir / client["pdf"]
    markdown_path = week_dir / client["markdown"]

    zip_result = upload_file(
        service,
        client_folder_id,
        package_path,
        "application/zip",
    )

    pdf_result = upload_file(
        service,
        client_folder_id,
        pdf_path,
        "application/pdf",
    )

    markdown_result = upload_file(
        service,
        client_folder_id,
        markdown_path,
        "text/markdown",
    )

    client["drive_zip_url"] = zip_result["webViewLink"]
    client["drive_pdf_url"] = pdf_result["webViewLink"]
    client["drive_markdown_url"] = markdown_result["webViewLink"]

    client["drive_zip_file_id"] = zip_result["id"]
    client["drive_pdf_file_id"] = pdf_result["id"]
    client["drive_markdown_file_id"] = markdown_result["id"]

    client["drive_week_folder_id"] = week_folder_id
    client["drive_client_folder_id"] = client_folder_id

    client["drive_upload_mode"] = "real"
    client["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    client["delivery_status"] = "uploaded"
    client["error"] = None


def process_client(
    client: Dict[str, Any],
    week_dir: Path,
    use_real_drive: bool,
    service=None,
    root_drive_folder_id: Optional[str] = None,
) -> bool:
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
            if service is None or not root_drive_folder_id:
                raise RuntimeError("Real Drive upload requested without service/folder ID")
            upload_real(client, week_dir, service, root_drive_folder_id)
        else:
            upload_mock(client)

        print(f"Drive upload completed for: {client_id}")
        return True

    except Exception as e:
        client["delivery_status"] = "upload_failed"
        client["error"] = str(e)
        client["drive_upload_mode"] = "real" if use_real_drive else "mock"
        client["upload_failed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Drive upload failed for {client_id}: {e}")
        return True


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    use_real_drive = has_drive_secrets()

    service = None
    root_drive_folder_id = None

    if use_real_drive:
        print("Drive credentials detected: real upload mode")
        service = get_drive_service()
        root_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    else:
        print("Drive credentials not found: mock upload mode")

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    changed_count = 0
    uploaded_count = 0
    failed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)

        changed = process_client(
            client,
            week_dir,
            use_real_drive,
            service=service,
            root_drive_folder_id=root_drive_folder_id,
        )

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
