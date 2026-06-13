"""Compatibility wrapper for client intelligence summary generation.

generate_trucking_pack imports:

    from src.client_intelligence_summary import write_client_intelligence_summary

and calls it with a client output directory during per-client generation.

The canonical combined report builder lives in src.write_client_intelligence_summary.
This wrapper supports both call styles:

1. write_client_intelligence_summary(client_output_dir)
   -> writes that client's client_intelligence_summary.md

2. write_client_intelligence_summary("2026-W50")
   -> writes the combined weekly client_intelligence_summary.md
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from src import write_client_intelligence_summary as writer


PathLike = Union[str, Path]


def _safe_client_name(meta: Dict[str, Any], client_id: str) -> str:
    return str(
        meta.get("company_name")
        or meta.get("client_name")
        or meta.get("name")
        or client_id.replace("_", " ").title()
    )


def _write_single_client_summary(client_dir: Path) -> Path:
    week_dir = client_dir.parent
    client_id = client_dir.name
    meta = writer.get_client_meta(week_dir, client_id)
    company_name = _safe_client_name(meta, client_id)

    client = {
        "client_id": client_id,
        "client_folder": client_id,
        "company_name": company_name,
    }

    operational_memory = writer.load_json(client_dir / "operational_memory.json") or {}
    trend_dashboard = writer.load_json(client_dir / "trend_dashboard.json") or {}

    operational_records = writer.extract_category_records(operational_memory)
    trend_records = writer.extract_category_records(trend_dashboard)
    records = writer.merge_category_records(operational_records, trend_records)

    groups = writer.classify_categories(records, client_id)
    signals = writer.extract_current_week_signals(week_dir, client_id)
    focus_areas = writer.recommended_focus_areas(records, client_id)

    lines = [
        "# Weekly Client Intelligence Summary",
        "",
        f"Client: `{company_name}`",
        f"Client ID: `{client_id}`",
        f"Week: `{week_dir.name}`",
        f"Memory Version: `{operational_memory.get('memory_version', 'unknown')}`",
        "",
        "## Executive Readout",
        "",
        writer.build_executive_readout(company_name, records, client_id),
        "",
        "## Trend Breakdown",
        "",
    ]

    lines.extend(writer.build_group_section("Worsening", groups["worsening"]))
    lines.extend(writer.build_group_section("New", groups["new"]))
    lines.extend(writer.build_group_section("Persistent", groups["persistent"]))
    lines.extend(writer.build_group_section("Improving", groups["improving"]))
    lines.extend(writer.build_group_section("Resolved", groups["resolved"]))

    if groups["other"]:
        lines.extend(writer.build_group_section("Other Watch Items", groups["other"]))

    lines.extend(writer.build_forward_outlook_section(records, client_id))

    lines.extend(
        [
            "## Recommended Focus",
            "",
        ]
    )

    for item in focus_areas:
        lines.append(f"- {item}")

    lines.extend([""])
    lines.extend(writer.build_raw_snapshot(records, client_id))

    output_path = client_dir / "client_intelligence_summary.md"
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {output_path}")

    return output_path


def _write_week_summary(week_dir: Path) -> Path:
    summary = writer.build_summary(week_dir)
    output_path = week_dir / "client_intelligence_summary.md"
    output_path.write_text(summary + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {output_path}")

    return output_path


def write_client_intelligence_summary(target: Optional[PathLike] = None) -> Path:
    """Write client intelligence summary.

    target may be:
    - None: use canonical week discovery and write combined weekly summary
    - a week key like "2026-W50": write combined weekly summary
    - a week output directory: write combined weekly summary
    - a client output directory: write individual client summary
    """

    if target is None:
        return _write_week_summary(writer.find_week_dir())

    target_path = Path(target)

    if isinstance(target, str) and not target_path.exists():
        week_dir = writer.OUTPUT_DIR / target
        if not week_dir.exists():
            raise FileNotFoundError(f"Week output folder not found: {week_dir}")
        return _write_week_summary(week_dir)

    if not target_path.exists():
        raise FileNotFoundError(f"Output path not found: {target_path}")

    if (target_path / "operational_memory.json").exists():
        return _write_single_client_summary(target_path)

    return _write_week_summary(target_path)


def build_summary(week_dir: Path) -> str:
    return writer.build_summary(week_dir)


def main() -> None:
    _write_week_summary(writer.find_week_dir())


__all__ = [
    "build_summary",
    "main",
    "write_client_intelligence_summary",
]


if __name__ == "__main__":
    main()
