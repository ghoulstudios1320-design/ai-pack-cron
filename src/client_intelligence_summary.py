"""Compatibility wrapper for client intelligence summary generation.

generate_trucking_pack imports:

    from src.client_intelligence_summary import write_client_intelligence_summary

The real report builder lives in src.write_client_intelligence_summary, but that
module currently exposes build_summary() and main(), not a function named
write_client_intelligence_summary(). This wrapper provides the expected function
without duplicating the report logic.
"""

from pathlib import Path
from typing import Optional

from src.write_client_intelligence_summary import (
    OUTPUT_DIR,
    build_summary,
    find_week_dir,
    main,
)


def write_client_intelligence_summary(week: Optional[str] = None) -> Path:
    """Write the client intelligence summary for the requested week.

    If week is omitted, this follows the same week-selection behavior as the
    canonical writer through find_week_dir().
    """

    if week:
        week_dir = OUTPUT_DIR / week
        if not week_dir.exists():
            raise FileNotFoundError(f"Week output folder not found: {week_dir}")
    else:
        week_dir = find_week_dir()

    summary = build_summary(week_dir)
    output_path = week_dir / "client_intelligence_summary.md"
    output_path.write_text(summary + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {output_path}")

    return output_path


__all__ = [
    "build_summary",
    "main",
    "write_client_intelligence_summary",
]


if __name__ == "__main__":
    main()
