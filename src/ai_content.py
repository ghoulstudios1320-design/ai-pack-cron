import os
from typing import Dict, Any

from openai import OpenAI


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


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

    return f"""
Use the company context below to write the requested section.

{context}

Important:
- Only use details supported by the company context.
- Do not add unlisted pay numbers, bonuses, guarantees, benefits, dedicated lanes, or policy claims.
- Mention practical trucking realities.
- Make the output client-ready.
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
            temperature=0.65,
        )

        text = response.choices[0].message.content

        if not text or not text.strip():
            return fallback_text

        return text.strip()

    except Exception as e:
        print(f"AI content generation failed for {content_type}: {e}")
        return fallback_text
