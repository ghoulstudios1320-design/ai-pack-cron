import json
import mimetypes
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"
CLIENTS_DIR = ROOT_DIR / "clients"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_latest_week_dir() -> Path:
    week_key = os.getenv("WEEK_KEY", "").strip()

    if week_key:
        week_dir = OUTPUT_DIR / week_key
        if not week_dir.exists():
            raise RuntimeError(f"WEEK_KEY folder does not exist: {week_dir}")
        return week_dir

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


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def split_emails(value: str) -> List[str]:
    if not value:
        return []

    raw_items = value.replace(";", ",").split(",")

    return [item.strip() for item in raw_items if item.strip()]


def normalize_recipients(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        return split_emails(value)

    return []


def truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()

    if not value:
        return default

    return value in {"1", "true", "yes", "y", "on"}


def smtp_config_available() -> bool:
    required = [
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM_EMAIL",
    ]

    return all(os.getenv(key, "").strip() for key in required)


def get_smtp_port() -> int:
    value = os.getenv("SMTP_PORT", "587").strip()

    try:
        return int(value)
    except ValueError:
        return 587


def load_client_config(client_id: str) -> Dict[str, Any]:
    path = CLIENTS_DIR / f"{client_id}.json"
    data = load_json(path)

    if not data:
        return {}

    return data


def resolve_recipients(client_record: Dict[str, Any]) -> List[str]:
    client_id = str(client_record.get("client_id", "")).strip()
    client_config = load_client_config(client_id)

    recipients = normalize_recipients(client_config.get("email_recipients"))
    if recipients:
        return recipients

    recipients = normalize_recipients(client_config.get("distribution_emails"))
    if recipients:
        return recipients

    recipients = normalize_recipients(client_config.get("delivery_emails"))
    if recipients:
        return recipients

    return split_emails(os.getenv("PACK_EMAIL_TO", "").strip())


def resolve_attachment_paths(week_dir: Path, client: Dict[str, Any]) -> List[Path]:
    """Resolve customer-facing email attachments.

    Default customer delivery is PDF-only for a frictionless experience.

    Set WHOA_EMAIL_INCLUDE_BUNDLE=true if you want to attach the ZIP and
    markdown file for internal testing or admin delivery.
    """

    paths: List[Path] = []

    pdf_rel = client.get("pdf")
    zip_rel = client.get("package_zip")
    markdown_rel = client.get("markdown")

    rel_paths = [pdf_rel]

    if truthy_env("WHOA_EMAIL_INCLUDE_BUNDLE", default=False):
        rel_paths.extend([zip_rel, markdown_rel])

    for rel_path in rel_paths:
        if not rel_path:
            continue

        path = week_dir / rel_path

        if path.exists() and path.is_file():
            paths.append(path)
        else:
            print(f"Attachment missing, skipping: {path}")

    return paths


def build_email_body(client: Dict[str, Any], week: str, attachments: List[Path]) -> str:
    company_name = client.get("company_name", client.get("client_id", "Client"))

    lines = [
        f"{company_name} - Weekly Fleet Packet",
        "",
        f"Week: {week}",
        "",
        "Attached is this week's WHOA fleet packet.",
        "",
        "This packet is delivered as a PDF attachment for easy viewing on desktop or mobile.",
        "",
        "No login or software is required.",
        "",
        "Included in this weekly packet:",
        "- Recruiting content",
        "- Safety content",
        "- Driver communication",
        "- Freight update",
        "- Weekly management readout",
        "",
    ]

    if attachments:
        lines.append("Attached file:")
        for path in attachments:
            lines.append(f"- {path.name}")
        lines.append("")

    lines.extend(
        [
            "Thank you,",
            "WHOA Weekly",
        ]
    )

    return "\n".join(lines)


def attach_file(msg: EmailMessage, path: Path) -> None:
    content_type, _ = mimetypes.guess_type(str(path))

    if content_type:
        maintype, subtype = content_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    msg.add_attachment(
        path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def send_email(
    to_addresses: List[str],
    subject: str,
    body: str,
    attachments: List[Path],
) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = get_smtp_port()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    from_name = os.getenv("SMTP_FROM_NAME", "WHOA Weekly").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)

    for attachment in attachments:
        attach_file(msg, attachment)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)


def process_client(
    week_dir: Path,
    client: Dict[str, Any],
    week: str,
    email_mode: str,
) -> bool:
    company_name = client.get("company_name", client.get("client_id", "Client"))
    recipients = resolve_recipients(client)

    client["email_mode"] = email_mode
    client["email_checked_at"] = now_iso()

    if email_mode != "real":
        client["email_sent"] = False
        client["email_status"] = "skipped"
        client["email_error"] = "SMTP credentials missing; email delivery skipped."
        print(f"Email skipped for {company_name}: SMTP credentials missing")
        return False

    if not recipients:
        client["email_sent"] = False
        client["email_status"] = "skipped"
        client["email_error"] = "No email recipients configured."
        print(f"Email skipped for {company_name}: no recipients configured")
        return False

    attachments = resolve_attachment_paths(week_dir, client)

    subject = f"{company_name} Weekly Fleet Packet - {week}"
    body = build_email_body(client, week, attachments)

    try:
        send_email(recipients, subject, body, attachments)

        client["email_sent"] = True
        client["email_status"] = "sent"
        client["email_sent_at"] = now_iso()
        client["email_recipients"] = recipients
        client["email_attachment_count"] = len(attachments)
        client["email_attachments"] = [path.name for path in attachments]
        client["email_error"] = None

        print(
            f"Email sent for {company_name}: "
            f"{', '.join(recipients)} "
            f"attachments={len(attachments)}"
        )
        return True

    except Exception as exc:
        client["email_sent"] = False
        client["email_status"] = "failed"
        client["email_error"] = str(exc)
        client["email_recipients"] = recipients
        client["email_attachment_count"] = len(attachments)
        client["email_attachments"] = [path.name for path in attachments]

        print(f"Email failed for {company_name}: {exc}")
        return False


def main() -> None:
    week_dir = find_latest_week_dir()
    manifest_path = week_dir / "distribution_manifest.json"
    manifest = load_json(manifest_path)

    if not manifest:
        raise RuntimeError(f"Missing distribution manifest: {manifest_path}")

    week = manifest.get("week", week_dir.name)
    clients = manifest.get("clients", [])

    if not clients:
        raise RuntimeError(f"No clients found in manifest: {manifest_path}")

    email_mode = "real" if smtp_config_available() else "skipped"

    sent_count = 0
    failed_count = 0
    skipped_count = 0
    changed_count = 0

    for client in clients:
        before = json.dumps(client, sort_keys=True)

        sent = process_client(
            week_dir=week_dir,
            client=client,
            week=week,
            email_mode=email_mode,
        )

        after = json.dumps(client, sort_keys=True)

        if before != after:
            changed_count += 1

        status = client.get("email_status")

        if sent:
            sent_count += 1
        elif status == "failed":
            failed_count += 1
        else:
            skipped_count += 1

    manifest["email_notifications_completed_at"] = now_iso()
    manifest["email_mode"] = email_mode
    manifest["email_sent_client_count"] = sent_count
    manifest["email_failed_client_count"] = failed_count
    manifest["email_skipped_client_count"] = skipped_count
    manifest["email_changed_client_count"] = changed_count
    manifest["last_updated_at"] = now_iso()

    save_json(manifest_path, manifest)

    print(f"Saved manifest: {manifest_path}")
    print(f"Email mode: {email_mode}")
    print(f"Email sent clients: {sent_count}")
    print(f"Email failed clients: {failed_count}")
    print(f"Email skipped clients: {skipped_count}")
    print(f"Changed client records: {changed_count}")


if __name__ == "__main__":
    main()
