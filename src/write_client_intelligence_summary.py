import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


SECTION_LABELS = {
    "recruiting_posts": "Recruiting",
    "social_posts": "Social",
    "safety_reminders": "Safety",
    "company_update": "Company Update",
    "freight_digest": "Freight Digest",
}


FOCUS_RECOMMENDATIONS = {
    "weather / seasonal road conditions": [
        "weather-aware routing",
        "driver fatigue during weather delays",
        "equipment readiness in changing conditions",
    ],
    "detention and appointment pressure": [
        "detention documentation habits",
        "appointment communication expectations",
        "driver time protection",
    ],
    "parking and staging limits": [
        "parking strategy",
        "legal staging options",
        "pre-planned rest breaks",
    ],
    "metro congestion and routing pressure": [
        "route timing strategy",
        "metro delay communication",
        "traffic-aware dispatch planning",
    ],
    "paperwork and documentation": [
        "clean paperwork habits",
        "BOL/POD accuracy",
        "detention proof collection",
    ],
    "equipment inspections and maintenance": [
        "pre-trip inspection discipline",
        "preventive maintenance reporting",
        "equipment readiness messaging",
    ],
    "fatigue and hours-of-service planning": [
        "HOS planning",
        "fatigue prevention",
        "reset strategy",
    ],
    "backing, dock, and customer-site safety": [
        "backing safety",
        "dock awareness",
        "customer-site hazard communication",
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_latest_week_dir() -> Path:
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

    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace").strip()


def get_client_meta(week_dir: Path, client_folder: str) -> Dict[str, Any]:
    meta = load_json(week_dir / client_folder / "meta.json")
    return meta or {}


def collect_memory_for_client(
    memory_report: Dict[str, Any],
    client_id: str,
) -> Dict[str, Any]:
    clients = memory_report.get("clients", {}) if memory_report else {}
    return clients.get(client_id, {})


def collect_trends(client_memory: Dict[str, Any]) -> Dict[str, Any]:
    sections = client_memory.get("sections", {})
    theme_counter: Counter[str] = Counter()
    section_theme_map: Dict[str, List[str]] = {}
    prior_weeks: List[str] = []
    memory_sections = 0

    for section_name, section_record in sections.items():
        if section_record.get("memory_available"):
            memory_sections += 1

        themes = section_record.get("trend_themes_detected", [])
        section_theme_map[section_name] = themes

        for theme in themes:
            theme_counter[theme] += 1

        for week in section_record.get("prior_weeks_used", []):
            if week not in prior_weeks:
                prior_weeks.append(week)

    return {
        "theme_counter": theme_counter,
        "section_theme_map": section_theme_map,
        "prior_weeks": prior_weeks,
        "memory_sections": memory_sections,
        "section_count": len(sections),
    }


def extract_client_text_signals(week_dir: Path, client_folder: str) -> Counter[str]:
    signal_keywords = {
        "weather": ["weather", "winter", "ice", "snow", "rain", "fog", "wind"],
        "detention": ["detention", "waiting", "wait time", "dock delay"],
        "parking": ["parking", "staging", "overnight"],
        "equipment": ["equipment", "maintenance", "pre-trip", "tractor", "trailer"],
        "dispatch": ["dispatch", "communication", "appointment"],
        "safety": ["safety", "backing", "fatigue", "hours of service", "hos"],
        "congestion": ["congestion", "traffic", "metro", "rush hour"],
    }

    files = [
        "recruiting_posts.md",
        "social_posts.md",
        "safety_reminders.md",
        "company_update.md",
        "freight_digest.md",
    ]

    combined = ""

    for filename in files:
        combined += "\n" + load_text(week_dir / client_folder / filename).lower()

    counter: Counter[str] = Counter()

    for label, keywords in signal_keywords.items():
        for keyword in keywords:
            counter[label] += combined.count(keyword)

    return counter


def recommended_focus_areas(theme_counter: Counter[str]) -> List[str]:
    recommendations: List[str] = []

    for theme, _ in theme_counter.most_common(5):
        for item in FOCUS_RECOMMENDATIONS.get(theme, []):
            if item not in recommendations:
                recommendations.append(item)

    defaults = [
        "driver communication habits",
        "parking and staging planning",
        "detention documentation",
        "safe routing decisions",
        "equipment readiness",
    ]

    for item in defaults:
        if len(recommendations) >= 6:
            break

        if item not in recommendations:
            recommendations.append(item)

    return recommendations[:6]


def build_client_summary(
    week_dir: Path,
    client: Dict[str, Any],
    memory_report: Dict[str, Any],
) -> List[str]:
    client_id = client.get("client_id", "")
    client_folder = client.get("client_folder", client_id)
    company_name = client.get("company_name", client_id)

    meta = get_client_meta(week_dir, client_folder)
    client_memory = collect_memory_for_client(memory_report, client_id)
    trend_data = collect_trends(client_memory)
    signal_counter = extract_client_text_signals(week_dir, client_folder)

    theme_counter: Counter[str] = trend_data["theme_counter"]
    section_theme_map: Dict[str, List[str]] = trend_data["section_theme_map"]
    prior_weeks: List[str] = trend_data["prior_weeks"]
    memory_sections = trend_data["memory_sections"]
    section_count = trend_data["section_count"]

    fleet_size = meta.get("fleet_size", "")
    region = meta.get("region", "")
    equipment = meta.get("equipment", "")
    hiring_for = meta.get("hiring_for", "")
    tagline = meta.get("tagline", "")

    top_themes = theme_counter.most_common(6)
    top_signals = signal_counter.most_common(6)
    focus_areas = recommended_focus_areas(theme_counter)

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
            f"- Memory Coverage: `{memory_sections}/{section_count}` sections",
            f"- Prior Weeks Used: `{', '.join(prior_weeks) if prior_weeks else 'none'}`",
            "",
            "### Recurring Operational Themes",
            "",
        ]
    )

    if top_themes:
        for theme, count in top_themes:
            lines.append(f"- {theme} `{count}`")
    else:
        lines.append("- No recurring memory themes detected yet.")

    lines.extend(
        [
            "",
            "### Current-Week Content Signals",
            "",
        ]
    )

    if top_signals:
        for signal, count in top_signals:
            if count > 0:
                lines.append(f"- {signal}: `{count}` mentions")
    else:
        lines.append("- No strong current-week text signals detected.")

    lines.extend(
        [
            "",
            "### Section Theme Breakdown",
            "",
            "| Section | Themes |",
            "|---|---|",
        ]
    )

    if section_theme_map:
        for section_name, themes in section_theme_map.items():
            label = SECTION_LABELS.get(section_name, section_name)
            theme_text = ", ".join(themes) if themes else "none"
            lines.append(f"| {label} | {theme_text} |")
    else:
        lines.append("| none | no section memory available |")

    lines.extend(
        [
            "",
            "### Recommended Future Content Focus",
            "",
        ]
    )

    for item in focus_areas:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "### Intelligence Read",
            "",
            build_intelligence_read(company_name, top_themes, top_signals, prior_weeks),
            "",
            "---",
            "",
        ]
    )

    return lines


def build_intelligence_read(
    company_name: str,
    top_themes: List[tuple[str, int]],
    top_signals: List[tuple[str, int]],
    prior_weeks: List[str],
) -> str:
    if not top_themes:
        return (
            f"{company_name} does not have enough trend memory yet for a strong intelligence read. "
            "Continue generating weekly packs to build a clearer operating profile."
        )

    primary_theme = top_themes[0][0]
    secondary_theme = top_themes[1][0] if len(top_themes) > 1 else None
    weeks_text = ", ".join(prior_weeks) if prior_weeks else "recent weeks"

    if secondary_theme:
        return (
            f"{company_name}'s recent communication pattern is anchored around {primary_theme}, "
            f"with secondary emphasis on {secondary_theme}. Based on memory from {weeks_text}, "
            "future content should keep the same operational identity while rotating the weekly focus "
            "to avoid sounding repetitive."
        )

    return (
        f"{company_name}'s recent communication pattern is anchored around {primary_theme}. "
        f"Based on memory from {weeks_text}, future content should maintain continuity while rotating "
        "supporting topics across recruiting, safety, and operations."
    )


def build_summary(week_dir: Path) -> str:
    manifest = load_json(week_dir / "distribution_manifest.json")

    if not manifest:
        raise RuntimeError(f"Missing distribution manifest in {week_dir}")

    memory_report = load_json(week_dir / "ai_memory_report.json") or {}
    clients = manifest.get("clients", [])
    week = manifest.get("week", week_dir.name)

    lines: List[str] = [
        f"# Client Intelligence Summary - {week}",
        "",
        f"Written At: `{now_iso()}`",
        f"Client Count: `{len(clients)}`",
        "",
        "This report summarizes recurring operational themes, AI memory coverage, current-week content signals, and recommended future content focus areas.",
        "",
        "---",
        "",
    ]

    for client in clients:
        lines.extend(build_client_summary(week_dir, client, memory_report))

    return "\n".join(lines)


def main() -> None:
    week_dir = find_latest_week_dir()
    summary = build_summary(week_dir)

    path = week_dir / "client_intelligence_summary.md"
    path.write_text(summary + "\n", encoding="utf-8")

    print(f"Wrote client intelligence summary: {path}")


if __name__ == "__main__":
    main()
