"""Legacy simulated webhook notifier removed.

WHOA delivery now uses:
- Notion publishing
- Email delivery

This module remains as a no-op compatibility shim so any old workflow step that
still runs:

    python -m src.simulate_webhook_notify

will complete successfully without mutating distribution_manifest.json,
delivery_status, webhook fields, or retry state.
"""

from datetime import datetime, timezone


def main() -> None:
    print("Simulated webhook notify disabled.")
    print("Delivery path is now Notion + Email.")
    print(f"Checked at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
