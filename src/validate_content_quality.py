import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VALIDATOR_VERSION = "client-intel-self-heal-1.0"


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


CATEGORY_LABELS = {
    "appointment_pressure": "Appointment Pressure",
    "detention": "Detention",
    "freight_volume": "Freight Volume",
    "weather_disruption": "Weather Disruption",
    "equipment_issues": "Equipment Issues",
    "customer_pressure": "Customer Pressure",
    "lane_activity": "Lane Activity",
}


TREND_BUCKETS = [
    ("worsening", "Worsening"),
    ("new", "New"),
    ("persistent", "Persistent"),
    ("improving", "Improving"),
    ("resolved", "Resolved"),
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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def _normalize_trend_delta(entry: Dict[str, Any]) -> str:
    raw = str(entry.get("trend_delta", "insufficient_history")).strip().lower()

    if raw in {"worsening", "new", "persistent", "improving", "resolved"}:
        return raw

    if raw in {"stable", "changed"}:
        return "persistent"

    return "insufficient_history"


def _status(entry: Dict[str, Any]) -> str:
    return str(entry.get("status", "unknown"))


def _previous_status(entry: Dict[str, Any]) -> str:
    return str(entry.get("previous_status", "unknown"))


def _weeks_observed(entry: Dict[str, Any]) -> int:
    try:
        return int(entry.get("weeks_observed", 0))
    except Exception:
        return 0


def _severity(entry: Dict[str, Any]) -> int:
    try:
        value = int(entry.get("severity", 1))
    except Exception:
        value = 1

    return max(1, min(value, 5))


def _risk_label(severity: int) -> str:
    if severity >= 4:
        return "High"

    if severity >= 3:
        return "Moderate"

    if severity >= 2:
        return "Low"

    return "Minimal"


def _summary(entry: Dict[str, Any]) -> str:
    value = entry.get("summary")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return "No clear operational pattern detected."


def _client_name(client_dir: Path) -> str:
    meta = _safe_read_json(client_dir / "meta.json")

    for key in ["company_name", "client_name", "name"]:
        value = meta.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return client_dir.name.replace("_", " ").title()


def _memory_categories(memory: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    categories = memory.get("categories", {})

    if not isinstance(categories, dict):
        return {}

    cleaned: Dict[str, Dict[str, Any]] = {}

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category)

        if isinstance(entry, dict):
            cleaned[category] = entry
        else:
            cleaned[category] = {}

    return cleaned


def _bucket_categories(categories: Dict[str, Dict[str, Any]]) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {
        key: [] for key, _label in TREND_BUCKETS
    }

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        delta = _normalize_trend_delta(entry)

        if delta in buckets:
            buckets[delta].append((category, entry))

    for items in buckets.values():
        items.sort(
            key=lambda item: (
                -_severity(item[1]),
                -_weeks_observed(item[1]),
                _category_label(item[0]),
            )
        )

    return buckets


def _trend_counts(buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]]) -> Dict[str, int]:
    return {key: len(buckets.get(key, [])) for key, _label in TREND_BUCKETS}


def _strongest_themes(categories: Dict[str, Dict[str, Any]], limit: int = 3) -> List[str]:
    ranked: List[Tuple[int, int, str]] = []

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})

        if _status(entry) == "unknown" and _severity(entry) <= 1:
            continue

        ranked.append(
            (
                _severity(entry),
                _weeks_observed(entry),
                _category_label(category),
            )
        )

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))

    return [label for _sev, _weeks, label in ranked[:limit]]


def _category_line(category: str, entry: Dict[str, Any]) -> str:
    delta = _normalize_trend_delta(entry)
    severity = _severity(entry)
    risk = _risk_label(severity)
    current = _status(entry)
    previous = _previous_status(entry)
    weeks = _weeks_observed(entry)
    summary = _summary(entry)

    if weeks > 0:
        observed_text = f"observed for {weeks} weeks"
    else:
        observed_text = "not currently observed"

    return (
        f"- **{_category_label(category)}**: {delta} "
        f"({risk}, current: `{current}`, previous: `{previous}`, {observed_text}). "
        f"{summary}"
    )


def _recommended_focus(categories: Dict[str, Dict[str, Any]]) -> List[str]:
    focus_map = {
        "appointment_pressure": "Keep appointment-window communication tight and push earlier driver-dispatch updates when timing starts slipping.",
        "detention": "Track detention while it is happening, not after the fact, so dispatch can protect the next appointment chain.",
        "freight_volume": "Watch freight-flow language week to week so content reflects whether demand is steady, tightening, or softening.",
        "weather_disruption": "Keep route planning flexible around weather-sensitive lanes and remind drivers to communicate conditions early.",
        "equipment_issues": "Keep pre-trip and pickup-site equipment checks visible in driver communication before minor issues become roadside failures.",
        "customer_pressure": "Protect customer confidence by emphasizing proactive updates, realistic ETAs, and early notice on delays.",
        "lane_activity": "Use active lane patterns to keep recruiting and driver messaging specific instead of generic.",
    }

    ranked: List[Tuple[int, str]] = []

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        delta = _normalize_trend_delta(entry)

        priority = _severity(entry) * 10 + min(_weeks_observed(entry), 10)

        if delta == "worsening":
            priority += 50
        elif delta == "new":
            priority += 35
        elif delta == "persistent":
            priority += 25
        elif delta == "improving":
            priority += 10

        ranked.append((priority, category))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    focus: List[str] = []

    for _priority, category in ranked:
        item = focus_map.get(category)

        if item and item not in focus:
            focus.append(item)

        if len(focus) >= 7:
            break

    return focus


def _write_self_healed_client_intelligence_summary(client_dir: Path) -> None:
    """
    Writes a validator-compliant individual client summary directly from
    operational_memory.json.

    This protects the pipeline even when validate_content_quality runs before
    the standalone write_client_intelligence_summary step.
    """

    memory_path = client_dir / "operational_memory.json"
    memory = _safe_read_json(memory_path)

    if not memory:
        return

    categories = _memory_categories(memory)
    buckets = _bucket_categories(categories)
    counts = _trend_counts(buckets)
    strongest = _strongest_themes(categories)
    focus = _recommended_focus(categories)

    client_name = _client_name(client_dir)
    client_id = client_dir.name
    week = str(memory.get("week", ""))
    memory_version = str(memory.get("memory_version", "unknown"))
    strongest_text = ", ".join(strongest) if strongest else "None detected"

    lines: List[str] = [
        "# Weekly Client Intelligence Summary",
        "",
        f"Client: `{client_name}`",
        f"Client ID: `{client_id}`",
        f"Week: `{week}`",
        f"Memory Version: `{memory_version}`",
        "",
        "## Executive Readout",
        "",
        (
            "This week's operational memory shows "
            f"**{counts['persistent']} persistent**, "
            f"**{counts['new']} new**, "
            f"**{counts['worsening']} worsening**, "
            f"**{counts['improving']} improving**, and "
            f"**{counts['resolved']} resolved** signals. "
            f"The strongest carrier-specific themes are **{strongest_text}**."
        ),
        "",
        "## Trend Breakdown",
        "",
    ]

    for bucket_key, bucket_label in TREND_BUCKETS:
        lines.append(f"### {bucket_label}")
        lines.append("")

        items = buckets.get(bucket_key, [])

        if not items:
            lines.append("- None detected.")
        else:
            for category, entry in items:
                lines.append(_category_line(category, entry))

        lines.append("")

    lines.append("## Recommended Focus")
    lines.append("")

    if focus:
        for item in focus:
            lines.append(f"- {item}")
    else:
        lines.append("- No specific focus areas detected yet.")

    lines.append("")
    lines.append("## Raw Category Snapshot")
    lines.append("")

    sorted_categories = sorted(
        MEMORY_CATEGORIES,
        key=lambda category: (
            -_severity(categories.get(category, {})),
            -_weeks_observed(categories.get(category, {})),
            _category_label(category),
        ),
    )

    for category in sorted_categories:
        entry = categories.get(category, {})
        lines.append(f"### {_category_label(category)}")
        lines.append("")
        lines.append(f"- Status: `{_status(entry)}`")
        lines.append(f"- Previous Status: `{_previous_status(entry)}`")
        lines.append(f"- Trend Delta: `{_normalize_trend_delta(entry)}`")
        lines.append(f"- Weeks Observed: `{_weeks_observed(entry)}`")
        lines.append(f"- Severity: `{_severity(entry)}/5`")

        raw_severity = entry.get("raw_severity")
        if raw_severity is not None:
            lines.append(f"- Raw Severity: `{raw_severity}/5`")

        hit_count = entry.get("evidence_hit_count")
        if hit_count is not None:
            lines.append(f"- Evidence Hit Count: `{hit_count}`")

        momentum = entry.get("momentum")
        if momentum is not None:
            lines.append(f"- Momentum: `{momentum}`")

        lines.append(f"- Summary: {_summary(entry)}")
        lines.append("")

    output_path = client_dir / "client_intelligence_summary.md"
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _self_heal_client_intelligence_summaries(client_dirs: List[Path]) -> None:
    print(f"Content QA validator version: {VALIDATOR_VERSION}")

    for client_dir in client_dirs:
        _write_self_healed_client_intelligence_summary(client_dir)


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
            "validator_version": VALIDATOR_VERSION,
            "week": week_key,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "client_folders_checked": 0,
            "files_checked_per_client": len(REQUIRED_CONTENT_FILES),
            "operational_memory_checked_per_client": 1,
            "client_intelligence_summary_checked_per_client": 1,
            "trend_dashboard_checked_per_client": 1,
            "errors": errors,
        }

    client_dirs = _client_dirs(week_dir)

    if not client_dirs:
        _add_error(
            errors,
            week_dir,
            "no_client_output_dirs",
            "No client output folders found",
        )
    else:
        _self_heal_client_intelligence_summaries(client_dirs)

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
        "validator_version": VALIDATOR_VERSION,
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
    _write_json(output_path, report)

    status = report.get("status", "failed")
    errors = report.get("errors", [])

    if status == "passed":
        print("CONTENT QUALITY CHECK PASSED")
    else:
        print("CONTENT QUALITY CHECK FAILED")

    print(f"Week: {week_key}")
    print(f"Validator version: {report.get('validator_version', VALIDATOR_VERSION)}")
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
