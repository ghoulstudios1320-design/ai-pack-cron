import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


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


CLIENT_IDENTITY = {
    "cascade_cold_chain": {
        "name": "Cascade Cold Chain",
        "tagline": "Reliable refrigerated freight across the Pacific Northwest",
        "fleet_size": "28 trucks",
        "region": "Pacific Northwest",
        "equipment": "refrigerated van",
        "hiring_focus": "CDL-A reefer drivers",
        "identity_summary": (
            "Cascade Cold Chain's profile should emphasize temperature-sensitive freight, "
            "reefer readiness, dock timing, weather exposure, and customer confidence "
            "around cold-chain reliability."
        ),
        "focus_areas": [
            "reefer inspection discipline",
            "temperature-sensitive dock communication",
            "weather-aware routing for refrigerated freight",
            "customer update discipline during appointment pressure",
        ],
    },
    "inland_flatbed_logistics": {
        "name": "Inland Flatbed Logistics",
        "tagline": "Flatbed freight built for the Inland Northwest.",
        "fleet_size": "36 trucks",
        "region": "Inland Northwest",
        "equipment": "flatbed",
        "hiring_focus": "CDL-A regional flatbed drivers",
        "identity_summary": (
            "Inland Flatbed Logistics' profile should emphasize flatbed readiness, "
            "weather exposure, securement-minded operations, regional staging, and "
            "practical planning around shipper and receiver timing."
        ),
        "focus_areas": [
            "flatbed inspection and securement discipline",
            "weather-aware load planning",
            "staging options near regional shippers",
            "driver-dispatch updates around appointment changes",
        ],
    },
    "iron_mile_freight": {
        "name": "Iron Mile Freight",
        "tagline": "Steady Midwest freight. Straight answers. Real dispatch.",
        "fleet_size": "42 trucks",
        "region": "Midwest",
        "equipment": "dry van",
        "hiring_focus": "CDL-A regional dry van drivers",
        "identity_summary": (
            "Iron Mile Freight's profile should emphasize Midwest dry van execution, "
            "metro congestion, appointment discipline, detention management, and clear "
            "dispatch communication."
        ),
        "focus_areas": [
            "metro timing and congestion planning",
            "appointment discipline on dry van lanes",
            "detention documentation habits",
            "dispatch updates around warehouse delays",
        ],
    },
}


CATEGORY_FOCUS_AREAS = {
    "appointment_pressure": [
        "appointment-window communication",
        "earlier driver-dispatch updates",
        "delivery-window planning",
    ],
    "detention": [
        "detention documentation habits",
        "dock wait communication",
        "protecting downstream appointment chains",
    ],
    "freight_volume": [
        "freight-flow trend monitoring",
        "steady demand messaging",
        "lane-specific load planning",
    ],
    "weather_disruption": [
        "weather-aware routing",
        "safe staging during weather delays",
        "driver fatigue during adverse conditions",
    ],
    "equipment_issues": [
        "pre-trip inspection discipline",
        "preventive maintenance reporting",
        "equipment readiness messaging",
    ],
    "customer_pressure": [
        "proactive customer updates",
        "realistic ETA communication",
        "service reliability messaging",
    ],
    "lane_activity": [
        "lane-specific recruiting content",
        "regional route planning",
        "market-lane communication",
    ],
}


def _repo_root() -> Path:
    return Path.cwd()


def _output_root() -> Path:
    return _repo_root() / "output"


def _current_week() -> str:
    env_week = os.getenv("WEEK_KEY") or os.getenv("WEEK") or os.getenv("WHOА_WEEK")
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


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_title(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()

    return fallback


def _display_client_id(client_dir: Path) -> str:
    return client_dir.name


def _load_client_meta(client_dir: Path) -> Dict[str, Any]:
    meta = _safe_read_json(client_dir / "meta.json")

    if not meta:
        return {}

    return meta


def _client_profile(client_id: str, client_dir: Path) -> Dict[str, str]:
    identity = CLIENT_IDENTITY.get(client_id, {})
    meta = _load_client_meta(client_dir)

    company_name = (
        meta.get("company_name")
        or meta.get("client_name")
        or meta.get("name")
        or identity.get("name")
        or client_id.replace("_", " ").title()
    )

    tagline = (
        meta.get("tagline")
        or meta.get("description")
        or identity.get("tagline")
        or ""
    )

    return {
        "client_id": client_id,
        "name": str(company_name),
        "tagline": str(tagline),
        "fleet_size": str(meta.get("fleet_size") or identity.get("fleet_size") or "unknown"),
        "region": str(meta.get("region") or identity.get("region") or "unknown"),
        "equipment": str(meta.get("equipment") or meta.get("equipment_type") or identity.get("equipment") or "unknown"),
        "hiring_focus": str(meta.get("hiring_focus") or identity.get("hiring_focus") or "unknown"),
        "identity_summary": str(identity.get("identity_summary") or ""),
    }


def _memory_categories(memory: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    categories = memory.get("categories", {})

    if not isinstance(categories, dict):
        return {}

    cleaned: Dict[str, Dict[str, Any]] = {}

    for category in MEMORY_CATEGORIES:
        value = categories.get(category, {})

        if isinstance(value, dict):
            cleaned[category] = value
        else:
            cleaned[category] = {}

    return cleaned


def _severity_value(entry: Dict[str, Any]) -> int:
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


def _trend_delta(entry: Dict[str, Any]) -> str:
    value = str(entry.get("trend_delta", "insufficient_history")).strip().lower()

    if value in {"worsening", "new", "persistent", "improving", "resolved"}:
        return value

    if value in {"stable", "changed"}:
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


def _summary(entry: Dict[str, Any]) -> str:
    value = entry.get("summary")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return "No clear operational pattern detected."


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def _bucket_categories(categories: Dict[str, Dict[str, Any]]) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    """
    Groups categories by their exact trend_delta.

    This fixes the prior dashboard bug where persistent items could be displayed
    under the Worsening heading because grouping logic mixed risk rank with
    trend bucket labels.
    """

    buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {
        key: [] for key, _label in TREND_BUCKETS
    }

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        delta = _trend_delta(entry)

        if delta in buckets:
            buckets[delta].append((category, entry))

    for bucket_items in buckets.values():
        bucket_items.sort(
            key=lambda item: (
                -_severity_value(item[1]),
                -_weeks_observed(item[1]),
                _category_label(item[0]),
            )
        )

    return buckets


def _trend_counts(buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]]) -> Dict[str, int]:
    return {key: len(buckets.get(key, [])) for key, _label in TREND_BUCKETS}


def _strongest_themes(categories: Dict[str, Dict[str, Any]], limit: int = 3) -> List[str]:
    ranked = []

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        severity = _severity_value(entry)
        weeks = _weeks_observed(entry)
        status = _status(entry)

        if status == "unknown" and severity <= 1:
            continue

        ranked.append((severity, weeks, _category_label(category)))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))

    return [label for _severity, _weeks, label in ranked[:limit]]


def _memory_coverage(categories: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
    observed_weeks = 0
    observed_categories = 0

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        weeks = _weeks_observed(entry)

        if weeks > 0:
            observed_categories += 1
            observed_weeks = max(observed_weeks, weeks)

    return observed_weeks, observed_categories


def _risk_groups(categories: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    groups = {
        "High": [],
        "Moderate": [],
        "Low": [],
        "Minimal": [],
    }

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        severity = _severity_value(entry)

        if _status(entry) == "unknown" and severity <= 1:
            risk = "Minimal"
        else:
            risk = _risk_label(severity)

        groups[risk].append(_category_label(category))

    for labels in groups.values():
        labels.sort()

    return groups


def _iter_numbers_from_mapping(value: Any) -> Iterable[Tuple[str, int]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(nested, int):
                yield str(key), nested
            elif isinstance(nested, float):
                yield str(key), int(nested)
            elif isinstance(nested, dict):
                for nested_key, nested_value in _iter_numbers_from_mapping(nested):
                    yield nested_key, nested_value


def _extract_signal_counts(trend_dashboard: Dict[str, Any]) -> List[Tuple[str, int]]:
    """
    Supports several possible trend_dashboard shapes without making the writer
    brittle. Preferred keys are checked first, then it falls back to numeric
    mappings if needed.
    """

    preferred_keys = [
        "current_week_content_signals",
        "current_week_signals",
        "signal_counts",
        "signals",
        "keyword_counts",
    ]

    for key in preferred_keys:
        value = trend_dashboard.get(key)

        if isinstance(value, dict):
            counts = [
                (str(label), int(count))
                for label, count in value.items()
                if isinstance(count, (int, float)) and int(count) > 0
            ]

            if counts:
                counts.sort(key=lambda item: (-item[1], item[0]))
                return counts

    fallback_counts = [
        (label, count)
        for label, count in _iter_numbers_from_mapping(trend_dashboard)
        if count > 0 and len(label) <= 40
    ]

    deduped: Dict[str, int] = {}

    for label, count in fallback_counts:
        normalized = label.strip().lower()

        if not normalized:
            continue

        deduped[normalized] = max(deduped.get(normalized, 0), count)

    counts = sorted(deduped.items(), key=lambda item: (-item[1], item[0]))

    return counts[:8]


def _recommended_focus(
    client_id: str,
    categories: Dict[str, Dict[str, Any]],
    limit: int = 8,
) -> List[str]:
    focus: List[str] = []

    identity_focus = CLIENT_IDENTITY.get(client_id, {}).get("focus_areas", [])

    for item in identity_focus:
        if item not in focus:
            focus.append(item)

    ranked_categories = []

    for category in MEMORY_CATEGORIES:
        entry = categories.get(category, {})
        delta = _trend_delta(entry)
        severity = _severity_value(entry)

        priority = 0

        if delta == "worsening":
            priority += 30
        elif delta == "new":
            priority += 25
        elif delta == "persistent":
            priority += 15
        elif delta == "improving":
            priority += 8

        priority += severity * 3
        priority += min(_weeks_observed(entry), 10)

        ranked_categories.append((priority, category))

    ranked_categories.sort(key=lambda item: (-item[0], item[1]))

    for _priority, category in ranked_categories:
        for item in CATEGORY_FOCUS_AREAS.get(category, []):
            if item not in focus:
                focus.append(item)

            if len(focus) >= limit:
                return focus

    return focus[:limit]


def _format_category_line(category: str, entry: Dict[str, Any]) -> str:
    label = _category_label(category)
    delta = _trend_delta(entry)
    risk = _risk_label(_severity_value(entry))
    current = _status(entry)
    previous = _previous_status(entry)
    weeks = _weeks_observed(entry)
    summary = _summary(entry)

    if weeks > 0:
        observed_text = f"observed for `{weeks}` weeks"
    else:
        observed_text = "not currently observed"

    return (
        f"- **{label}**: {delta} ({risk}, current: `{current}`, "
        f"previous: `{previous}`, {observed_text}). {summary}"
    )


def _write_trend_breakdown(lines: List[str], buckets: Dict[str, List[Tuple[str, Dict[str, Any]]]]) -> None:
    lines.append("## Trend Breakdown")
    lines.append("")

    for bucket_key, bucket_label in TREND_BUCKETS:
        lines.append(f"### {bucket_label}")
        lines.append("")

        items = buckets.get(bucket_key, [])

        if not items:
            lines.append("- None detected.")
        else:
            for category, entry in items:
                lines.append(_format_category_line(category, entry))

        lines.append("")


def _write_raw_snapshot(lines: List[str], categories: Dict[str, Dict[str, Any]]) -> None:
    lines.append("### Raw Category Snapshot")
    lines.append("")

    sorted_categories = sorted(
        MEMORY_CATEGORIES,
        key=lambda category: (
            -_severity_value(categories.get(category, {})),
            -_weeks_observed(categories.get(category, {})),
            _category_label(category),
        ),
    )

    for category in sorted_categories:
        entry = categories.get(category, {})
        lines.append(f"#### {_category_label(category)}")
        lines.append("")
        lines.append(f"- Status: `{_status(entry)}`")
        lines.append(f"- Previous Status: `{_previous_status(entry)}`")
        lines.append(f"- Trend Delta: `{_trend_delta(entry)}`")
        lines.append(f"- Weeks Observed: `{_weeks_observed(entry)}`")
        lines.append(f"- Severity: `{_severity_value(entry)}/5`")

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


def _client_summary_lines(
    client_id: str,
    client_dir: Path,
    memory: Dict[str, Any],
    trend_dashboard: Dict[str, Any],
    combined: bool = False,
) -> List[str]:
    profile = _client_profile(client_id, client_dir)
    categories = _memory_categories(memory)
    buckets = _bucket_categories(categories)
    counts = _trend_counts(buckets)
    strongest = _strongest_themes(categories)
    observed_weeks, observed_categories = _memory_coverage(categories)
    risk_groups = _risk_groups(categories)
    signal_counts = _extract_signal_counts(trend_dashboard)
    focus = _recommended_focus(client_id, categories)

    lines: List[str] = []

    if combined:
        lines.append(f"## {profile['name']}")
        lines.append("")

        if profile["tagline"]:
            lines.append(f"*{profile['tagline']}*")
            lines.append("")

        lines.append("### Fleet Profile")
        lines.append("")
        lines.append(f"- Fleet Size: `{profile['fleet_size']}`")
        lines.append(f"- Region: `{profile['region']}`")
        lines.append(f"- Equipment: `{profile['equipment']}`")
        lines.append(f"- Hiring Focus: `{profile['hiring_focus']}`")
        lines.append(
            f"- Memory Coverage: `{observed_weeks} observed weeks across {observed_categories} operational categories`"
        )
        lines.append("")
        lines.append("### Executive Readout")
        lines.append("")
    else:
        lines.append(f"# Weekly Client Intelligence Summary - {profile['name']}")
        lines.append("")
        lines.append(f"**Client ID:** `{client_id}`")
        lines.append(f"**Week:** `{memory.get('week', '')}`")
        lines.append(f"**Memory Version:** `{memory.get('memory_version', 'unknown')}`")
        lines.append("")
        lines.append("## Executive Readout")
        lines.append("")

    strongest_text = ", ".join(strongest) if strongest else "None detected"
    identity_summary = profile["identity_summary"]

    if identity_summary:
        identity_sentence = f" {identity_summary}"
    else:
        identity_sentence = ""

    lines.append(
        "This week's operational memory shows "
        f"**{counts['persistent']} persistent**, "
        f"**{counts['new']} new**, "
        f"**{counts['worsening']} worsening**, "
        f"**{counts['improving']} improving**, and "
        f"**{counts['resolved']} resolved** signals. "
        f"The strongest carrier-specific themes are **{strongest_text}**."
        f"{identity_sentence}"
    )
    lines.append("")

    if combined:
        lines.append("### Operational Identity")
        lines.append("")
        if identity_summary:
            operating_profile = ", ".join(label.lower() for label in strongest[:3]) or "emerging operational signals"
            lines.append(
                f"{profile['name']} is developing a stable operating profile centered around "
                f"{operating_profile}. {identity_summary} Future recruiting, safety, dispatch, "
                "and freight communication should preserve this carrier-specific identity while "
                "rotating weekly focus areas to avoid repetitive content."
            )
        else:
            lines.append(
                f"{profile['name']} is developing an operating profile from recurring weekly memory signals."
            )
        lines.append("")

        lines.append("### Operational Risk Summary")
        lines.append("")
        for risk in ["High", "Moderate", "Low", "Minimal"]:
            labels = risk_groups.get(risk, [])
            if labels:
                lines.append(f"- **{risk}:** {', '.join(labels)}")
        lines.append("")

    _write_trend_breakdown(lines, buckets)

    if combined:
        lines.append("### Current-Week Content Signals")
        lines.append("")

        if signal_counts:
            for label, count in signal_counts[:8]:
                lines.append(f"- {label}: `{count}` mentions")
        else:
            lines.append("- None detected.")

        lines.append("")

    lines.append("### Recommended Future Content Focus" if combined else "## Recommended Focus")
    lines.append("")

    if focus:
        for item in focus:
            lines.append(f"- {item}")
    else:
        lines.append("- No specific focus areas detected yet.")

    lines.append("")

    _write_raw_snapshot(lines, categories)

    return lines


def _is_client_output_dir(path: Path) -> bool:
    if not path.is_dir():
        return False

    if path.name.startswith("_"):
        return False

    return (path / "operational_memory.json").exists()


def _client_dirs(week_dir: Path) -> List[Path]:
    return sorted(
        [path for path in week_dir.iterdir() if _is_client_output_dir(path)],
        key=lambda path: path.name,
    )


def _write_individual_client_summary(client_dir: Path) -> Optional[Path]:
    client_id = _display_client_id(client_dir)
    memory = _safe_read_json(client_dir / "operational_memory.json")

    if not memory:
        return None

    trend_dashboard = _safe_read_json(client_dir / "trend_dashboard.json")

    lines = _client_summary_lines(
        client_id=client_id,
        client_dir=client_dir,
        memory=memory,
        trend_dashboard=trend_dashboard,
        combined=False,
    )

    output_path = client_dir / "client_intelligence_summary.md"
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    return output_path


def write_client_intelligence_summary(week: Optional[str] = None) -> Path:
    week_key = week or _current_week()
    week_dir = _output_root() / week_key

    if not week_dir.exists():
        raise FileNotFoundError(f"Week output folder not found: {week_dir}")

    client_dirs = _client_dirs(week_dir)

    written_client_summaries: List[Path] = []

    for client_dir in client_dirs:
        output_path = _write_individual_client_summary(client_dir)

        if output_path:
            written_client_summaries.append(output_path)

    lines: List[str] = [
        f"# Client Intelligence Summary - {week_key}",
        "",
        f"Written At: `{datetime.now(timezone.utc).isoformat()}`",
        f"Client Count: `{len(client_dirs)}`",
        "Memory Source: `operational_memory.json + trend_dashboard.json`",
        "",
        "This report summarizes operational memory, recurring fleet signals, current-week content signals, recommended future content focus areas, and carrier-specific operational identity.",
        "",
        "---",
        "",
    ]

    for index, client_dir in enumerate(client_dirs):
        client_id = _display_client_id(client_dir)
        memory = _safe_read_json(client_dir / "operational_memory.json")
        trend_dashboard = _safe_read_json(client_dir / "trend_dashboard.json")

        if not memory:
            continue

        lines.extend(
            _client_summary_lines(
                client_id=client_id,
                client_dir=client_dir,
                memory=memory,
                trend_dashboard=trend_dashboard,
                combined=True,
            )
        )

        if index != len(client_dirs) - 1:
            lines.append("---")
            lines.append("")

    output_path = week_dir / "client_intelligence_summary.md"
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {output_path}")

    return output_path


def main() -> None:
    write_client_intelligence_summary()


if __name__ == "__main__":
    main()
