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


def build_fake_drive_url(client_id: str, artifact_name: str) -> str:
    return (
        f"https://drive.mock.local/"
        f"{client_id}/"
        f"{artifact_name}"
    )


def process_client(client: Dict[str, Any]) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping client with missing client_id")
        return False

    status = client.get("delivery_status")

    if status != "ready_for_upload":
        print(f"Skipping {client_id}: status={status}")
        return False

    package_zip = client.get("package_zip")
    pdf = client.get("pdf")
    markdown = client.get("markdown")

    client["drive_zip_url"] = build_fake_drive_url(
        client_id,
        Path(package_zip).name,
    )

    client["drive_pdf_url"] = build_fake_drive_url(
        client_id,
        Path(pdf).name,
    )

    client["drive_markdown_url"] = build_fake_drive_url(
        client_id,
        Path(markdown).name,
    )

    client["delivery_status"] = "uploaded"

    client["uploaded_at"] = datetime.now(timezone.utc).isoformat()

    print(f"Simulated upload for: {client_id}")

    return True


def main() -> None:
    week_dir = find_week_dir()

    manifest = load_manifest(week_dir)

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    updated_count = 0

    for client in clients:
        if process_client(client):
            updated_count += 1

    manifest["simulated_distribution_completed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    manifest["simulated_uploaded_client_count"] = updated_count

    save_manifest(week_dir, manifest)

    print(f"Simulated uploads completed: {updated_count}")


if __name__ == "__main__":
    main()
