import json
import os
from openai import OpenAI


AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def ai_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_ai_section(
    section_name: str,
    client_config: dict,
    week_label: str,
    memory_context: dict | None = None,
    fallback_text: str = "",
) -> dict:
    """
    Generates one WHOA Weekly content section with safe fallback behavior.
    Returns:
    {
      "enabled": bool,
      "section": str,
      "content": str,
      "error": str | None
    }
    """

    if not ai_enabled():
        return {
            "enabled": False,
            "section": section_name,
            "content": fallback_text,
            "error": "OPENAI_API_KEY not set",
        }

    company_name = client_config.get("company_name", "the carrier")
    region = client_config.get("region", "the operating region")
    fleet_size = client_config.get("fleet_size", "small fleet")
    equipment_type = client_config.get(
        "equipment_type",
        client_config.get("equipment", "commercial trucks"),
    )
    primary_lanes = client_config.get(
        "primary_lanes",
        client_config.get("common_lanes", "regional freight lanes"),
    )
    voice = client_config.get(
        "voice",
        "clear, practical, trucking-operations focused",
    )

    voice_profile = client_config.get("voice_profile", {})
    voice_profile_json = json.dumps(voice_profile, indent=2)

    memory_json = json.dumps(memory_context or {}, indent=2)

    prompt = f"""
You are generating a weekly trucking communication section for WHOA Weekly.

Section:
{section_name}

Client:
- Company: {company_name}
- Region: {region}
- Fleet size: {fleet_size}
- Equipment type: {equipment_type}
- Primary lanes: {primary_lanes}
- Voice: {voice}
- Week: {week_label}

Voice Profile:
{voice_profile_json}

Memory / prior-week context:
{memory_json}

Rules:
- Sound operationally realistic.
- Follow the client's voice profile closely.
- Make each carrier sound distinct from the others.
- Do not invent fake pay, fake lanes, fake contracts, fake guarantees, or fake customer names.
- No emojis.
- Keep it concise and useful.
- Write like this could go directly into a weekly fleet communication pack.
- Avoid generic AI wording.
- Avoid corporate buzzwords unless the client voice profile asks for them.
- Mention the company name naturally where useful.
- Use prior-week memory when available, but do not over-explain it.
- If trends repeat across weeks, reference them naturally.
- If the section is social posts, produce multiple short post-ready items.
- If the section is safety reminders, produce practical reminders drivers can act on.
- If the section is recruiting, focus on realistic driver-facing messaging.
- If the section is company update, keep it professional and fleet-oriented.
- If the section is freight digest, summarize freight/ops themes without pretending to know exact proprietary data.

Quality Examples:
Avoid this style:
- "Join our growing team."
- "We're excited to announce."
- "Freight remains steady."
- "As we move into another week."
- "Drive with us today."
- "Your safety is our top priority."

Prefer this style:
- "Drivers who are tired of guessing what dispatch will look like tomorrow should take a look."
- "This is the third straight week where appointment pressure is showing up on the same lanes."
- "If the reefer unit is acting strange at pickup, solve it there. Do not drag the problem 300 miles down I-5."
- "Flatbed drivers know securement is not a checklist item. It is the job."
- "If detention starts stacking up, call dispatch while there is still time to protect the appointment chain."
- "I-80 freight is moving, but traffic and weather are still eating time around the same chokepoints."

Writing Standard:
- Use concrete trucking language.
- Prefer driver-facing realism over marketing polish.
- Make the section sound like it came from someone who has had to answer the phone when freight is late.
- Do not use fake specifics, but do use the client’s actual lanes, equipment, region, and pain points.
Return only the finished section content in Markdown.
"""

    try:
        response = _client().chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
    "role": "system",
    "content": (
        "You are a veteran trucking operations manager with "
        "experience in dispatch, recruiting, fleet management, "
        "safety, maintenance planning, customer service, and "
        "daily trucking operations. Write like someone who has "
        "spent years running trucks, handling freight delays, "
        "equipment failures, detention, appointment windows, "
        "customer expectations, weather disruptions, and driver "
        "communication. Avoid sounding like a marketing agency. "
        "Avoid sounding like generic AI content. Sound like a "
        "real fleet manager, recruiter, dispatcher, or safety "
        "supervisor speaking to professional drivers."
    ),
},
                {"role": "user", "content": prompt},
            ],
            temperature=0.55,
        )

        content = response.choices[0].message.content.strip()

        return {
            "enabled": True,
            "section": section_name,
            "content": content,
            "error": None,
        }

    except Exception as exc:
        return {
            "enabled": False,
            "section": section_name,
            "content": fallback_text,
            "error": str(exc),
        }


def generate_all_ai_sections(
    client_config: dict,
    week_label: str,
    memory_context: dict | None = None,
    fallbacks: dict | None = None,
) -> dict:
    fallbacks = fallbacks or {}

    sections = [
        "recruiting_posts",
        "social_posts",
        "safety_reminders",
        "company_update",
        "freight_digest",
    ]

    results = {}

    for section in sections:
        results[section] = generate_ai_section(
            section_name=section,
            client_config=client_config,
            week_label=week_label,
            memory_context=memory_context,
            fallback_text=fallbacks.get(section, ""),
        )

    return results


def generate_ai_content(
    client: dict,
    content_type: str,
    fallback_text: str = "",
    memory_context: dict | None = None,
    week_label: str | None = None,
) -> str:
    """
    Compatibility wrapper used by generate_trucking_pack.py.
    Keeps the existing pipeline working while routing each section
    through the newer AI section generator.
    """

    result = generate_ai_section(
        section_name=content_type,
        client_config=client,
        week_label=week_label or os.getenv("WEEK_KEY", "current-week"),
        memory_context=memory_context,
        fallback_text=fallback_text,
    )

    return result["content"]
