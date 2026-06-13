import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


REQUIRED_CONTENT_FILES = [
    "full_pack.md",
    "freight_digest.md",
    "safety_reminders.md",
    "company_update.md",
    "recruiting_posts.md",
    "social_posts.md",
]


REQUIRED_CLIENT_INTELLIGENCE_HEADINGS = [
    "# Weekly Client Intelligence Summary",
    "## Executive Readout",
    "## Trend Breakdown",
    "## Recommended Focus",
    "## Raw Category Snapshot",
]


MEMORY_CATEGORIES = [
    "appointment_pressure",
    "detention",
    "freight_volume",
    "weather_disruption",
    "equipment_issues",
    "customer_pressure",
    "lane_activity",
]


def _repo_root() -> Path:
    return Path.cwd()


def _output_root() -> Path:
    return _repo_root() / "output"


def _current_week() -> str:
    env_week = os.getenv("WEEK_KEY") or os.getenv("WEEK") or os.getenv("WHOA_WEEK")
    if env_week:
        return env_week.strip()

    output_root = _output_root()

    if not output_root.exists():
        raise FileNotFoundError("Output folder not found and WEEK_KEY was not set.")

    week_dirs = sorted(
        path.name
        for path in output_root.iterdir()
        if path.is_dir() and re.match(r"^\d{4}-W\d{2}$", path.name)
    )

    if not week_dirs:
        raise FileNotFoundError("No weekly output folders found and WEEK_KEY was not set.")

    return week_dirs[-1]


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_client_output_dir(path: Path) -> bool:
    if not path.is_dir():
        return False

    if path.name.startswith("_"):
        return False

    return any((path / filename).exists() for filename in REQUIRED_CONTENT_FILES)


def _client_dirs(week_dir: Path) -> List[Path]:
    return sorted(
        [path for path in week_dir.iterdir() if _is_client_output_dir(path)],
        key=lambda path: path.name,
    )


def _add_error(
    errors: List[Dict[str, str]],
    path: Path,
    error_type: str,
    detail: str,
) -> None:
    errors.append(
        {
            "path": str(path),
            "error_type": error_type,
            "detail": detail,
        }
    )


def _refresh_client_intelligence_summaries(week: str) -> None:
    """
    The GitHub workflow runs validate_content_quality before the standalone
    write_client_intelligence_summary step.

    That means validation can otherwise inspect stale or pre-writer client
    intelligence files. Refreshing here keeps the pipeline order safe without
    requiring a YAML change.
    """

    try:
        from src.write_client_intelligence_summary import write_client_intelligence_summary

        write_client_intelligence_summary(week=week)
    except Exception as exc:
        print(f"Warning: could not refresh client intelligence summaries before QA: {exc}")


def _validate_required_content_files(
    client_dir: Path,
    errors: List[Dict[str, str]],
) -> int:
    checked = 0

    for filename in REQUIRED_CONTENT_FILES:
        path = client_dir / filename
        checked += 1

        if not path.exists():
            _add_error(
                errors,
                path,
                "missing_required_file",
                f"Required content file missing: {filename}",
            )
            continue

        text = _safe_read_text(path).strip()

        if not text:
            _add_error(
                errors,
                path,
                "empty_required_file",
                f"Required content file is empty: {filename}",
            )

    return checked


def _validate_operational_memory(
    client_dir: Path,
    errors: List[Dict[str, str]],
) -> int:
    path = client_dir / "operational_memory.json"
    checked = 1

    if not path.exists():
        _add_error(
            errors,
            path,
            "missing_operational_memory",
            "operational_memory.json missing",
        )
        return checked

    memory = _safe_read_json(path)

    if not memory:
        _add_error(
            errors,
            path,
            "invalid_operational_memory_json",
            "operational_memory.json is missing, empty, or invalid JSON",
        )
        return checked

    categories = memory.get("categories")

    if not isinstance(categories, dict):
        _add_error(
            errors,
            path,
            "missing_operational_memory_categories",
            "operational_memory.json missing categories object",
        )
        return checked

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category)

        if not isinstance(entry, dict):
            _add_error(
                errors,
                path,
                "missing_operational_memory_category",
                f"operational_memory.json missing category: {category}",
            )
            continue

        for field in [
            "status",
            "previous_status",
            "trend_delta",
            "weeks_observed",
            "summary",
            "evidence",
            "severity",
            "severity_history",
            "momentum",
        ]:
            if field not in entry:
                _add_error(
                    errors,
                    path,
                    "missing_operational_memory_field",
                    f"{category} missing field: {field}",
                )

    return checked


def _validate_trend_dashboard(
    client_dir: Path,
    errors: List[Dict[str, str]],
) -> int:
    path = client_dir / "trend_dashboard.json"
    checked = 1

    if not path.exists():
        _add_error(
            errors,
            path,
            "missing_trend_dashboard",
            "trend_dashboard.json missing",
        )
        return checked

    dashboard = _safe_read_json(path)

    if not dashboard:
        _add_error(
            errors,
            path,
            "invalid_trend_dashboard_json",
            "trend_dashboard.json is missing, empty, or invalid JSON",
        )

    return checked


def _validate_client_intelligence_summary(
    client_dir: Path,
    errors: List[Dict[str, str]],
) -> int:
    path = client_dir / "client_intelligence_summary.md"
    checked = 1

    if not path.exists():
        _add_error(
            errors,
            path,
            "missing_client_intelligence_summary",
            "client_intelligence_summary.md missing",
        )
        return checked

    text = _safe_read_text(path)

    if not text.strip():
        _add_error(
            errors,
            path,
            "empty_client_intelligence_summary",
            "client_intelligence_summary.md is empty",
        )
        return checked

    for heading in REQUIRED_CLIENT_INTELLIGENCE_HEADINGS:
        if heading not in text:
            _add_error(
                errors,
                path,
                "missing_client_intelligence_summary_heading",
                f"{heading} | client_intelligence_summary.md missing heading: {heading}",
            )

    return checked


def validate_content_quality(week: Optional[str] = None) -> Dict[str, Any]:
    week_key = week or _current_week()
    week_dir = _output_root() / week_key

    errors: List[Dict[str, str]] = []

    if not week_dir.exists():
        _add_error(
            errors,
            week_dir,
            "missing_week_output_dir",
            f"Week output folder missing: {week_dir}",
        )

        return {
            "status": "failed",
            "week": week_key,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "client_folders_checked": 0,
            "files_checked_per_client": len(REQUIRED_CONTENT_FILES),
            "operational_memory_checked_per_client": 1,
            "client_intelligence_summary_checked_per_client": 1,
            "trend_dashboard_checked_per_client": 1,
            "errors": errors,
        }

    _refresh_client_intelligence_summaries(week_key)

    client_dirs = _client_dirs(week_dir)

    if not client_dirs:
        _add_error(
            errors,
            week_dir,
            "no_client_output_dirs",
            "No client output folders found",
        )

    total_content_file_checks = 0
    total_memory_checks = 0
    total_client_intel_checks = 0
    total_trend_dashboard_checks = 0

    for client_dir in client_dirs:
        total_content_file_checks += _validate_required_content_files(client_dir, errors)
        total_memory_checks += _validate_operational_memory(client_dir, errors)
        total_client_intel_checks += _validate_client_intelligence_summary(client_dir, errors)
        total_trend_dashboard_checks += _validate_trend_dashboard(client_dir, errors)

    status = "passed" if not errors else "failed"

    return {
        "status": status,
        "week": week_key,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "client_folders_checked": len(client_dirs),
        "files_checked_per_client": len(REQUIRED_CONTENT_FILES),
        "operational_memory_checked_per_client": 1,
        "client_intelligence_summary_checked_per_client": 1,
        "trend_dashboard_checked_per_client": 1,
        "total_content_file_checks": total_content_file_checks,
        "total_operational_memory_checks": total_memory_checks,
        "total_client_intelligence_summary_checks": total_client_intel_checks,
        "total_trend_dashboard_checks": total_trend_dashboard_checks,
        "errors": errors,
    }


def write_content_quality_report(week: Optional[str] = None) -> Path:
    report = validate_content_quality(week=week)
    week_key = report["week"]
    week_dir = _output_root() / week_key
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / "content_quality_report.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    status = report.get("status", "failed")
    errors = report.get("errors", [])

    if status == "passed":
        print("CONTENT QUALITY CHECK PASSED")
    else:
        print("CONTENT QUALITY CHECK FAILED")

    print(f"Week: {week_key}")
    print(f"Client folders checked: {report.get('client_folders_checked', 0)}")
    print(f"Files checked per client: {report.get('files_checked_per_client', len(REQUIRED_CONTENT_FILES))}")
    print(f"Operational memory checked per client: {report.get('operational_memory_checked_per_client', 1)}")
    print(f"Client intelligence summary checked per client: {report.get('client_intelligence_summary_checked_per_client', 1)}")
    print(f"Trend dashboard checked per client: {report.get('trend_dashboard_checked_per_client', 1)}")

    if errors:
        print(f"Errors found: {len(errors)}")

    print(f"Report written: {output_path}")

    for error in errors:
        print(
            f"- {error.get('path')}: "
            f"{error.get('error_type')} | "
            f"{error.get('detail')}"
        )

    return output_path


def main() -> None:
    week = os.getenv("WEEK_KEY") or os.getenv("WEEK") or os.getenv("WHOA_WEEK")
    report_path = write_content_quality_report(week=week)
    report = _safe_read_json(report_path)

    if report.get("status") != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
