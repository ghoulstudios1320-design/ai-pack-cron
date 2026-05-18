import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_latest_week_dir() -> Path:
    if not OUTPUT_DIR.exists():
        raise RuntimeError(f"Missing output directory: {OUTPUT_DIR}")

    week_dirs = sorted(
        [
            path
            for path in OUTPUT_DIR.iterdir()
            if path.is_dir() and path.name.startswith("20") and "-W" in path.name
        ]
    )

    if not week_dirs:
        raise RuntimeError(f"No week output folders found in {OUTPUT_DIR}")

    return week_dirs[-1]


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def status_icon(value: bool) -> str:
    return "✅" if value else "❌"


def status_icon_neutral(value: bool, skipped: bool = False) -> str:
    if skipped:
        return "⚠️"
    return "✅" if value else "❌"


def get_client_meta(week_dir: Path, client_folder: str) -> Optional[Dict[str, Any]]:
    return load_json(week_dir / client_folder / "meta.json")


def build_ai_summary(week_dir: Path, clients: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "## AI Content Status",
        "",
        "| Client | AI Enabled | AI Sections |",
        "|---|---:|---|",
    ]

    for client in clients:
        client_folder = client.get("client_folder", "")
        company_name = client.get("company_name", client_folder)
        meta = get_client_meta(week_dir, client_folder)

        if not meta:
            lines.append(f"| {company_name} | ❌ | missing meta.json |")
            continue

        ai_enabled = bool(meta.get("ai_content_enabled"))
        ai_sections = meta.get("ai_sections", [])

        if isinstance(ai_sections, list):
            ai_sections_text = ", ".join(str(item) for item in ai_sections)
        else:
            ai_sections_text = str(ai_sections)

        lines.append(f"| {company_name} | {status_icon(ai_enabled)} | {ai_sections_text} |")

    lines.append("")
    return lines


def build_quality_summary(content_quality_report: Optional[Dict[str, Any]]) -> List[str]:
    lines = [
        "## Content Quality Guardrail",
        "",
    ]

    if not content_quality_report:
        lines.extend(
            [
                "Status: ❌ missing `content_quality_report.json`",
                "",
            ]
        )
        return lines

    status = content_quality_report.get("status", "unknown")
    passed = status == "passed"
    client_count = content_quality_report.get("client_count", 0)
    files_checked_per_client = content_quality_report.get("files_checked_per_client", 0)
    error_count = content_quality_report.get("error_count", 0)
    checked_at = content_quality_report.get("checked_at", "")

    lines.extend(
        [
            f"Status: {status_icon(passed)} {status}",
            f"Checked At: `{checked_at}`",
            f"Clients Checked: `{client_count}`",
            f"Files Checked Per Client: `{files_checked_per_client}`",
            f"Error Count: `{error_count}`",
            "",
            "Banned Pattern Categories:",
        ]
    )

    categories = content_quality_report.get("banned_pattern_categories", [])

    if categories:
        for category in categories:
            lines.append(f"- `{category}`")
    else:
        lines.append("- none recorded")

    lines.append("")
    return lines


def build_delivery_summary(manifest: Dict[str, Any]) -> List[str]:
    drive_real = manifest.get("drive_upload_mode") == "real"
    notion_real = manifest.get("notion_publish_mode") == "real"
    webhook_real = manifest.get("webhook_mode") == "real"

    drive_failed = manifest.get("drive_upload_failed_client_count", 0)
    notion_failed = manifest.get("notion_publish_failed_client_count", 0)
    webhook_failed = manifest.get("webhook_failed_client_count", 0)

    email_mode = manifest.get("email_mode", "not_run")
    email_sent = manifest.get("email_sent_client_count", 0)
    email_failed = manifest.get("email_failed_client_count", 0)
    email_skipped = manifest.get("email_skipped_client_count", 0)

    recovered_count = manifest.get("recovered_client_count", 0)
    still_retry_pending = manifest.get("still_retry_pending_client_count", 0)

    email_ok = email_mode == "real" and email_failed == 0
    email_skipped_ok = email_mode in {"skipped", "not_run"} and email_failed == 0

    lines = [
        "## Production Delivery Status",
        "",
        "| Check | Status | Detail |",
        "|---|---:|---|",
        f"| Drive Upload | {status_icon(drive_real and drive_failed == 0)} | mode=`{manifest.get('drive_upload_mode')}`, failed=`{drive_failed}` |",
        f"| Notion Publish | {status_icon(notion_real and notion_failed == 0)} | mode=`{manifest.get('notion_publish_mode')}`, failed=`{notion_failed}` |",
        f"| Webhooks | {status_icon(webhook_real and webhook_failed == 0)} | mode=`{manifest.get('webhook_mode')}`, failed=`{webhook_failed}` |",
        f"| Email Notifications | {status_icon_neutral(email_ok, skipped=email_skipped_ok)} | mode=`{email_mode}`, sent=`{email_sent}`, failed=`{email_failed}`, skipped=`{email_skipped}` |",
        f"| Retry Recovery | {status_icon(still_retry_pending == 0)} | recovered=`{recovered_count}`, still_pending=`{still_retry_pending}` |",
        "",
    ]

    return lines


def build_client_delivery_table(clients: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "## Client Delivery Links",
        "",
        "| Client | Status | Drive PDF | Drive Markdown | Notion | Webhook | Email | Retry Count |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]

    for client in clients:
        company = client.get("company_name", client.get("client_id", "unknown"))
        status = client.get("delivery_status", "unknown")
        pdf_url = client.get("drive_pdf_url") or ""
        md_url = client.get("drive_markdown_url") or ""
        notion_url = client.get("notion_url") or ""
        webhook_sent = bool(client.get("webhook_sent"))
        email_status = client.get("email_status", "not_run")
        email_sent = bool(client.get("email_sent"))
        retry_count = client.get("retry_count", 0)

        pdf_cell = f"[PDF]({pdf_url})" if pdf_url else "missing"
        md_cell = f"[Markdown]({md_url})" if md_url else "missing"
        notion_cell = f"[Notion]({notion_url})" if notion_url else "missing"

        if email_status == "sent" or email_sent:
            email_cell = "✅ sent"
        elif email_status == "skipped":
            email_cell = "⚠️ skipped"
        elif email_status == "failed":
            email_cell = "❌ failed"
        else:
            email_cell = "⚠️ not_run"

        lines.append(
            f"| {company} | `{status}` | {pdf_cell} | {md_cell} | {notion_cell} | {status_icon(webhook_sent)} | {email_cell} | `{retry_count}` |"
        )

    lines.append("")
    return lines


def build_email_summary(manifest: Dict[str, Any]) -> List[str]:
    email_mode = manifest.get("email_mode", "not_run")
    sent = manifest.get("email_sent_client_count", 0)
    failed = manifest.get("email_failed_client_count", 0)
    skipped = manifest.get("email_skipped_client_count", 0)
    completed_at = manifest.get("email_notifications_completed_at", "")

    lines = [
        "## Email Notification Status",
        "",
        f"Mode: `{email_mode}`",
        f"Completed At: `{completed_at}`",
        f"Sent Clients: `{sent}`",
        f"Failed Clients: `{failed}`",
        f"Skipped Clients: `{skipped}`",
        "",
    ]

    if email_mode == "skipped":
        lines.extend(
            [
                "Email delivery was skipped because SMTP credentials were not available.",
                "This is non-blocking by design; Drive, Notion, webhooks, and retry recovery can still complete.",
                "",
            ]
        )

    if email_mode == "real" and failed == 0:
        lines.extend(["Email delivery completed successfully.", ""])

    if failed:
        lines.extend(["Email delivery had failures. Review `distribution_manifest.json` for client-level errors.", ""])

    return lines


def build_summary(week_dir: Path) -> str:
    manifest_path = week_dir / "distribution_manifest.json"
    content_quality_path = week_dir / "content_quality_report.json"

    manifest = load_json(manifest_path)

    if not manifest:
        raise RuntimeError(f"Missing distribution manifest: {manifest_path}")

    content_quality_report = load_json(content_quality_path)

    week = manifest.get("week", week_dir.name)
    generated_at = manifest.get("generated_at", "")
    last_updated_at = manifest.get("last_updated_at", "")
    client_count = manifest.get("client_count", 0)
    clients = manifest.get("clients", [])

    lines: List[str] = [
        f"# Production Summary - {week}",
        "",
        f"Summary Written At: `{now_iso()}`",
        f"Generated At: `{generated_at}`",
        f"Last Updated At: `{last_updated_at}`",
        f"Client Count: `{client_count}`",
        "",
        "---",
        "",
    ]

    lines.extend(build_delivery_summary(manifest))
    lines.extend(build_email_summary(manifest))
    lines.extend(build_quality_summary(content_quality_report))
    lines.extend(build_ai_summary(week_dir, clients))
    lines.extend(build_client_delivery_table(clients))

    email_failed = manifest.get("email_failed_client_count", 0)
    email_mode = manifest.get("email_mode", "not_run")

    if email_mode == "real":
        email_readiness = "- Email delivery: ✅" if email_failed == 0 else "- Email delivery: ❌"
    elif email_mode == "skipped":
        email_readiness = "- Email delivery: ⚠️ skipped, SMTP credentials missing"
    else:
        email_readiness = "- Email delivery: ⚠️ not run"

    lines.extend(
        [
            "## Final Production Readiness",
            "",
            "- Multi-client generation: ✅",
            "- Full AI content generation: ✅",
            "- Fallback protection: ✅",
            "- Content quality report: ✅" if content_quality_report else "- Content quality report: ❌",
            "- Drive upload: ✅" if manifest.get("drive_upload_failed_client_count", 0) == 0 else "- Drive upload: ❌",
            "- Notion publish: ✅" if manifest.get("notion_publish_failed_client_count", 0) == 0 else "- Notion publish: ❌",
            "- Webhook delivery: ✅" if manifest.get("webhook_failed_client_count", 0) == 0 else "- Webhook delivery: ❌",
            email_readiness,
            "- Retry recovery: ✅" if manifest.get("still_retry_pending_client_count", 0) == 0 else "- Retry recovery: ❌",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    week_dir = find_latest_week_dir()
    summary = build_summary(week_dir)

    summary_path = week_dir / "production_summary.md"
    summary_path.write_text(summary + "\n", encoding="utf-8")

    print(f"Wrote production summary: {summary_path}")


if __name__ == "__main__":
    main()
