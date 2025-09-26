import os, json, io
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

def drive():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def ensure_week_folder(svc, parent_id: str, name: str) -> str:
    q = f"'{parent_id}' in parents and name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = svc.files().list(q=q, fields="files(id,name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    items = res.get("files", [])
    if items:
        return items[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    f = svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()
    return f["id"]

def upload_file(svc, folder_id: str, path: Path, mime: str) -> str:
    media = MediaIoBaseUpload(io.BytesIO(path.read_bytes()), mimetype=mime, resumable=True)
    meta = {"name": path.name, "parents": [folder_id]}
    f = svc.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True).execute()
    return f["id"]

def make_public_link(svc, file_id: str) -> str:
    # Turn on "Anyone with the link: Viewer"
    svc.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        supportsAllDrives=True
    ).execute()
    # Direct download-ish link
    return f"https://drive.google.com/uc?id={file_id}"

def main():
    svc = drive()
    parent = os.environ["GOOGLE_DRIVE_FOLDER_ID"]  # MUST be a folder inside a Shared drive
    out_root = Path("output")
    weekly = sorted(out_root.glob("*"))[-1]  # latest run folder, e.g. 2025-W39
    week_name = weekly.name

    week_folder_id = ensure_week_folder(svc, parent, week_name)

    md_path  = next(weekly.glob("*.md"))
    pdf_path = next(weekly.glob("*.pdf"))

    md_id  = upload_file(svc, week_folder_id, md_path,  "text/markdown")
    pdf_id = upload_file(svc, week_folder_id, pdf_path, "application/pdf")

    md_url  = make_public_link(svc, md_id)
    pdf_url = make_public_link(svc, pdf_id)

    (weekly / "drive_links.json").write_text(json.dumps({
        "folder_id": week_folder_id,
        "md_url": md_url,
        "pdf_url": pdf_url
    }, indent=2), encoding="utf-8")

    print(f"[OK] Uploaded to Shared Drive {week_name}. Links -> MD: {md_url} | PDF: {pdf_url}")

if __name__ == "__main__":
    main()
