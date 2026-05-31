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

Return only the finished section content in Markdown.
"""

    try:
        response = _client().chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create practical trucking fleet communications "
                        "for small and mid-sized carriers. Write like someone "
                        "who understands dispatch, drivers, freight delays, "
                        "equipment issues, and customer appointment pressure."
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
