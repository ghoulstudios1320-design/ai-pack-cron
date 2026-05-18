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
            raise RuntimeError(f"WEEK_KEY was set but output folder does not exist: {week_dir}")
        return week_dir

    if not OUTPUT_DIR.exists():
        raise RuntimeError(f"Output directory does not exist: {OUTPUT_DIR}")

    week_dirs = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]

    if not week_dirs:
        raise RuntimeError(f"No week folders found in: {OUTPUT_DIR}")

    return sorted(week_dirs, key=lambda p: p.name)[-1]


def load_master_index(week_dir: Path) -> Dict[str, Any]:
    index_path = week_dir / "master_index.json"

    if not index_path.exists():
        raise RuntimeError(f"Missing master_index.json: {index_path}")

    with index_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_distribution_manifest(master_index: Dict[str, Any]) -> Dict[str, Any]:
    clients: List[Dict[str, Any]] = []

    for client in master_index.get("clients", []):
        clients.append(
            {
                "client_id": client.get("client_id"),
                "company_name": client.get("company_name"),
                "package_zip": client.get("package_zip"),
                "client_folder": client.get("client_folder"),
                "pdf": client.get("pdf"),
                "markdown": client.get("markdown"),
                "meta": client.get("meta"),

                "drive_zip_url": None,
                "drive_pdf_url": None,
                "drive_markdown_url": None,
                "notion_url": None,
                "webhook_sent": False,
                "email_sent": False,
                "delivery_status": "ready_for_upload",
                "error": None,
            }
        )

    return {
        "week": master_index.get("week"),
        "generated_at": master_index.get("generated_at"),
        "distribution_manifest_created_at": datetime.now(timezone.utc).isoformat(),
        "client_count": len(clients),
        "clients": clients,
    }


def main() -> None:
    week_dir = find_week_dir()
    master_index = load_master_index(week_dir)

    distribution_manifest = build_distribution_manifest(master_index)

    output_path = week_dir / "distribution_manifest.json"
    output_path.write_text(
        json.dumps(distribution_manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote distribution manifest: {output_path}")


if __name__ == "__main__":
    main()
