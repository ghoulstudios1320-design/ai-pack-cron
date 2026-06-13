"""Legacy webhook notifier removed.

This file used the old Make/webhook + Drive-link notification path.
WHOA now delivers through:
- Notion publishing
- Email delivery

The module remains as a no-op compatibility shim so any old workflow step that
still runs:

    python -m src.notify_webhook

will complete successfully without requiring WEBHOOK_URL, WEBHOOK_TOKEN,
requests, drive_links.json, or root meta.json.
"""

from datetime import datetime, timezone


def main() -> None:
    print("Legacy notify_webhook disabled.")
    print("Delivery path is now Notion + Email.")
    print(f"Checked at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
