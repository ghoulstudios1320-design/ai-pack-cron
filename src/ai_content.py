import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


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


def find_previous_week_dir(current_week: str) -> Optional[Path]:
    if not OUTPUT_DIR.exists():
        return None

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

    if not previous_dirs:
        return None

    return sorted(previous_dirs, key=lambda path: week_sort_key(path.name))[-1]


def load_previous_section(client: Dict[str, Any], content_type: str) -> str:
    current_week = get_current_week_key()
    previous_week_dir = find_previous_week_dir(current_week)

    if not previous_week_dir:
        return ""

    client_id = str(client.get("client_id", "")).strip()

    if not client_id:
        return ""

    section_path = previous_week_dir / client_id / f"{content_type}.md"

    if not section_path.exists():
        return ""

    try:
        text = section_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""

    if not text:
        return ""

    max_chars = 3500

    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0].strip()

    return f"""
Previous week reference:
Week: {previous_week_dir.name}
Client: {client.get("company_name", client_id)}
Section: {content_type}

Use this only for continuity and variation.
Do not copy it.
Do not repeat the same hooks, examples, sentence patterns, or section phrasing.
Keep recurring operational themes if they still fit, but make this week's section feel fresh.

Previous section excerpt:
{text}
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
- If previous-week content is provided, use it for continuity only.
- Do not copy previous-week wording.
- Avoid repeating the same post hooks, lane descriptions, and sentence patterns from the previous week.
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
- If previous-week recruiting posts are provided, vary the opening hooks and avoid repeating the same pitch structure.

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
- If previous-week social posts are provided, change the angles and phrasing.

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
- If previous-week safety reminders are provided, keep recurring safety priorities but rotate the emphasis.

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
- If previous-week company update is provided, preserve continuity but avoid repeating the same wording.

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
- If previous-week freight digest is provided, avoid repeating the same lane commentary word-for-word and vary operational emphasis.

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
    previous_section = load_previous_section(client, content_type)

    previous_context_note = previous_section or """
Previous week reference:
No previous-week section was available for this client/content type.
Write this as a fresh first-run section.
"""

    return f"""
Use the company context below to write the requested section.

{context}

{previous_context_note}

Important:
- Only use details supported by the company context.
- Do not add unlisted pay numbers, bonuses, guarantees, benefits, dedicated lanes, or policy claims.
- Mention practical trucking realities.
- Make the output client-ready.
- Keep this week's content distinct from the previous week when previous-week content is available.
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
            temperature=0.68,
        )

        text = response.choices[0].message.content

        if not text or not text.strip():
            return fallback_text

        return text.strip()

    except Exception as e:
        print(f"AI content generation failed for {content_type}: {e}")
        return fallback_text
