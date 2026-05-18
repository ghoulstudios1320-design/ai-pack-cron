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


def process_client(client: Dict[str, Any]) -> bool:
    client_id = client.get("client_id")

    if not client_id:
        print("Skipping missing client_id")
        return False

    status = client.get("delivery_status")

    if status != "retry_pending":
        print(f"Skipping {client_id}: status={status}")
        return False

    retry_count = int(client.get("retry_count", 0) or 0)

    client["delivery_status"] = "retrying"
    client["retry_started_at"] = datetime.now(timezone.utc).isoformat()

    # Mock recovery succeeds if this is at least the first retry.
    if retry_count >= 1:
        client["delivery_status"] = "confirmed"
        client["error"] = None
        client["last_error"] = None
        client["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        client["retry_resolved_at"] = datetime.now(timezone.utc).isoformat()
        client["retry_after"] = None
        print(f"Recovered retry for {client_id}")
        return True

    client["delivery_status"] = "retry_pending"
    client["error"] = "Retry attempted before retry_count was incremented"
    client["last_error"] = client["error"]
    client["retry_count"] = retry_count + 1
    client["retry_after"] = "next_run"

    print(f"Retry still pending for {client_id}")
    return True


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    clients: List[Dict[str, Any]] = manifest.get("clients", [])

    changed_count = 0
    recovered_count = 0
    still_pending_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)
        changed = process_client(client)
        after = json.dumps(client, sort_keys=True)

        if changed and before != after:
            changed_count += 1

        if client.get("delivery_status") == "confirmed":
            recovered_count += 1

        if client.get("delivery_status") == "retry_pending":
            still_pending_count += 1

    manifest["simulated_retry_recovery_completed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    manifest["simulated_retry_recovery_changed_client_count"] = changed_count
    manifest["recovered_client_count"] = recovered_count
    manifest["still_retry_pending_client_count"] = still_pending_count

    save_manifest(week_dir, manifest)

    print(f"Recovered clients: {recovered_count}")
    print(f"Still retry pending clients: {still_pending_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
