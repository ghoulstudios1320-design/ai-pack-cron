import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


CATEGORY_LABELS = {
    "appointment_pressure": "Appointment Pressure",
    "detention": "Detention",
    "freight_volume": "Freight Volume",
    "weather_disruption": "Weather Disruption",
    "equipment_issues": "Equipment Issues",
    "customer_pressure": "Customer Pressure",
    "lane_activity": "Lane Activity",
}


FOCUS_RECOMMENDATIONS = {
    "appointment_pressure": [
        "appointment-window communication",
        "earlier driver-dispatch updates",
        "delivery timing expectations",
    ],
    "detention": [
        "detention documentation habits",
        "dock-delay escalation",
        "driver time protection",
    ],
    "freight_volume": [
        "lane-specific freight visibility",
        "load-flow monitoring",
        "market demand messaging",
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
        "lane-specific recruiting hooks",
        "route planning strategy",
        "regional operations visibility",
    ],
}


TEXT_SIGNAL_KEYWORDS = {
    "dispatch": ["dispatch", "communication", "appointment"],
    "weather": ["weather", "winter", "ice", "snow", "rain", "fog", "wind", "storm"],
    "safety": ["safety", "backing", "fatigue", "hours of service", "hos", "spotter"],
    "detention": ["detention", "waiting", "wait time", "dock delay", "loading delay", "unloading delay"],
    "equipment": ["equipment", "maintenance", "pre-trip", "post-trip", "tractor", "trailer", "tires", "brakes"],
    "congestion": ["congestion", "traffic", "metro", "rush hour", "urban"],
    "parking": ["parking", "staging", "overnight", "truck stop", "rest area"],
}


CONTENT_FILES = [
    "recruiting_posts.md",
    "social_posts.md",
    "safety_reminders.md",
    "company_update.md",
    "freight_digest.md",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_week_key() -> str:
    override = os.getenv("WEEK_KEY", "").strip()
    if override:
        return override

    today = datetime.now(timezone.utc).date()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def find_week_dir() -> Path:
    week_key = get_week_key()
    week_dir = OUTPUT_DIR / week_key

    if week_dir.exists():
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


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read JSON {path}: {exc}")
        return None


def load_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace").strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def get_manifest_clients(week_dir: Path) -> List[Dict[str, Any]]:
    manifest = load_json(week_dir / "distribution_manifest.json")
    if not manifest:
        raise RuntimeError(f"Missing distribution_manifest.json in {week_dir}")

    return manifest.get("clients", [])


def get_client_meta(week_dir: Path, client_folder: str) -> Dict[str, Any]:
    return load_json(week_dir / client_folder / "meta.json") or {}


def normalize_category_name(raw_name: str) -> str:
    value = str(raw_name).strip()
    snake = value.lower().replace(" ", "_").replace("-", "_")
    snake = "".join(ch for ch in snake if ch.isalnum() or ch == "_")
    return snake


def human_category_name(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def extract_category_records_from_mapping(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}

    for raw_category, raw_record in data.items():
        category = normalize_category_name(raw_category)

        if category in {
            "client_id",
            "company_name",
            "week",
            "generated_at",
            "updated_at",
            "memory_version",
            "version",
            "summary",
            "executive_readout",
        }:
            continue

        if isinstance(raw_record, dict):
            records[category] = raw_record

    return records


def extract_category_records(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not data:
        return {}

    candidates = [
        data.get("categories"),
        data.get("signals"),
        data.get("memory"),
        data.get("operational_memory"),
        data.get("trend_categories"),
        data.get("category_snapshot"),
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            records = extract_category_records_from_mapping(candidate)
            if records:
                return records

    if isinstance(data.get("items"), list):
        records: Dict[str, Dict[str, Any]] = {}
        for item in data["items"]:
            if not isinstance(item, dict):
                continue

            raw_category = item.get("category") or item.get("name") or item.get("signal") or item.get("type")

            if not raw_category:
                continue

            records[normalize_category_name(str(raw_category))] = item

        if records:
            return records

    return extract_category_records_from_mapping(data)


def merge_category_records(
    operational_records: Dict[str, Dict[str, Any]],
    trend_records: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for category in sorted(set(operational_records) | set(trend_records)):
        merged_record: Dict[str, Any] = {}

        if category in operational_records:
            merged_record.update(operational_records[category])

        if category in trend_records:
            merged_record.update({k: v for k, v in trend_records[category].items() if v not in [None, ""]})

        merged[category] = merged_record

    return merged


def get_record_status(record: Dict[str, Any]) -> str:
    return safe_str(
        record.get("status")
        or record.get("current_status")
        or record.get("state")
        or record.get("level")
        or "watch"
    )


def get_record_previous_status(record: Dict[str, Any]) -> str:
    return safe_str(
        record.get("previous_status")
        or record.get("prior_status")
        or record.get("last_status")
        or ""
    )


def get_record_delta(record: Dict[str, Any]) -> str:
    return safe_str(record.get("trend_delta") or record.get("delta") or record.get("trend") or "persistent")


def get_record_weeks_observed(record: Dict[str, Any]) -> int:
    return safe_int(
        record.get("weeks_observed")
        or record.get("observed_weeks")
        or record.get("weeks_seen")
        or record.get("week_count")
        or record.get("count")
        or 0
    )


def get_record_severity(record: Dict[str, Any]) -> int:
    return safe_int(
        record.get("severity")
        or record.get("severity_score")
        or record.get("risk_score")
        or record.get("score")
        or 0
    )


def get_record_summary(category: str, record: Dict[str, Any]) -> str:
    summary = safe_str(record.get("summary") or record.get("description") or record.get("note"))
    if summary:
        return summary

    label = human_category_name(category)
    return f"{label} appeared in recent fleet communication and operational memory."


def severity_label(value: int) -> str:
    if value >= 4:
        return "High"
    if value == 3:
        return "Moderate"
    if value in {1, 2}:
        return "Low"
    return "Unscored"


def category_sort_key(item: Tuple[str, Dict[str, Any]]) -> Tuple[int, int, str]:
    category, record = item
    return (get_record_weeks_observed(record), get_record_severity(record), category)


def classify_categories(records: Dict[str, Dict[str, Any]]) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    groups = {
        "worsening": [],
        "new": [],
        "persistent": [],
        "improving": [],
        "resolved": [],
        "other": [],
    }

    for category, record in records.items():
        delta = get_record_delta(record).lower()
        status = get_record_status(record).lower()

        if "worsen" in delta or "increasing" in delta or status == "increasing":
            groups["worsening"].append((category, record))
        elif "new" in delta:
            groups["new"].append((category, record))
        elif "improv" in delta or "decreasing" in delta:
            groups["improving"].append((category, record))
        elif "resolved" in delta or "resolved" in status:
            groups["resolved"].append((category, record))
        elif "persistent" in delta or get_record_weeks_observed(record) >= 2:
            groups["persistent"].append((category, record))
        else:
            groups["other"].append((category, record))

    for key in groups:
        groups[key] = sorted(groups[key], key=category_sort_key, reverse=True)

    return groups


def extract_current_week_signals(week_dir: Path, client_folder: str) -> Counter[str]:
    combined = ""

    for filename in CONTENT_FILES:
        combined += "\n" + load_text(week_dir / client_folder / filename).lower()

    counter: Counter[str] = Counter()

    for signal, keywords in TEXT_SIGNAL_KEYWORDS.items():
        for keyword in keywords:
            counter[signal] += combined.count(keyword)

    return counter


def recommended_focus_areas(records: Dict[str, Dict[str, Any]]) -> List[str]:
    recommendations: List[str] = []

    sorted_categories = sorted(records.items(), key=category_sort_key, reverse=True)

    for category, _record in sorted_categories:
        for item in FOCUS_RECOMMENDATIONS.get(category, []):
            if item not in recommendations:
                recommendations.append(item)

    defaults = [
        "driver communication habits",
        "parking and staging planning",
        "detention documentation",
        "safe routing decisions",
        "equipment readiness",
        "customer update discipline",
    ]

    for item in defaults:
        if len(recommendations) >= 8:
            break
        if item not in recommendations:
            recommendations.append(item)

    return recommendations[:8]


def memory_coverage(records: Dict[str, Dict[str, Any]]) -> str:
    if not records:
        return "No operational memory available"

    max_weeks = max(get_record_weeks_observed(record) for record in records.values())
    category_count = len(records)

    if max_weeks:
        return f"{max_weeks} observed weeks across {category_count} operational categories"

    return f"{category_count} operational categories detected"


def build_executive_readout(company_name: str, records: Dict[str, Dict[str, Any]]) -> str:
    if not records:
        return (
            f"{company_name} does not have enough operational memory yet for a strong intelligence read. "
            "Continue generating weekly packs to build a clearer operating profile."
        )

    groups = classify_categories(records)
    persistent = len(groups["persistent"])
    new = len(groups["new"])
    worsening = len(groups["worsening"])
    improving = len(groups["improving"])
    resolved = len(groups["resolved"])

    top_categories = sorted(records.items(), key=category_sort_key, reverse=True)[:3]
    top_labels = [human_category_name(category) for category, _ in top_categories]

    base = (
        f"This week's operational memory shows {persistent} persistent, {new} new, "
        f"{worsening} worsening, {improving} improving, and {resolved} resolved signals."
    )

    if top_labels:
        base += f" The strongest recurring themes are {', '.join(top_labels)}."

    return base


def build_operational_identity(company_name: str, records: Dict[str, Dict[str, Any]]) -> str:
    if not records:
        return (
            f"{company_name}'s operational identity is still forming. "
            "More weekly runs are needed before persistent patterns can be summarized confidently."
        )

    sorted_categories = sorted(records.items(), key=category_sort_key, reverse=True)[:4]
    labels = [human_category_name(category).lower() for category, _record in sorted_categories]

    if len(labels) >= 3:
        return (
            f"{company_name} is developing a stable operating profile centered around "
            f"{labels[0]}, {labels[1]}, and {labels[2]}. These themes should guide future "
            "recruiting, safety, dispatch, and freight communication so the content stays specific "
            "to the fleet instead of becoming generic."
        )

    return (
        f"{company_name}'s strongest current operating theme is {labels[0]}. "
        "Future content should preserve this identity while rotating supporting weekly topics."
    )


def format_category_line(category: str, record: Dict[str, Any]) -> str:
    status = get_record_status(record)
    previous = get_record_previous_status(record)
    delta = get_record_delta(record)
    weeks = get_record_weeks_observed(record)
    severity = get_record_severity(record)
    severity_text = severity_label(severity)

    previous_text = f", previous: `{previous}`" if previous else ""

    return (
        f"- **{human_category_name(category)}**: {delta} "
        f"({severity_text}, current: `{status}`{previous_text}, observed for `{weeks}` weeks). "
        f"{get_record_summary(category, record)}"
    )


def build_group_section(title: str, items: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    lines = [f"### {title}", ""]

    if not items:
        lines.append("- None detected.")
    else:
        for category, record in items:
            lines.append(format_category_line(category, record))

    lines.append("")
    return lines


def build_raw_snapshot(records: Dict[str, Dict[str, Any]]) -> List[str]:
    lines = ["### Raw Category Snapshot", ""]

    if not records:
        lines.append("- No operational memory records available.")
        lines.append("")
        return lines

    for category, record in sorted(records.items(), key=category_sort_key, reverse=True):
        lines.extend(
            [
                f"#### {human_category_name(category)}",
                "",
                f"- Status: `{get_record_status(record)}`",
                f"- Previous Status: `{get_record_previous_status(record) or 'none'}`",
                f"- Trend Delta: `{get_record_delta(record)}`",
                f"- Weeks Observed: `{get_record_weeks_observed(record)}`",
                f"- Severity: `{get_record_severity(record)}/5`",
                f"- Summary: {get_record_summary(category, record)}",
                "",
            ]
        )

    return lines


def build_client_summary(week_dir: Path, client: Dict[str, Any]) -> List[str]:
    client_id = safe_str(client.get("client_id"))
    client_folder = safe_str(client.get("client_folder") or client_id)
    company_name = safe_str(client.get("company_name") or client_id)

    client_dir = week_dir / client_folder
    meta = get_client_meta(week_dir, client_folder)

    operational_memory = load_json(client_dir / "operational_memory.json") or {}
    trend_dashboard = load_json(client_dir / "trend_dashboard.json") or {}

    operational_records = extract_category_records(operational_memory)
    trend_records = extract_category_records(trend_dashboard)
    records = merge_category_records(operational_records, trend_records)

    groups = classify_categories(records)
    signals = extract_current_week_signals(week_dir, client_folder)
    focus_areas = recommended_focus_areas(records)

    fleet_size = meta.get("fleet_size", "")
    region = meta.get("region", "")
    equipment = meta.get("equipment", "")
    hiring_for = meta.get("hiring_for", "")
    tagline = meta.get("tagline", "")

    lines: List[str] = [
        f"## {company_name}",
        "",
    ]

    if tagline:
        lines.extend([f"*{tagline}*", ""])

    lines.extend(
        [
            "### Fleet Profile",
            "",
            f"- Fleet Size: `{fleet_size}`",
            f"- Region: `{region}`",
            f"- Equipment: `{equipment}`",
            f"- Hiring Focus: `{hiring_for}`",
            f"- Memory Coverage: `{memory_coverage(records)}`",
            "",
            "### Executive Readout",
            "",
            build_executive_readout(company_name, records),
            "",
            "### Operational Identity",
            "",
            build_operational_identity(company_name, records),
            "",
            "## Trend Breakdown",
            "",
        ]
    )

    lines.extend(build_group_section("Worsening", groups["worsening"]))
    lines.extend(build_group_section("New", groups["new"]))
    lines.extend(build_group_section("Persistent", groups["persistent"]))
    lines.extend(build_group_section("Improving", groups["improving"]))
    lines.extend(build_group_section("Resolved", groups["resolved"]))

    if groups["other"]:
        lines.extend(build_group_section("Other Watch Items", groups["other"]))

    lines.extend(["### Current-Week Content Signals", ""])

    emitted_signal = False
    for signal, count in signals.most_common(8):
        if count <= 0:
            continue
        emitted_signal = True
        lines.append(f"- {signal}: `{count}` mentions")

    if not emitted_signal:
        lines.append("- No strong current-week content signals detected.")

    lines.extend(["", "### Recommended Future Content Focus", ""])

    for item in focus_areas:
        lines.append(f"- {item}")

    lines.extend([""])
    lines.extend(build_raw_snapshot(records))
    lines.extend(["---", ""])

    return lines


def build_summary(week_dir: Path) -> str:
    clients = get_manifest_clients(week_dir)
    week = week_dir.name

    lines: List[str] = [
        f"# Client Intelligence Summary - {week}",
        "",
        f"Written At: `{now_iso()}`",
        f"Client Count: `{len(clients)}`",
        "Memory Source: `operational_memory.json + trend_dashboard.json`",
        "",
        "This report summarizes operational memory, recurring fleet signals, current-week content signals, and recommended future content focus areas.",
        "",
        "---",
        "",
    ]

    for client in clients:
        lines.extend(build_client_summary(week_dir, client))

    return "\n".join(lines)


def main() -> None:
    week_dir = find_week_dir()
    summary = build_summary(week_dir)

    path = week_dir / "client_intelligence_summary.md"
    path.write_text(summary + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {path}")


if __name__ == "__main__":
    main()
