import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MEMORY_VERSION = "1.5"


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
    "forecast": "unknown",
    "forecast_confidence": "low",
    "forecast_reason": "insufficient history available",
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
    Converts observed evidence volume into a raw operational severity score.

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


def _recent_average(values: List[int], limit: int = 3) -> Optional[float]:
    if not values:
        return None

    recent_values = values[-limit:]

    if not recent_values:
        return None

    return sum(recent_values) / len(recent_values)


def _smooth_severity(
    raw_severity: int,
    previous_entry: Dict[str, Any],
    has_current_evidence: bool,
) -> int:
    """
    Smooths raw keyword severity so one noisy week does not over-amplify the dashboard.

    Rules:
    - If there is no evidence this week, allow severity to drop to 1 immediately.
      This preserves resolved/unknown behavior.
    - If there is no previous history, use the raw score.
    - If there is history, limit week-over-week movement to one severity level.
    - A category can still rise or improve, just not whiplash from 2 to 4 or 4 to 2
      in one generated week without more history.

    This keeps dynamic severity real while making trend movement more executive-safe.
    """

    raw = _normalize_severity(raw_severity)

    if not has_current_evidence:
        return 1

    history = _coerce_severity_history(previous_entry.get("severity_history", []))

    if not history:
        previous_severity = previous_entry.get("severity")
        try:
            history = [_normalize_severity(previous_severity)]
        except Exception:
            history = []

    average = _recent_average(history, limit=3)

    if average is None:
        return raw

    max_allowed = math.ceil(average + 1)
    min_allowed = math.floor(average - 1)

    smoothed = max(min_allowed, min(raw, max_allowed))

    return _normalize_severity(smoothed)


def _status_from_severity(severity: int, fallback_status: str, has_current_evidence: bool) -> str:
    """
    Keeps category status aligned with final severity while preserving useful
    category-specific labels like watch, increasing, and active.

    Severity 4+ becomes high.
    Severity 3 keeps the category's operational posture.
    Severity 2 becomes moderate.
    Severity 1 becomes low unless the category had no evidence, in which case it
    becomes unknown.
    """

    value = _normalize_severity(severity)

    if not has_current_evidence:
        return "unknown"

    if value <= 1:
        return "low"

    if value == 2:
        return "moderate"

    if value == 3:
        normalized_fallback = _normalize_status(fallback_status)

        if normalized_fallback in {"high", "critical"}:
            return "watch"

        return normalized_fallback

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
    source of truth is now raw dynamic severity from keyword evidence volume.
    Final smoothing happens later when previous memory is available.
    """

    hits = _keyword_hits(text, keywords)
    hit_count = len(hits)
    has_current_evidence = bool(hits)

    raw_dynamic_severity = _calculate_dynamic_severity(hit_count)

    if severity is not None:
        fallback_severity = _normalize_severity(severity)
        raw_severity = max(raw_dynamic_severity, min(fallback_severity, 2))
    else:
        raw_severity = raw_dynamic_severity

    raw_severity = _normalize_severity(raw_severity)

    evidence = [f"Detected operational language around: {hit}" for hit in hits[:5]]

    if not has_current_evidence:
        return {
            "status": "unknown",
            "previous_status": "unknown",
            "trend_delta": "insufficient_history",
            "weeks_observed": 0,
            "summary": "No clear operational pattern detected this week.",
            "evidence": [],
            "severity": 1,
            "raw_severity": 1,
            "evidence_hit_count": 0,
            "severity_history": [1],
            "momentum": "stable",
            "forecast": "likely_stable",
            "forecast_confidence": "low",
            "forecast_reason": "no current operational evidence was detected this week",
        }

    return {
        "status": _status_from_severity(raw_severity, status, has_current_evidence),
        "previous_status": "unknown",
        "trend_delta": "insufficient_history",
        "weeks_observed": 1,
        "summary": summary,
        "evidence": evidence,
        "severity": raw_severity,
        "raw_severity": raw_severity,
        "evidence_hit_count": hit_count,
        "severity_history": [raw_severity],
        "momentum": "stable",
        "forecast": "likely_stable",
        "forecast_confidence": "low",
        "forecast_reason": "initial current-week evidence captured; more history is needed before stronger forecasting",
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



def _calculate_forecast(
    momentum: str,
    weeks_observed: int,
    severity_history: List[int],
    evidence_hit_count: int,
) -> Tuple[str, str, str]:
    """
    Produces a simple, explainable next-week directional forecast.

    Forecasting v1 is intentionally conservative and rule-based:
    - momentum is the primary signal
    - observed history controls confidence
    - evidence count helps explain weak/low-confidence cases

    This is not statistical prediction. It is an operational outlook layer built
    on top of severity history and momentum.
    """

    normalized_momentum = str(momentum or "unknown").strip().lower()

    try:
        observed_weeks = int(weeks_observed)
    except Exception:
        observed_weeks = 0

    try:
        hit_count = int(evidence_hit_count)
    except Exception:
        hit_count = 0

    history = _coerce_severity_history(severity_history)

    if observed_weeks >= 8 and len(history) >= 4:
        confidence = "high"
    elif observed_weeks >= 4 and len(history) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if observed_weeks <= 0 or not history:
        return (
            "likely_stable",
            "low",
            "no current operational evidence was detected this week",
        )

    if normalized_momentum == "rising":
        return (
            "likely_rising",
            confidence,
            "severity has increased relative to recent observations",
        )

    if normalized_momentum == "improving":
        return (
            "likely_improving",
            confidence,
            "severity has decreased relative to recent observations",
        )

    if hit_count <= 1 and observed_weeks < 4:
        return (
            "likely_stable",
            "low",
            "limited current-week evidence and limited history suggest a cautious stable outlook",
        )

    return (
        "likely_stable",
        confidence,
        "severity has remained stable across recent observations",
    )


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

            raw_severity = _normalize_severity(
                current_entry.get("raw_severity", current_entry.get("severity", 1))
            )
            evidence_hit_count = current_entry.get("evidence_hit_count", 0)

            try:
                has_current_evidence = int(evidence_hit_count) > 0
            except Exception:
                has_current_evidence = bool(current_entry.get("evidence"))

            severity = raw_severity if has_current_evidence else 1

            current_entry["severity"] = severity
            current_entry["severity_history"] = [severity]
            current_entry["momentum"] = "stable"

            forecast, confidence, reason = _calculate_forecast(
                momentum="stable",
                weeks_observed=current_entry.get("weeks_observed", 0),
                severity_history=[severity],
                evidence_hit_count=evidence_hit_count,
            )

            current_entry["forecast"] = forecast
            current_entry["forecast_confidence"] = confidence
            current_entry["forecast_reason"] = reason

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

        previous_status = previous_entry.get("status", "unknown")

        raw_severity = _normalize_severity(
            current_entry.get("raw_severity", current_entry.get("severity", 1))
        )
        evidence_hit_count = current_entry.get("evidence_hit_count", 0)

        try:
            has_current_evidence = int(evidence_hit_count) > 0
        except Exception:
            has_current_evidence = bool(current_entry.get("evidence"))

        smoothed_severity = _smooth_severity(
            raw_severity=raw_severity,
            previous_entry=previous_entry,
            has_current_evidence=has_current_evidence,
        )

        current_entry["raw_severity"] = raw_severity
        current_entry["severity"] = smoothed_severity

        fallback_status = current_entry.get("status", "unknown")
        current_status = _status_from_severity(
            severity=smoothed_severity,
            fallback_status=fallback_status,
            has_current_evidence=has_current_evidence,
        )

        current_entry["status"] = current_status
        current_entry["previous_status"] = _normalize_status(previous_status)
        current_entry["trend_delta"] = _calculate_trend_delta(
            current_status=current_status,
            previous_status=previous_status,
        )
        current_entry["weeks_observed"] = _calculate_weeks_observed(
            current_status=current_status,
            previous_entry=previous_entry,
        )

        severity_history, momentum = _calculate_momentum(
            severity=smoothed_severity,
            previous_entry=previous_entry,
        )

        current_entry["severity_history"] = severity_history
        current_entry["momentum"] = momentum

        forecast, confidence, reason = _calculate_forecast(
            momentum=momentum,
            weeks_observed=current_entry.get("weeks_observed", 0),
            severity_history=severity_history,
            evidence_hit_count=evidence_hit_count,
        )

        current_entry["forecast"] = forecast
        current_entry["forecast_confidence"] = confidence
        current_entry["forecast_reason"] = reason

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

    Version 1.5 adds Forecasting Layer v1:
    - raw_severity still captures this week's keyword evidence
    - severity is smoothed against recent history
    - momentum drives a simple next-week operational forecast
    - forecast, forecast_confidence, and forecast_reason are written per category
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
        raw_severity = data.get("raw_severity")
        evidence_hit_count = data.get("evidence_hit_count")
        severity_history = data.get("severity_history", [])
        momentum = data.get("momentum", "unknown")
        forecast = data.get("forecast", "unknown")
        forecast_confidence = data.get("forecast_confidence", "low")
        forecast_reason = data.get("forecast_reason", "insufficient history available")
        summary = data.get("summary", "No clear operational pattern detected.")

        lines.append(f"- {category}:")
        lines.append(f"  - current_status: {status}")
        lines.append(f"  - previous_status: {previous_status}")
        lines.append(f"  - trend_delta: {trend_delta}")
        lines.append(f"  - weeks_observed: {weeks_observed}")
        lines.append(f"  - severity: {severity}/5")

        if raw_severity is not None:
            lines.append(f"  - raw_severity: {raw_severity}/5")

        if evidence_hit_count is not None:
            lines.append(f"  - evidence_hit_count: {evidence_hit_count}")

        lines.append(f"  - severity_history: {severity_history}")
        lines.append(f"  - momentum: {momentum}")
        lines.append(f"  - forecast: {forecast}")
        lines.append(f"  - forecast_confidence: {forecast_confidence}")
        lines.append(f"  - forecast_reason: {forecast_reason}")
        lines.append(f"  - summary: {summary}")

    return "\n".join(lines)
