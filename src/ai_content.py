import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"

MAX_PREVIOUS_WEEKS = 3
MAX_SECTION_CHARS = 2200


TREND_KEYWORDS = {
    "weather": ["weather", "winter", "snow", "ice", "rain", "fog", "wind", "storm", "slick roads", "reduced visibility", "great lakes", "mountain", "chains"],
    "detention": ["detention", "wait time", "waiting", "dock delay", "warehouse delay", "loading delay", "unloading delay", "appointment"],
    "parking": ["parking", "staging", "overnight parking", "safe parking", "truck stop", "rest area", "limited parking"],
    "congestion": ["congestion", "traffic", "metro", "rush hour", "urban", "chicago", "detroit", "milwaukee", "columbus", "indianapolis"],
    "paperwork": ["paperwork", "bol", "pod", "documentation", "documents", "timestamps", "arrival time", "release time", "signatures"],
    "equipment": ["equipment", "tractor", "trailer", "maintenance", "pre-trip", "post-trip", "tires", "brakes", "lights", "reefer", "securement"],
    "fatigue_hos": ["fatigue", "hours of service", "hos", "reset", "rest", "break", "sleep", "alert"],
    "backing_customer_site": ["backing", "dock", "yard", "customer site", "spotter", "forklift", "pedestrian", "loading area"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_current_week_key() -> str:
    override = os.getenv("WEEK_KEY", "").strip()
    if override:
        return override

    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def week_sort_key(week_name: str) -> tuple[int, int]:
    match = re.match(r"^(\d{4})-W(\d{2})$", week_name)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def find_previous_week_dirs(current_week: str, limit: int = MAX_PREVIOUS_WEEKS) -> List[Path]:
    if not OUTPUT_DIR.exists():
        return []

    week_dirs = [
        path
        for path in OUTPUT_DIR.iterdir()
        if path.is_dir() and re.match(r"^\d{4}-W\d{2}$", path.name)
    ]

    previous_dirs = [
        path
        for path in week_dirs
        if week_sort_key(path.name) < week_sort_key(current_week)
    ]

    previous_dirs = sorted(previous_dirs, key=lambda path: week_sort_key(path.name), reverse=True)
    return previous_dirs[:limit]


def read_section_excerpt(path: Path, max_chars: int = MAX_SECTION_CHARS) -> str:
    if not path.exists():
        return ""

    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""

    if not text:
        return ""

    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0].strip()

    return text


def load_recent_sections(client: Dict[str, Any], content_type: str) -> List[Dict[str, str]]:
    current_week = get_current_week_key()
    previous_week_dirs = find_previous_week_dirs(current_week)

    client_id = str(client.get("client_id", "")).strip()
    if not client_id:
        return []

    recent_sections: List[Dict[str, str]] = []

    for week_dir in previous_week_dirs:
        section_path = week_dir / client_id / f"{content_type}.md"
        text = read_section_excerpt(section_path)

        if not text:
            continue

        recent_sections.append(
            {
                "week": week_dir.name,
                "content_type": content_type,
                "text": text,
            }
        )

    return recent_sections


def count_keyword_groups(text: str) -> Dict[str, int]:
    lowered = text.lower()
    counts: Dict[str, int] = {}

    for group, keywords in TREND_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            count += lowered.count(keyword.lower())

        if count:
            counts[group] = count

    return counts


def summarize_trend_counts(recent_sections: List[Dict[str, str]]) -> List[str]:
    combined_counts: Dict[str, int] = {}

    for section in recent_sections:
        counts = count_keyword_groups(section["text"])

        for group, count in counts.items():
            combined_counts[group] = combined_counts.get(group, 0) + count

    if not combined_counts:
        return []

    sorted_groups = sorted(combined_counts.items(), key=lambda item: item[1], reverse=True)

    trend_labels = {
        "weather": "weather / seasonal road conditions",
        "detention": "detention and appointment pressure",
        "parking": "parking and staging limits",
        "congestion": "metro congestion and routing pressure",
        "paperwork": "paperwork and documentation",
        "equipment": "equipment inspections and maintenance",
        "fatigue_hos": "fatigue and hours-of-service planning",
        "backing_customer_site": "backing, dock, and customer-site safety",
    }

    return [
        trend_labels.get(group, group)
        for group, _ in sorted_groups[:5]
    ]


def memory_report_path() -> Path:
    week = get_current_week_key()
    week_dir = OUTPUT_DIR / week
    week_dir.mkdir(parents=True, exist_ok=True)
    return week_dir / "ai_memory_report.json"


def write_ai_memory_report(
    client: Dict[str, Any],
    content_type: str,
    recent_sections: List[Dict[str, str]],
    trend_themes: List[str],
) -> None:
    path = memory_report_path()

    if path.exists():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            report = {}
    else:
        report = {}

    current_week = get_current_week_key()
    client_id = str(client.get("client_id", "")).strip()
    company_name = str(client.get("company_name", client_id)).strip()

    report.setdefault("week", current_week)
    report["updated_at"] = now_iso()
    report.setdefault("max_previous_weeks", MAX_PREVIOUS_WEEKS)
    report.setdefault("clients", {})

    client_record = report["clients"].setdefault(
        client_id,
        {
            "client_id": client_id,
            "company_name": company_name,
            "sections": {},
        },
    )

    client_record["sections"][content_type] = {
        "content_type": content_type,
        "memory_available": bool(recent_sections),
        "prior_weeks_used": [section["week"] for section in recent_sections],
        "prior_section_count": len(recent_sections),
        "trend_themes_detected": trend_themes,
        "recorded_at": now_iso(),
    }

    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def build_recent_history_context(client: Dict[str, Any], content_type: str) -> str:
    recent_sections = load_recent_sections(client, content_type)
    trend_themes = summarize_trend_counts(recent_sections)

    write_ai_memory_report(client, content_type, recent_sections, trend_themes)

    if not recent_sections:
        return """
Recent history:
No previous sections were available for this client/content type.
Write this as a fresh first-run section.
"""

    trend_text = "\n".join(f"- {line} appeared repeatedly" for line in trend_themes) if trend_themes else "- No strong recurring trend detected."

    excerpts = []

    for section in recent_sections:
        excerpts.append(
            f"""
--- {section['week']} / {section['content_type']} excerpt ---
{section['text']}
"""
        )

    return f"""
Recent history:
The following prior sections were found for this client/content type.

Detected recurring operational themes:
{trend_text}

Use this history for continuity and variation.
Do not copy prior wording.
Do not repeat the same hooks, section order, sentence patterns, or lane descriptions.
Keep recurring operational themes if they still fit, but rotate emphasis so this week feels like the next real weekly packet.

Recent excerpts:
{chr(10).join(excerpts)}
"""


def build_company_context(client: Dict[str, Any], content_type: str) -> str:
    company = client.get("company_name", "the carrier")
    fleet_size = client.get("fleet_size", "regional fleet")
    region = client.get("region", "regional lanes")
    equipment = client.get("equipment", "tractor-trailer")
    operation_type = client.get("operation_type", "regional trucking")
    hiring_for = client.get("hiring_for", "CDL-A drivers")
    target_driver = client.get("target_driver", "experienced CDL-A drivers")
    experience_required = client.get("experience_required", "CDL-A experience preferred")
    home_time = client.get("home_time", "home time varies by lane")
    pay_angle = client.get("pay_angle", "steady freight and practical dispatch communication")
    lanes = ", ".join(client.get("common_lanes", [])) or region
    pain_points = ", ".join(client.get("pain_points", [])) or "weather, detention, parking, and appointment pressure"
    benefits = ", ".join(client.get("benefits", [])) or "clear communication, safe routing, and practical dispatch support"
    contact_email = client.get("contact_email", "")
    contact_phone = client.get("contact_phone", "")
    website = client.get("website", "")

    return f"""
Company: {company}
Fleet size: {fleet_size}
Region: {region}
Equipment: {equipment}
Operation type: {operation_type}
Hiring focus: {hiring_for}
Target driver: {target_driver}
Experience required: {experience_required}
Home time: {home_time}
Pay/positioning angle: {pay_angle}
Common lanes: {lanes}
Operating pain points: {pain_points}
Driver support / benefits: {benefits}
Contact email: {contact_email}
Contact phone: {contact_phone}
Website: {website}
Content type: {content_type}
"""


def build_system_prompt(content_type: str) -> str:
    base_rules = """
You are generating trucking fleet communication content.

Global rules:
- Be operationally realistic.
- Do not invent pay numbers.
- Do not invent bonuses.
- Do not invent guarantees.
- Do not invent benefits that are not provided.
- Do not claim guaranteed home time, guaranteed miles, or guaranteed pay.
- Avoid hype language like "best", "unbeatable", "top paying", or "dream job".
- Keep claims grounded in the company context.
- Write clearly for trucking operators, drivers, dispatchers, and recruiters.
- Do not include markdown code fences.
- If recent history is provided, use it for continuity only.
- Do not copy recent-history wording.
- Avoid repeating the same post hooks, lane descriptions, and sentence patterns from recent weeks.
- Preserve operational continuity while rotating emphasis.
"""

    section_roles = {
        "recruiting_posts": """
Role:
You are a trucking fleet recruiter writing honest CDL-A recruiting copy.

Voice:
- Driver-facing.
- Practical.
- Direct.
- Respectful of experienced drivers.
- No fake excitement or mega-carrier hype.

Priorities:
- Explain the real operating fit.
- Mention equipment, region, lane realities, driver expectations, and communication style.
- Make the job sound credible, not inflated.
- Include contact information in each post.
- If recent recruiting posts are provided, vary the opening hooks and avoid repeating the same pitch structure.

Structure:
- Start with "# Recruiting Posts".
- Write exactly 5 posts.
- Use headings like "### Post 1 - CDL-A Regional Opportunity".
- Each post should feel slightly different, not copy-pasted.
""",
        "social_posts": """
Role:
You are a trucking company social media coordinator writing short operational posts.

Voice:
- Public-facing.
- Shorter and punchier than the internal sections.
- Clear enough for drivers, prospects, and customers.
- No corporate fluff.

Priorities:
- One safety/operations post.
- One paperwork, detention, or customer-delay post.
- One recruiting reality-check post.
- Keep each post tight and usable on LinkedIn/Facebook.
- If recent social posts are provided, change the angles and phrasing.

Structure:
- Start with "# Social Posts".
- Write exactly 3 posts.
- Use headings like "### Post 1 - Weather & Route Awareness".
- Keep each post concise.
""",
        "safety_reminders": """
Role:
You are a fleet safety manager writing weekly driver safety reminders.

Voice:
- Firm.
- Practical.
- Safety-first.
- Driver-respectful, not preachy.

Priorities:
- Equipment-specific safety.
- Route and weather awareness.
- Parking and fatigue.
- Backing and customer-site safety.
- Documentation and dispatch communication.
- Make it feel like it came from safety/operations, not recruiting.
- If recent safety reminders are provided, keep recurring safety priorities but rotate the emphasis.

Structure:
- Start with "# Safety Reminders".
- Use clear section headings.
- Prefer bullet points where useful.
- Avoid sales language.
""",
        "company_update": """
Role:
You are an operations manager writing a weekly internal fleet update.

Voice:
- Internal.
- Calm.
- Dispatch-aware.
- Focused on execution and weekly priorities.

Priorities:
- Quick status.
- Lane notes.
- Operating risks.
- Paperwork/detention.
- Equipment/maintenance.
- HOS/fatigue.
- Weekly priorities.
- This should sound like it is for current drivers and dispatch, not new applicants.
- If recent company updates are provided, preserve continuity but avoid repeating the same wording.

Structure:
- Start with "# Company Update".
- Use operational headings.
- Keep it organized and practical.
- Avoid recruiting language except contact info where naturally needed.
""",
        "freight_digest": """
Role:
You are a trucking operations analyst writing a freight and lane digest.

Voice:
- Analytical.
- Grounded.
- Lane-specific.
- Less emotional than recruiting or social.

Priorities:
- Operational overview.
- Lane-specific notes.
- Weather, parking, detention, fuel/routing, documentation, and driver safety.
- Make the lane notes feel specific to the region and equipment.
- Focus on freight movement and operational reality.
- If recent freight digests are provided, avoid repeating the same lane commentary word-for-word and vary operational emphasis.
- Use the trend history to rotate analysis focus across weeks.

Structure:
- Start with "# Freight Digest".
- Use clear headings.
- Include lane-specific subsections.
- Avoid recruiter-style language until a short final contact line, if needed.
""",
    }

    return base_rules + "\n" + section_roles.get(
        content_type,
        """
Role:
You are a trucking operations communicator.

Voice:
- Practical.
- Clear.
- Grounded.

Structure:
- Use clear headings.
""",
    )


def build_prompt(client: Dict[str, Any], content_type: str) -> str:
    context = build_company_context(client, content_type)
    recent_history = build_recent_history_context(client, content_type)

    return f"""
Use the company context below to write the requested section.

{context}

{recent_history}

Important:
- Only use details supported by the company context.
- Do not add unlisted pay numbers, bonuses, guarantees, benefits, dedicated lanes, or policy claims.
- Mention practical trucking realities.
- Make the output client-ready.
- Keep this week's content distinct from recent weeks when recent-history content is available.
- Use trend history to continue the operational narrative without sounding repetitive.
"""


def generate_ai_content(
    client: Dict[str, Any],
    content_type: str,
    fallback_text: str,
) -> str:
    if not has_openai_key():
        return fallback_text

    try:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        client_api = OpenAI(api_key=api_key)

        response = client_api.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": build_system_prompt(content_type),
                },
                {
                    "role": "user",
                    "content": build_prompt(client, content_type),
                },
            ],
            temperature=0.7,
        )

        text = response.choices[0].message.content

        if not text or not text.strip():
            return fallback_text

        return text.strip()

    except Exception as e:
        print(f"AI content generation failed for {content_type}: {e}")
        return fallback_text
