import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


CATEGORY_LABELS = {
    "appointment_pressure": "Appointment Pressure",
    "detention": "Detention",
    "freight_volume": "Freight Volume",
    "weather_disruption": "Weather Disruption",
    "equipment_issues": "Equipment Issues",
    "customer_pressure": "Customer Pressure",
    "lane_activity": "Lane Activity",
}


CATEGORY_WEIGHTS = {
    "appointment_pressure": 1.25,
    "detention": 1.2,
    "freight_volume": 0.85,
    "weather_disruption": 1.0,
    "equipment_issues": 1.1,
    "customer_pressure": 1.3,
    "lane_activity": 0.75,
}


TREND_MULTIPLIERS = {
    "worsening": 1.45,
    "new": 1.25,
    "persistent": 1.15,
    "changed": 1.0,
    "stable": 0.75,
    "improving": 0.55,
    "resolved": -0.75,
    "insufficient_history": 0.65,
}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required JSON file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def normalize_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def get_action_level(risk_score: int, worsening_count: int, urgent_categories: List[str]) -> str:
    if risk_score >= 80 or worsening_count >= 3 or urgent_categories:
        return "urgent"

    if risk_score >= 60 or worsening_count >= 1:
        return "elevated"

    if risk_score >= 35:
        return "monitor"

    return "normal"


def score_category(category: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    status = str(entry.get("status", "unknown"))
    previous_status = str(entry.get("previous_status", "unknown"))
    trend_delta = str(entry.get("trend_delta", "insufficient_history"))

    severity = normalize_int(entry.get("severity"), 1)
    weeks_observed = normalize_int(entry.get("weeks_observed"), 0)

    severity = max(1, min(severity, 5))
    weeks_observed = max(0, weeks_observed)

    category_weight = CATEGORY_WEIGHTS.get(category, 1.0)
    trend_multiplier = TREND_MULTIPLIERS.get(trend_delta, 1.0)

    persistence_bonus = 0.0
    if trend_delta == "persistent":
        persistence_bonus = min(weeks_observed * 1.5, 10.0)

    base_score = severity * 10
    weighted_score = (base_score * category_weight * trend_multiplier) + persistence_bonus

    if trend_delta == "resolved":
        weighted_score = max(0, weighted_score)

    score = clamp_score(weighted_score)

    return {
        "category": category,
        "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
        "status": status,
        "previous_status": previous_status,
        "trend_delta": trend_delta,
        "weeks_observed": weeks_observed,
        "severity": severity,
        "score": score,
        "summary": entry.get("summary", ""),
        "evidence_count": len(entry.get("evidence", [])) if isinstance(entry.get("evidence"), list) else 0,
    }


def summarize_counts(category_scores: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "persistent": 0,
        "new": 0,
        "worsening": 0,
        "improving": 0,
        "resolved": 0,
        "stable": 0,
        "changed": 0,
        "insufficient_history": 0,
    }

    for item in category_scores:
        trend_delta = item.get("trend_delta", "insufficient_history")

        if trend_delta not in counts:
            counts["changed"] += 1
        else:
            counts[trend_delta] += 1

    return counts


def identify_highest_risk_categories(
    category_scores: List[Dict[str, Any]],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    sorted_items = sorted(
        category_scores,
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    return sorted_items[:limit]


def identify_urgent_categories(category_scores: List[Dict[str, Any]]) -> List[str]:
    urgent = []

    for item in category_scores:
        severity = item.get("severity", 1)
        trend_delta = item.get("trend_delta", "insufficient_history")
        score = item.get("score", 0)

        if severity >= 4 and trend_delta in {"new", "worsening", "persistent"}:
            urgent.append(item["category"])
            continue

        if score >= 80:
            urgent.append(item["category"])

    return urgent


def build_recommended_actions(
    action_level: str,
    category_scores: List[Dict[str, Any]],
) -> List[str]:
    actions: List[str] = []

    by_category = {item["category"]: item for item in category_scores}

    appointment = by_category.get("appointment_pressure", {})
    detention = by_category.get("detention", {})
    equipment = by_category.get("equipment_issues", {})
    weather = by_category.get("weather_disruption", {})
    customer = by_category.get("customer_pressure", {})
    lane = by_category.get("lane_activity", {})
    freight = by_category.get("freight_volume", {})

    if action_level in {"elevated", "urgent"}:
        actions.append(
            "Review the highest-risk operational categories before publishing next week's content or client update."
        )

    if appointment.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Keep appointment pressure visible in dispatch-facing messaging and remind drivers to report timing issues early."
        )

    if detention.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Track detention as an active operational signal and keep documentation language in driver communication."
        )

    if customer.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Protect customer confidence with proactive delay communication, realistic ETAs, and documented exceptions."
        )

    if equipment.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Keep equipment readiness, pre-trip inspections, and pickup-site issue reporting prominent in safety reminders."
        )

    if weather.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Keep weather-sensitive lane planning and early route updates in the weekly communication cycle."
        )

    if lane.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Use active lane patterns to make recruiting and operations content specific to the carrier instead of generic."
        )

    if freight.get("trend_delta") in {"persistent", "worsening", "new"}:
        actions.append(
            "Watch freight-flow wording week to week to identify whether demand is steady, tightening, or softening."
        )

    if not actions:
        actions.append(
            "No major escalation detected. Continue normal monitoring and preserve current operational memory."
        )

    return actions


def build_summary_text(
    client_name: str,
    risk_score: int,
    action_level: str,
    counts: Dict[str, int],
    highest_risk_categories: List[Dict[str, Any]],
) -> str:
    top_labels = [
        item.get("label", item.get("category", "Unknown"))
        for item in highest_risk_categories
    ]

    top_text = ", ".join(top_labels) if top_labels else "none"

    return (
        f"{client_name} is at {action_level.upper()} action level with a risk score of "
        f"{risk_score}/100. Current operational memory shows "
        f"{counts.get('persistent', 0)} persistent, {counts.get('new', 0)} new, "
        f"{counts.get('worsening', 0)} worsening, {counts.get('improving', 0)} improving, "
        f"and {counts.get('resolved', 0)} resolved signals. Highest-risk categories: {top_text}."
    )


def calculate_overall_risk_score(category_scores: List[Dict[str, Any]]) -> int:
    if not category_scores:
        return 0

    total = sum(item.get("score", 0) for item in category_scores)

    # Seven categories at 100 each would be 700. Normalize to 100.
    normalized = (total / (len(category_scores) * 100)) * 100

    # Give persistent multi-category pressure a small system-wide bump.
    persistent_count = sum(
        1 for item in category_scores
        if item.get("trend_delta") == "persistent"
    )
    worsening_count = sum(
        1 for item in category_scores
        if item.get("trend_delta") == "worsening"
    )
    new_count = sum(
        1 for item in category_scores
        if item.get("trend_delta") == "new"
    )

    bump = 0
    if persistent_count >= 4:
        bump += 8
    if worsening_count:
        bump += worsening_count * 10
    if new_count >= 2:
        bump += 6

    return clamp_score(normalized + bump)


def build_trend_dashboard(meta: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
    client_id = memory.get("client_id") or meta.get("client_id") or "unknown_client"
    company_name = meta.get("company_name") or client_id
    week = memory.get("week") or meta.get("week") or "unknown_week"

    categories = memory.get("categories", {})
    if not isinstance(categories, dict):
        raise RuntimeError("operational_memory.json categories must be an object")

    category_scores = []

    for category, entry in categories.items():
        if not isinstance(entry, dict):
            continue

        category_scores.append(score_category(category, entry))

    counts = summarize_counts(category_scores)
    highest_risk_categories = identify_highest_risk_categories(category_scores)
    urgent_categories = identify_urgent_categories(category_scores)
    risk_score = calculate_overall_risk_score(category_scores)
    action_level = get_action_level(
        risk_score=risk_score,
        worsening_count=counts.get("worsening", 0),
        urgent_categories=urgent_categories,
    )

    recommended_actions = build_recommended_actions(
        action_level=action_level,
        category_scores=category_scores,
    )

    return {
        "client_id": client_id,
        "company_name": company_name,
        "week": week,
        "dashboard_version": "1.0",
        "memory_version": memory.get("memory_version", "unknown"),
        "risk_score": risk_score,
        "recommended_action_level": action_level,
        "signal_counts": counts,
        "highest_risk_categories": highest_risk_categories,
        "urgent_categories": urgent_categories,
        "recommended_actions": recommended_actions,
        "summary": build_summary_text(
            client_name=company_name,
            risk_score=risk_score,
            action_level=action_level,
            counts=counts,
            highest_risk_categories=highest_risk_categories,
        ),
        "category_scores": sorted(
            category_scores,
            key=lambda item: item.get("score", 0),
            reverse=True,
        ),
    }


def write_trend_dashboard(client_dir: Path) -> Path:
    meta = load_json(client_dir / "meta.json")
    memory = load_json(client_dir / "operational_memory.json")

    dashboard = build_trend_dashboard(meta=meta, memory=memory)

    output_path = client_dir / "trend_dashboard.json"
    output_path.write_text(
        json.dumps(dashboard, indent=2),
        encoding="utf-8",
    )

    return output_path
