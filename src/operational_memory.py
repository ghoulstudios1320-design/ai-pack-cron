import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MEMORY_VERSION = "1.3"


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
    "previous_status": "unknown",
    "trend_delta": "insufficient_history",
    "weeks_observed": 0,
    "summary": "No clear operational pattern detected yet.",
    "evidence": [],
    "severity": 1,
    "severity_history": [],
    "momentum": "unknown",
}


STATUS_RANK = {
    "unknown": 0,
    "low": 1,
    "stable": 1,
    "decreasing": 1,
    "moderate": 2,
    "active": 2,
    "watch": 3,
    "increasing": 4,
    "high": 5,
    "critical": 6,
}


ACTIVE_STATUSES = {
    "moderate",
    "active",
    "watch",
    "increasing",
    "high",
    "critical",
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


def _calculate_dynamic_severity(hit_count: int) -> int:
    """
    Converts observed evidence volume into an operational severity score.

    This replaces the old hardcoded severity values.

    Scoring model:
    - 4 = heavy evidence concentration
    - 3 = clear recurring evidence
    - 2 = light/moderate evidence
    - 1 = no or minimal evidence

    Severity is intentionally capped at 4 for now.
    Level 5 remains available later for explicit critical-event detection.
    """

    try:
        count = int(hit_count)
    except Exception:
        count = 0

    if count >= 8:
        return 4

    if count >= 5:
        return 3

    if count >= 2:
        return 2

    return 1


def _status_from_severity(severity: int, fallback_status: str) -> str:
    """
    Keeps category status aligned with observed severity while preserving the
    category's intended operational framing.

    This prevents a category with only one weak hit from being marked as
    increasing/high pressure just because its fallback label says so.
    """

    value = _normalize_severity(severity)

    if value <= 1:
        return "low"

    if value == 2:
        return "moderate"

    if value == 3:
        return _normalize_status(fallback_status)

    if value >= 4:
        return "high"

    return _normalize_status(fallback_status)


def _build_category(
    text: str,
    status: str,
    summary: str,
    keywords: List[str],
    severity: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Builds one operational memory category from generated weekly content.

    The severity argument remains optional for backward compatibility, but the
    source of truth is now dynamic severity from keyword evidence volume.
    """

    hits = _keyword_hits(text, keywords)
    hit_count = len(hits)

    dynamic_severity = _calculate_dynamic_severity(hit_count)

    if severity is not None:
        fallback_severity = _normalize_severity(severity)
        final_severity = max(dynamic_severity, min(fallback_severity, 2))
    else:
        final_severity = dynamic_severity

    final_severity = _normalize_severity(final_severity)

    evidence = [f"Detected operational language around: {hit}" for hit in hits[:5]]

    if not hits:
        return {
            "status": "unknown",
            "previous_status": "unknown",
            "trend_delta": "insufficient_history",
            "weeks_observed": 0,
            "summary": "No clear operational pattern detected this week.",
            "evidence": [],
            "severity": 1,
            "severity_history": [1],
            "momentum": "stable",
        }

    return {
        "status": _status_from_severity(final_severity, status),
        "previous_status": "unknown",
        "trend_delta": "insufficient_history",
        "weeks_observed": 1,
        "summary": summary,
        "evidence": evidence,
        "severity": final_severity,
        "severity_history": [final_severity],
        "momentum": "stable",
    }


def _is_active_status(status: str) -> bool:
    return _normalize_status(status) in ACTIVE_STATUSES


def _status_rank(status: str) -> int:
    return STATUS_RANK.get(_normalize_status(status), 0)


def _calculate_trend_delta(
    current_status: str,
    previous_status: str,
) -> str:
    current = _normalize_status(current_status)
    previous = _normalize_status(previous_status)

    current_active = _is_active_status(current)
    previous_active = _is_active_status(previous)

    if previous == "unknown" and current == "unknown":
        return "insufficient_history"

    if not previous_active and current_active:
        return "new"

    if previous_active and not current_active:
        return "resolved"

    if current_active and previous_active:
        current_rank = _status_rank(current)
        previous_rank = _status_rank(previous)

        if current_rank > previous_rank:
            return "worsening"

        if current_rank < previous_rank:
            return "improving"

        return "persistent"

    if current == previous:
        return "stable"

    return "changed"


def _calculate_weeks_observed(
    current_status: str,
    previous_entry: Dict[str, Any],
) -> int:
    if not _is_active_status(current_status):
        return 0

    previous_status = previous_entry.get("status", "unknown")
    previous_weeks = previous_entry.get("weeks_observed")

    try:
        previous_weeks = int(previous_weeks)
    except Exception:
        previous_weeks = None

    if _is_active_status(previous_status):
        if previous_weeks is None or previous_weeks < 1:
            return 2

        return previous_weeks + 1

    return 1


def _coerce_severity_history(raw_history: Any) -> List[int]:
    if not isinstance(raw_history, list):
        return []

    cleaned: List[int] = []

    for value in raw_history:
        try:
            cleaned.append(_normalize_severity(value))
        except Exception:
            continue

    return cleaned


def _calculate_momentum(
    severity: int,
    previous_entry: Dict[str, Any],
) -> Tuple[List[int], str]:
    """
    Carries forward severity history and labels short-term momentum.

    The history is capped at 8 observations so the file stays small.
    Momentum is intentionally conservative:
    - rising: current severity is meaningfully above prior average
    - improving: current severity is meaningfully below prior average
    - stable: no meaningful movement yet
    """

    current_severity = _normalize_severity(severity)

    history = _coerce_severity_history(previous_entry.get("severity_history", []))

    if not history:
        previous_severity = previous_entry.get("severity")
        try:
            history = [_normalize_severity(previous_severity)]
        except Exception:
            history = []

    history.append(current_severity)
    history = history[-8:]

    if len(history) < 2:
        return history, "stable"

    previous_values = history[:-1]

    if not previous_values:
        return history, "stable"

    previous_average = sum(previous_values) / len(previous_values)
    current = history[-1]

    if current > previous_average + 0.5:
        return history, "rising"

    if current < previous_average - 0.5:
        return history, "improving"

    return history, "stable"


def _apply_previous_memory(
    current_memory: Dict[str, Any],
    previous_memory: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    current_categories = current_memory.get("categories", {})

    if not previous_memory:
        for category in MEMORY_CATEGORIES:
            current_entry = current_categories.get(category)

            if not isinstance(current_entry, dict):
                continue

            severity = _normalize_severity(current_entry.get("severity", 1))
            current_entry["severity"] = severity
            current_entry["severity_history"] = [severity]
            current_entry["momentum"] = "stable"

        return current_memory

    previous_categories = previous_memory.get("categories", {})

    if not isinstance(previous_categories, dict):
        return current_memory

    for category in MEMORY_CATEGORIES:
        current_entry = current_categories.get(category)
        previous_entry = previous_categories.get(category, {})

        if not isinstance(current_entry, dict):
            continue

        if not isinstance(previous_entry, dict):
            previous_entry = {}

        current_status = current_entry.get("status", "unknown")
        previous_status = previous_entry.get("status", "unknown")

        current_entry["previous_status"] = _normalize_status(previous_status)
        current_entry["trend_delta"] = _calculate_trend_delta(
            current_status=current_status,
            previous_status=previous_status,
        )
        current_entry["weeks_observed"] = _calculate_weeks_observed(
            current_status=current_status,
            previous_entry=previous_entry,
        )

        severity = _normalize_severity(current_entry.get("severity", 1))
        current_entry["severity"] = severity

        severity_history, momentum = _calculate_momentum(
            severity=severity,
            previous_entry=previous_entry,
        )

        current_entry["severity_history"] = severity_history
        current_entry["momentum"] = momentum

    return current_memory


def _is_week_dir(path: Path) -> bool:
    return path.is_dir() and bool(re.match(r"^\d{4}-W\d{2}$", path.name))


def infer_previous_operational_memory_path(output_dir: Path) -> Optional[Path]:
    """
    Infers the previous available week's operational memory path from the current client output folder.

    Expected structure:
    output/
      2026-W31/
        cascade_cold_chain/
          operational_memory.json
      2026-W32/
        cascade_cold_chain/
          operational_memory.json

    Missing weeks are tolerated. The function chooses the nearest earlier week
    that contains operational_memory.json for the same client.
    """

    client_folder = output_dir.name
    current_week_dir = output_dir.parent
    output_root = current_week_dir.parent

    if not output_root.exists():
        return None

    week_dirs = sorted(
        [path for path in output_root.iterdir() if _is_week_dir(path)],
        key=lambda path: path.name,
    )

    prior_week_dirs = [
        path
        for path in week_dirs
        if path.name < current_week_dir.name
    ]

    for previous_week_dir in reversed(prior_week_dirs):
        previous_memory_path = (
            previous_week_dir
            / client_folder
            / "operational_memory.json"
        )

        if previous_memory_path.exists():
            return previous_memory_path

    return None


def build_operational_memory(
    client_id: str,
    week: str,
    output_dir: Path,
    previous_memory: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds structured operational memory from generated weekly content.

    Version 1.3 adds dynamic severity scoring:
    - severity is calculated from observed keyword evidence volume
    - severity_history continues to power momentum
    - hardcoded severity no longer dominates every category
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

    memory = {
        "client_id": client_id,
        "week": week,
        "memory_version": MEMORY_VERSION,
        "categories": {
            "appointment_pressure": _build_category(
                combined_text,
                status="increasing",
                summary="Appointment pressure appeared in this week's content through scheduling, delivery-window, or timing language.",
                keywords=[
                    "appointment",
                    "appointments",
                    "delivery window",
                    "delivery windows",
                    "on-time",
                    "on time",
                    "schedule",
                    "scheduled",
                    "scheduling",
                    "tight window",
                    "tight windows",
                    "time-sensitive",
                    "time sensitive",
                    "late delivery",
                    "late deliveries",
                    "check-in",
                    "check in",
                    "cutoff",
                    "cut-off",
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
                    "dock delays",
                    "dock wait",
                    "dock waits",
                    "waiting",
                    "wait time",
                    "wait times",
                    "live load",
                    "live loads",
                    "live unload",
                    "live unloads",
                    "shipper delay",
                    "shipper delays",
                    "receiver delay",
                    "receiver delays",
                    "loading delay",
                    "unloading delay",
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
                    "load volumes",
                    "load availability",
                    "available loads",
                    "shipments",
                    "shipment flow",
                    "demand",
                    "freight demand",
                    "freight flow",
                    "steady freight",
                    "volume remains steady",
                    "surge",
                    "surges",
                    "slowdown",
                    "softening",
                    "load flow",
                    "market volume",
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
                    "heavy rain",
                    "snow",
                    "fog",
                    "dense fog",
                    "wind",
                    "high winds",
                    "ice",
                    "icy",
                    "storm",
                    "storms",
                    "mountain pass",
                    "mountain passes",
                    "chain",
                    "chains",
                    "visibility",
                    "low visibility",
                    "road conditions",
                    "winter conditions",
                    "slick roads",
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
                    "pre trip",
                    "inspection",
                    "inspections",
                    "reefer",
                    "reefers",
                    "temperature unit",
                    "tires",
                    "tire",
                    "brakes",
                    "brake",
                    "lights",
                    "trailer",
                    "trailers",
                    "breakdown",
                    "breakdowns",
                    "equipment failure",
                    "equipment failures",
                    "malfunction",
                    "malfunctions",
                    "repair",
                    "repairs",
                ],
                severity=2,
            ),
            "customer_pressure": _build_category(
                combined_text,
                status="increasing",
                summary="Customer pressure appeared through service expectations, communication, appointment discipline, or delivery reliability language.",
                keywords=[
                    "customer",
                    "customers",
                    "receiver",
                    "receivers",
                    "shipper",
                    "shippers",
                    "service",
                    "service expectations",
                    "communication",
                    "clear communication",
                    "delivery expectations",
                    "reliability",
                    "delivery reliability",
                    "late",
                    "late freight",
                    "on-time",
                    "on time",
                    "expectations",
                    "account",
                    "accounts",
                    "customer-facing",
                    "customer facing",
                ],
                severity=3,
            ),
            "lane_activity": _build_category(
                combined_text,
                status="active",
                summary="Lane activity appeared through regional, state, corridor, route, or market-lane language.",
                keywords=[
                    "lane",
                    "lanes",
                    "regional",
                    "corridor",
                    "corridors",
                    "washington",
                    "oregon",
                    "idaho",
                    "montana",
                    "illinois",
                    "indiana",
                    "chicago",
                    "rockford",
                    "milwaukee",
                    "st. louis",
                    "st louis",
                    "pacific northwest",
                    "pnw",
                    "i-5",
                    "i-80",
                    "i-90",
                    "route",
                    "routes",
                    "market lane",
                    "market lanes",
                    "regional lane",
                    "regional lanes",
                ],
                severity=2,
            ),
        },
    }

    return _apply_previous_memory(memory, previous_memory)


def write_operational_memory(
    client_id: str,
    week: str,
    output_dir: Path,
    previous_memory_path: Optional[Path] = None,
) -> Path:
    if previous_memory_path is None:
        previous_memory_path = infer_previous_operational_memory_path(output_dir)

    previous_memory = None

    if previous_memory_path and previous_memory_path.exists():
        previous_memory = load_operational_memory(previous_memory_path)

    memory = build_operational_memory(
        client_id=client_id,
        week=week,
        output_dir=output_dir,
        previous_memory=previous_memory,
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
            "memory_version": MEMORY_VERSION,
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
        previous_status = data.get("previous_status", "unknown")
        trend_delta = data.get("trend_delta", "insufficient_history")
        weeks_observed = data.get("weeks_observed", 0)
        severity = data.get("severity", 1)
        severity_history = data.get("severity_history", [])
        momentum = data.get("momentum", "unknown")
        summary = data.get("summary", "No clear operational pattern detected.")

        lines.append(f"- {category}:")
        lines.append(f"  - current_status: {status}")
        lines.append(f"  - previous_status: {previous_status}")
        lines.append(f"  - trend_delta: {trend_delta}")
        lines.append(f"  - weeks_observed: {weeks_observed}")
        lines.append(f"  - severity: {severity}/5")
        lines.append(f"  - severity_history: {severity_history}")
        lines.append(f"  - momentum: {momentum}")
        lines.append(f"  - summary: {summary}")

    return "\n".join(lines)
