# src/upload_drive.py
import os, json
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

PARENT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

def drive_service():
    if not SA_JSON:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    info = json.loads(SA_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def find_or_create_folder(svc, name: str, parent_id: str) -> str:
    # Look for existing child folder with this name under the parent
    q = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{name.replace(\"'\",\"\\'\")}' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    resp = svc.files().list(
        q=q,
        fields="files(id,name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        corpora="allDrives",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = svc.files().create(
        body=meta,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return folder["id"]

def set_anyone_reader(svc, file_id: str) -> None:
    svc.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()

def upload_file(svc, parent_id: str, path: Path, mimetype: str) -> str:
    file_meta = {"name": path.name, "parents": [parent_id]}
    media = MediaFileUpload(path.as_posix(), mimetype=mimetype, resumable=False)
    created = svc.files().create(
        body=file_meta,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    file_id = created["id"]
    set_anyone_reader(svc, file_id)
    return file_id

def main():
    if not PARENT_FOLDER_ID:
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is not set")

    out_dirs = sorted(Path("output").glob("*"))
    if not out_dirs:
        raise RuntimeError("No output/* folder found")
    out_dir = out_dirs[-1]  # e.g., 2025-W39

    svc = drive_service()

    # Create/find week folder under the shared parent folder
    week_folder_name = out_dir.name  # keep same (e.g., 2025-W39)
    weekly_folder_id = find_or_create_folder(svc, week_folder_name, PARENT_FOLDER_ID)

    # Find generated files
    md_file: Optional[Path] = next(iter(out_dir.glob("*.md")), None)
    pdf_file: Optional[Path] = next(iter(out_dir.glob("*.pdf")), None)

    if not md_file and not pdf_file:
        raise RuntimeError(f"No .md or .pdf files found in {out_dir}")

    links = {}

    if pdf_file:
        pdf_id = upload_file(svc, weekly_folder_id, pdf_file, "application/pdf")
        links["pdf_url"] = f"https://drive.google.com/uc?id={pdf_id}"

    if md_file:
        md_id = upload_file(svc, weekly_folder_id, md_file, "text/markdown")
        links["md_url"] = f"https://drive.google.com/uc?id={md_id}"

    # Also store the week folder link as a fallback
    links["folder_url"] = f"https://drive.google.com/drive/folders/{weekly_folder_id}"

    # Write links for later steps
    (out_dir / "drive_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Uploaded to Drive:")
    for k, v in links.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
