"""Webhook notifications removed.

WHOA delivery now uses:
- Notion publishing as the system of record
- Email delivery as the customer-facing notification channel

This module remains as a no-op compatibility shim so any existing workflow step
that still runs:

    python -m src.send_webhook_notifications

will complete successfully without mutating distribution_manifest.json or
marking clients as notify_failed.
"""

from datetime import datetime, timezone


def main() -> None:
    print("Webhook notifications disabled.")
    print("Delivery path is now Notion + Email.")
    print(f"Checked at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
