import json, io, os
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from src.utils import ensure_output_dir, load_sa_credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
PARENT = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

def drive():
    creds_info = load_sa_credentials()
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def create_folder(service, name, parent):
    file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}
    return service.files().create(body=file_metadata, fields="id").execute()["id"]

def upload_file(service, folder_id, path: Path, mime):
    media = MediaIoBaseUpload(io.BytesIO(path.read_bytes()), mimetype=mime, resumable=True)
    file_meta = {"name": path.name, "parents": [folder_id]}
    f = service.files().create(body=file_meta, media_body=media, fields="id").execute()
    return f["id"]

def make_public(service, file_id):
    service.permissions().create(fileId=file_id, body={"role":"reader","type":"anyone"}).execute()
    return f"https://drive.google.com/uc?id={file_id}&export=download"

def main():
    out_dir, year, week = ensure_output_dir()
    svc = drive()
    weekly_folder = create_folder(svc, f"{year}-W{week:02d}", PARENT)

    md_id = upload_file(svc, weekly_folder, next(out_dir.glob("*.md")), "text/markdown")
    pdf_id = upload_file(svc, weekly_folder, next(out_dir.glob("*.pdf")), "application/pdf")

    md_url = make_public(svc, md_id)
    pdf_url = make_public(svc, pdf_id)

    meta_path = out_dir / "drive_links.json"
    meta_path.write_text(json.dumps({"md_url": md_url, "pdf_url": pdf_url, "folder_id": weekly_folder}, indent=2), encoding="utf-8")
    print("Drive links written:", meta_path)

if __name__ == "__main__":
    main()
