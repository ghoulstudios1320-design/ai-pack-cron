import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


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

    print(f"Updated manifest: {manifest_path}")


def update_client_record(
    manifest: Dict[str, Any],
    client_id: str,
    field: str,
    value: Any,
) -> bool:
    clients = manifest.get("clients", [])

    for client in clients:
        if client.get("client_id") == client_id:
            client[field] = value
            return True

    return False


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--client-id", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--value", required=True)

    args = parser.parse_args()

    week_dir = find_week_dir()

    manifest = load_manifest(week_dir)

    updated = update_client_record(
        manifest,
        args.client_id,
        args.field,
        args.value,
    )

    if not updated:
        raise RuntimeError(
            f"Client not found in distribution manifest: {args.client_id}"
        )

    save_manifest(week_dir, manifest)

    print(
        f"Updated client '{args.client_id}' field '{args.field}' -> '{args.value}'"
    )


if __name__ == "__main__":
    main()
