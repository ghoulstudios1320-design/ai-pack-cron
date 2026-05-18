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
    path = week_dir / "distribution_manifest.json"
    if not path.exists():
        raise RuntimeError(f"Missing distribution manifest: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def safe(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_manifest(week_dir)

    clients: List[Dict[str, Any]] = manifest.get("clients", [])
    created_at = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# Production Summary - {manifest.get('week')}",
        "",
        f"Generated at UTC: {created_at}",
        "",
        "## Run Status",
        "",
        f"- Client count: {manifest.get('client_count')}",
        f"- Drive upload mode: {manifest.get('drive_upload_mode')}",
        f"- Drive uploaded clients: {manifest.get('drive_uploaded_client_count')}",
        f"- Drive failed clients: {manifest.get('drive_upload_failed_client_count')}",
        f"- Notion publish mode: {manifest.get('notion_publish_mode')}",
        f"- Notion published clients: {manifest.get('notion_published_client_count')}",
        f"- Notion failed clients: {manifest.get('notion_publish_failed_client_count')}",
        f"- Webhook mode: {manifest.get('webhook_mode')}",
        f"- Webhook sent clients: {manifest.get('webhook_sent_client_count')}",
        f"- Webhook failed clients: {manifest.get('webhook_failed_client_count')}",
        f"- Recovered clients: {manifest.get('recovered_client_count')}",
        f"- Still retry pending: {manifest.get('still_retry_pending_client_count')}",
        "",
        "## Client Results",
        "",
    ]

    for client in clients:
        lines.extend(
            [
                f"### {safe(client.get('company_name'))}",
                "",
                f"- Client ID: `{safe(client.get('client_id'))}`",
                f"- Final status: `{safe(client.get('delivery_status'))}`",
                f"- Retry count: `{safe(client.get('retry_count', 0))}`",
                f"- Error: `{safe(client.get('error'))}`",
                f"- Package ZIP: {safe(client.get('drive_zip_url'))}",
                f"- PDF: {safe(client.get('drive_pdf_url'))}",
                f"- Markdown: {safe(client.get('drive_markdown_url'))}",
                f"- Notion: {safe(client.get('notion_url'))}",
                f"- Uploaded at: {safe(client.get('uploaded_at'))}",
                f"- Published at: {safe(client.get('published_at'))}",
                f"- Webhook sent at: {safe(client.get('webhook_sent_at'))}",
                f"- Confirmed at: {safe(client.get('confirmed_at'))}",
                "",
            ]
        )

    output_path = week_dir / "production_summary.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote production summary: {output_path}")


if __name__ == "__main__":
    main()
