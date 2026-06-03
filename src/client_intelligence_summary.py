import json
from pathlib import Path
from typing import Any, Dict, List


CATEGORY_LABELS = {
    "appointment_pressure": "Appointment Pressure",
    "detention": "Detention",
    "freight_volume": "Freight Volume",
    "weather_disruption": "Weather Disruption",
    "equipment_issues": "Equipment Issues",
    "customer_pressure": "Customer Pressure",
    "lane_activity": "Lane Activity",
}


TREND_ORDER = [
    "worsening",
    "new",
    "persistent",
    "changed",
    "improving",
    "resolved",
    "stable",
    "insufficient_history",
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required JSON file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def get_client_name(meta: Dict[str, Any], memory: Dict[str, Any]) -> str:
    return (
        meta.get("company_name")
        or memory.get("client_id")
        or "Unknown Client"
    )


def severity_label(severity: int) -> str:
    if severity >= 5:
        return "Critical"
    if severity == 4:
        return "High"
    if severity == 3:
        return "Moderate"
    if severity == 2:
        return "Low"
    return "Minimal"


def format_weeks_observed(weeks: int) -> str:
    if weeks <= 0:
        return "not previously observed"
    if weeks == 1:
        return "observed this week"
    return f"observed for {weeks} weeks"


def category_sentence(category: str, entry: Dict[str, Any]) -> str:
    label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())

    status = entry.get("status", "unknown")
    previous_status = entry.get("previous_status", "unknown")
    trend_delta = entry.get("trend_delta", "insufficient_history")
    weeks_observed = entry.get("weeks_observed", 0)
    severity = entry.get("severity", 1)
    summary = entry.get("summary", "No summary available.")

    try:
        weeks_observed = int(weeks_observed)
    except Exception:
        weeks_observed = 0

    try:
        severity = int(severity)
    except Exception:
        severity = 1

    return (
        f"- **{label}**: {trend_delta.replace('_', ' ')} "
        f"({severity_label(severity)}, current: `{status}`, previous: `{previous_status}`, "
        f"{format_weeks_observed(weeks_observed)}). {summary}"
    )


def group_categories_by_trend(categories: Dict[str, Any]) -> Dict[str, List[str]]:
    grouped = {trend: [] for trend in TREND_ORDER}

    for category, entry in categories.items():
        if not isinstance(entry, dict):
            continue

        trend_delta = entry.get("trend_delta", "insufficient_history")

        if trend_delta not in grouped:
            grouped["changed"].append(category)
        else:
            grouped[trend_delta].append(category)

    return grouped


def build_recommended_focus(categories: Dict[str, Any]) -> List[str]:
    recommendations: List[str] = []

    appointment = categories.get("appointment_pressure", {})
    detention = categories.get("detention", {})
    equipment = categories.get("equipment_issues", {})
    weather = categories.get("weather_disruption", {})
    customer = categories.get("customer_pressure", {})
    lane = categories.get("lane_activity", {})
    freight = categories.get("freight_volume", {})

    if appointment.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Keep appointment-window communication tight and push earlier driver-dispatch updates when timing starts slipping."
        )

    if detention.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Track detention while it is happening, not after the fact, so dispatch can protect the next appointment chain."
        )

    if equipment.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Keep pre-trip and pickup-site equipment checks visible in driver communication before minor issues become roadside failures."
        )

    if weather.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Keep route planning flexible around weather-sensitive lanes and remind drivers to communicate conditions early."
        )

    if customer.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Protect customer confidence by emphasizing proactive updates, realistic ETAs, and early notice on delays."
        )

    if lane.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Use active lane patterns to keep recruiting and driver messaging specific instead of generic."
        )

    if freight.get("trend_delta") in {"persistent", "worsening", "new"}:
        recommendations.append(
            "Watch freight-flow language week to week so content reflects whether demand is steady, tightening, or softening."
        )

    if not recommendations:
        recommendations.append(
            "No major operational escalation detected. Continue monitoring weekly memory for changes."
        )

    return recommendations


def build_intelligence_summary(meta: Dict[str, Any], memory: Dict[str, Any]) -> str:
    company_name = get_client_name(meta, memory)
    week = memory.get("week") or meta.get("week") or "Unknown Week"
    client_id = memory.get("client_id") or meta.get("client_id") or "unknown_client"
    categories = memory.get("categories", {})

    if not isinstance(categories, dict):
        raise RuntimeError("operational_memory.json categories must be an object")

    grouped = group_categories_by_trend(categories)
    recommendations = build_recommended_focus(categories)

    lines = [
        f"# Weekly Client Intelligence Summary - {company_name}",
        "",
        f"**Client ID:** `{client_id}`",
        f"**Week:** `{week}`",
        f"**Memory Version:** `{memory.get('memory_version', 'unknown')}`",
        "",
        "## Executive Readout",
        "",
    ]

    persistent_count = len(grouped.get("persistent", []))
    new_count = len(grouped.get("new", []))
    worsening_count = len(grouped.get("worsening", []))
    improving_count = len(grouped.get("improving", []))
    resolved_count = len(grouped.get("resolved", []))

    lines.append(
        f"This week's operational memory shows **{persistent_count} persistent**, "
        f"**{new_count} new**, **{worsening_count} worsening**, "
        f"**{improving_count} improving**, and **{resolved_count} resolved** signals."
    )

    lines.extend(["", "## Trend Breakdown", ""])

    for trend in TREND_ORDER:
        category_names = grouped.get(trend, [])

        if not category_names:
            continue

        lines.append(f"### {trend.replace('_', ' ').title()}")
        lines.append("")

        for category in category_names:
            entry = categories.get(category, {})
            lines.append(category_sentence(category, entry))

        lines.append("")

    lines.extend(["## Recommended Focus", ""])

    for recommendation in recommendations:
        lines.append(f"- {recommendation}")

    lines.extend(
        [
            "",
            "## Raw Category Snapshot",
            "",
        ]
    )

    for category, entry in categories.items():
        if not isinstance(entry, dict):
            continue

        label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"- Status: `{entry.get('status', 'unknown')}`")
        lines.append(f"- Previous Status: `{entry.get('previous_status', 'unknown')}`")
        lines.append(f"- Trend Delta: `{entry.get('trend_delta', 'insufficient_history')}`")
        lines.append(f"- Weeks Observed: `{entry.get('weeks_observed', 0)}`")
        lines.append(f"- Severity: `{entry.get('severity', 1)}/5`")
        lines.append(f"- Summary: {entry.get('summary', 'No summary available.')}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_client_intelligence_summary(client_dir: Path) -> Path:
    meta = load_json(client_dir / "meta.json")
    memory = load_json(client_dir / "operational_memory.json")

    summary = build_intelligence_summary(meta=meta, memory=memory)

    output_path = client_dir / "client_intelligence_summary.md"
    output_path.write_text(summary, encoding="utf-8")

    return output_path
