import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


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


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def has_core_delivery(client: Dict[str, Any], email_mode: str) -> bool:
    notion_ok = client.get("notion_publish_mode") == "real" and bool(client.get("notion_url"))

    if email_mode == "real":
        email_ok = client.get("email_status") == "sent" or bool(client.get("email_sent"))
    elif email_mode == "skipped":
        email_ok = True
    else:
        email_ok = False

    return notion_ok and email_ok


def validate_manifest(manifest: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    client_count = manifest.get("client_count", 0)
    clients = manifest.get("clients", [])

    if client_count != len(clients):
        errors.append(f"Client count mismatch: client_count={client_count}, actual={len(clients)}")

    notion_mode = manifest.get("notion_publish_mode")
    notion_failed = manifest.get("notion_publish_failed_client_count", 0)
    notion_published = manifest.get("notion_published_client_count", 0)

    email_mode = manifest.get("email_mode", "not_run")
    email_failed = manifest.get("email_failed_client_count", 0)
    email_sent = manifest.get("email_sent_client_count", 0)
    email_skipped = manifest.get("email_skipped_client_count", 0)

    webhook_mode = manifest.get("webhook_mode", "not_run")
    webhook_failed = manifest.get("webhook_failed_client_count", 0)
    webhook_sent = manifest.get("webhook_sent_client_count", 0)

    recovered_count = manifest.get("recovered_client_count", 0)
    still_retry_pending = manifest.get("still_retry_pending_client_count", 0)

    if notion_mode != "real":
        errors.append(f"Notion publish mode is not real: {notion_mode}")

    if notion_failed:
        errors.append(f"Notion publish failures detected: {notion_failed}")

    if notion_published != client_count:
        errors.append(f"Notion published count does not match client count: published={notion_published}, clients={client_count}")

    if email_mode == "real":
        print("Email health OK: mode=real")

        if email_failed:
            errors.append(f"Email failures detected: {email_failed}")

        if email_sent != client_count:
            errors.append(f"Email sent count does not match client count: sent={email_sent}, clients={client_count}")

        if email_skipped:
            warnings.append(f"Email skipped clients detected even though mode is real: skipped={email_skipped}")

    elif email_mode == "skipped":
        warnings.append("Email delivery skipped because SMTP credentials were missing.")
    else:
        errors.append(f"Email delivery did not run or unknown mode: {email_mode}")

    if webhook_mode == "real":
        if webhook_failed:
            warnings.append(f"Webhook failures detected: {webhook_failed}")

        if webhook_sent != client_count:
            warnings.append(f"Webhook sent count does not match client count: sent={webhook_sent}, clients={client_count}")

    elif webhook_mode == "skipped":
        warnings.append("Webhook delivery skipped.")
    else:
        warnings.append(f"Webhook delivery did not run or unknown mode: {webhook_mode}")

    if still_retry_pending:
        errors.append(f"Retry recovery still pending for clients: {still_retry_pending}")

    if recovered_count < client_count:
        warnings.append(f"Recovered client count is lower than client count: recovered={recovered_count}, clients={client_count}")

    for client in clients:
        company = client.get("company_name", client.get("client_id", "unknown"))
        status = client.get("delivery_status", "unknown")
        error = client.get("error")
        confirmed_at = client.get("confirmed_at")

        notion_ok = client.get("notion_publish_mode") == "real" and bool(client.get("notion_url"))

        if email_mode == "real":
            email_ok = client.get("email_status") == "sent" or bool(client.get("email_sent"))
        elif email_mode == "skipped":
            email_ok = True
        else:
            email_ok = False

        webhook_ok = bool(client.get("webhook_sent"))
        core_ok = notion_ok and email_ok

        if not notion_ok:
            errors.append(f"{company}: Notion publish incomplete")

        if email_mode == "real" and not email_ok:
            errors.append(f"{company}: email delivery incomplete")

        if not webhook_ok:
            warnings.append(f"{company}: webhook not confirmed")

        if status in {"notify_failed", "webhook_failed"}:
            if core_ok:
                warnings.append(f"{company}: final status is {status}, but Notion/email delivery succeeded")
            else:
                errors.append(f"{company}: final status is {status}")

        elif status not in {"confirmed", "published", "delivered"}:
            if core_ok:
                warnings.append(f"{company}: final status is {status}, but Notion/email delivery succeeded")
            else:
                errors.append(f"{company}: final status is {status}")

        if error:
            error_text = str(error)

            if "Webhook failed" in error_text or "Queue is full" in error_text:
                if core_ok:
                    warnings.append(f"{company}: webhook error present but non-fatal: {error_text}")
                else:
                    errors.append(f"{company}: error still present: {error_text}")
            else:
                errors.append(f"{company}: error still present: {error_text}")

        if not confirmed_at:
            if core_ok:
                warnings.append(f"{company}: missing confirmed_at, but Notion/email delivery succeeded")
            else:
                errors.append(f"{company}: missing confirmed_at")

    return errors, warnings


def validate_content_quality(week_dir: Path) -> List[str]:
    errors: List[str] = []
    report_path = week_dir / "content_quality_report.json"

    if not report_path.exists():
        errors.append("Missing content_quality_report.json")
        return errors

    report = load_json(report_path)

    if report.get("status") != "passed":
        errors.append(f"Content quality status is not passed: {report.get('status')}")

    if report.get("error_count", 0):
        errors.append(f"Content quality errors detected: {report.get('error_count')}")

    return errors


def validate_required_outputs(week_dir: Path, manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    required_root_files = [
        "distribution_manifest.json",
        "master_index.json",
        "content_quality_report.json",
    ]

    optional_root_files = [
        "ai_memory_report.json",
        "client_intelligence_summary.md",
        "production_summary.md",
    ]

    for filename in required_root_files:
        if not (week_dir / filename).exists():
            errors.append(f"Missing root output file: {filename}")

    for filename in optional_root_files:
        if not (week_dir / filename).exists():
            print(f"Optional output not found yet: {filename}")

    clients = manifest.get("clients", [])

    required_client_files = [
        "full_pack.md",
        "full_pack.pdf",
        "meta.json",
        "recruiting_posts.md",
        "social_posts.md",
        "safety_reminders.md",
        "company_update.md",
        "freight_digest.md",
    ]

    optional_client_files = [
        "operational_memory.json",
        "trend_dashboard.md",
        "client_intelligence_summary.md",
    ]

    for client in clients:
        client_folder = client.get("client_folder", client.get("client_id", ""))
        client_dir = week_dir / client_folder

        if not client_dir.exists():
            errors.append(f"Missing client output folder: {client_folder}")
            continue

        for filename in required_client_files:
            path = client_dir / filename
            if not path.exists():
                errors.append(f"{client_folder}: missing {filename}")
            elif path.stat().st_size == 0:
                errors.append(f"{client_folder}: empty {filename}")

        for filename in optional_client_files:
            path = client_dir / filename
            if path.exists() and path.stat().st_size == 0:
                errors.append(f"{client_folder}: empty optional file {filename}")

    return errors


def main() -> None:
    week_dir = find_week_dir()
    manifest = load_json(week_dir / "distribution_manifest.json")

    errors: List[str] = []
    warnings: List[str] = []

    manifest_errors, manifest_warnings = validate_manifest(manifest)
    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)

    errors.extend(validate_content_quality(week_dir))
    errors.extend(validate_required_outputs(week_dir, manifest))

    if errors:
        print("PIPELINE HEALTH CHECK FAILED")
        for error in errors:
            print(f"- {error}")

        if warnings:
            print("")
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")

        raise SystemExit(1)

    if warnings:
        print("PIPELINE HEALTH CHECK PASSED WITH WARNINGS")
        for warning in warnings:
            print(f"- {warning}")
        return

    print("PIPELINE HEALTH CHECK PASSED")


if __name__ == "__main__":
    main()
