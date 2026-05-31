import json
from pathlib import Path
from typing import Any, Dict, List


MEMORY_CATEGORIES = [
    "appointment_pressure",
    "detention",
    "freight_volume",
    "weather_disruption",
    "equipment_issues",
    "customer_pressure",
    "lane_activity",
]


DEFAULT_CATEGORY_MEMORY = {
    "status": "unknown",
    "summary": "No clear operational pattern detected yet.",
    "evidence": [],
    "severity": 1,
}


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_status(raw_status: str) -> str:
    if not raw_status:
        return "unknown"

    value = raw_status.strip().lower()

    allowed = {
        "unknown",
        "low",
        "stable",
        "moderate",
        "active",
        "watch",
        "increasing",
        "decreasing",
        "high",
        "critical",
    }

    return value if value in allowed else "watch"


def _normalize_severity(raw_value: Any) -> int:
    try:
        value = int(raw_value)
    except Exception:
        return 1

    return max(1, min(value, 5))


def _keyword_hits(text: str, keywords: List[str]) -> List[str]:
    lowered = text.lower()
    hits = []

    for keyword in keywords:
        if keyword.lower() in lowered:
            hits.append(keyword)

    return hits


def _build_category(
    text: str,
    status: str,
    summary: str,
    keywords: List[str],
    severity: int,
) -> Dict[str, Any]:
    hits = _keyword_hits(text, keywords)

    evidence = [f"Detected operational language around: {hit}" for hit in hits[:5]]

    if not hits:
        return {
            "status": "unknown",
            "summary": "No clear operational pattern detected this week.",
            "evidence": [],
            "severity": 1,
        }

    return {
        "status": _normalize_status(status),
        "summary": summary,
        "evidence": evidence,
        "severity": _normalize_severity(severity),
    }


def build_operational_memory(
    client_id: str,
    week: str,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Builds structured operational memory from generated weekly content.

    This is intentionally deterministic for the first version.
    Later, this can be upgraded to use AI classification.
    """

    source_files = [
        "full_pack.md",
        "freight_digest.md",
        "safety_reminders.md",
        "company_update.md",
        "recruiting_posts.md",
        "social_posts.md",
    ]

    combined_text = "\n\n".join(
        _safe_read_text(output_dir / filename)
        for filename in source_files
    )

    categories = {
        "appointment_pressure": _build_category(
            combined_text,
            status="increasing",
            summary="Appointment pressure appeared in this week's content through scheduling, delivery-window, or timing language.",
            keywords=[
                "appointment",
                "delivery window",
                "on-time",
                "schedule",
                "tight window",
                "time-sensitive",
                "late delivery",
                "check-in",
            ],
            severity=3,
        ),
        "detention": _build_category(
            combined_text,
            status="watch",
            summary="Detention risk appeared through waiting, loading, unloading, or dock-delay language.",
            keywords=[
                "detention",
                "dock delay",
                "waiting",
                "wait time",
                "live load",
                "live unload",
                "shipper delay",
                "receiver delay",
            ],
            severity=3,
        ),
        "freight_volume": _build_category(
            combined_text,
            status="moderate",
            summary="Freight volume appeared through load-flow, shipment, lane, or demand language.",
            keywords=[
                "freight volume",
                "load volume",
                "shipments",
                "demand",
                "freight flow",
                "steady freight",
                "surge",
                "slowdown",
            ],
            severity=2,
        ),
        "weather_disruption": _build_category(
            combined_text,
            status="watch",
            summary="Weather disruption appeared through road-condition, mountain-pass, rain, snow, fog, or wind language.",
            keywords=[
                "weather",
                "rain",
                "snow",
                "fog",
                "wind",
                "ice",
                "mountain pass",
                "chain",
                "visibility",
                "road conditions",
            ],
            severity=3,
        ),
        "equipment_issues": _build_category(
            combined_text,
            status="watch",
            summary="Equipment issues appeared through inspection, maintenance, reefer, tire, brake, or trailer-readiness language.",
            keywords=[
                "equipment",
                "maintenance",
                "pre-trip",
                "inspection",
                "reefer",
                "tires",
                "brakes",
                "lights",
                "trailer",
                "breakdown",
            ],
            severity=2,
        ),
        "customer_pressure": _build_category(
            combined_text,
            status="increasing",
            summary="Customer pressure appeared through service expectations, communication, appointment discipline, or delivery reliability language.",
            keywords=[
                "customer",
                "receiver",
                "shipper",
                "service",
                "communication",
                "delivery expectations",
                "reliability",
                "late",
                "on-time",
            ],
            severity=3,
        ),
        "lane_activity": _build_category(
            combined_text,
            status="active",
            summary="Lane activity appeared through regional, state, corridor, route, or market-lane language.",
            keywords=[
                "lane",
                "regional",
                "corridor",
                "washington",
                "oregon",
                "idaho",
                "pacific northwest",
                "pnw",
                "i-5",
                "i-90",
                "route",
            ],
            severity=2,
        ),
    }

    return {
        "client_id": client_id,
        "week": week,
        "memory_version": "1.0",
        "categories": categories,
    }


def write_operational_memory(
    client_id: str,
    week: str,
    output_dir: Path,
) -> Path:
    memory = build_operational_memory(
        client_id=client_id,
        week=week,
        output_dir=output_dir,
    )

    output_path = output_dir / "operational_memory.json"
    output_path.write_text(
        json.dumps(memory, indent=2),
        encoding="utf-8",
    )

    return output_path


def load_operational_memory(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "memory_version": "1.0",
            "categories": {
                category: DEFAULT_CATEGORY_MEMORY.copy()
                for category in MEMORY_CATEGORIES
            },
        }

    return json.loads(path.read_text(encoding="utf-8"))


def format_operational_memory_for_prompt(memory: Dict[str, Any]) -> str:
    categories = memory.get("categories", {})

    lines = [
        "Structured operational memory:",
        "",
    ]

    for category in MEMORY_CATEGORIES:
        data = categories.get(category, DEFAULT_CATEGORY_MEMORY)

        status = data.get("status", "unknown")
        severity = data.get("severity", 1)
        summary = data.get("summary", "No clear operational pattern detected.")

        lines.append(f"- {category}:")
        lines.append(f"  - status: {status}")
        lines.append(f"  - severity: {severity}/5")
        lines.append(f"  - summary: {summary}")

    return "\n".join(lines)
