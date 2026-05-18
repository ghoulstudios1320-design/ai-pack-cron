import os
from typing import Dict, Any

from openai import OpenAI


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def build_prompt(client: Dict[str, Any], content_type: str) -> str:
    company = client.get("company_name", "the carrier")
    region = client.get("region", "regional lanes")
    equipment = client.get("equipment", "tractor-trailer")
    hiring_for = client.get("hiring_for", "CDL-A drivers")
    lanes = ", ".join(client.get("common_lanes", [])) or region
    pain_points = ", ".join(client.get("pain_points", [])) or "weather, detention, parking, and appointment pressure"
    benefits = ", ".join(client.get("benefits", [])) or "clear communication, safe routing, and practical dispatch support"
    fleet_size = client.get("fleet_size", "regional fleet")
    operation_type = client.get("operation_type", "regional trucking")

    base = f"""
You are writing operationally realistic trucking company content.

Company: {company}
Fleet size: {fleet_size}
Region: {region}
Equipment: {equipment}
Operation type: {operation_type}
Hiring focus: {hiring_for}
Common lanes: {lanes}
Operating pain points: {pain_points}
Driver support / benefits: {benefits}
Content type: {content_type}

Rules:
- Write like a real trucking operations/recruiting coordinator.
- No fake pay numbers.
- No fake guarantees.
- No exaggerated marketing claims.
- Mention practical trucking realities.
- Keep it useful, grounded, and client-ready.
- Use clear markdown headings.
- Do not include markdown code fences.
"""

    if content_type == "freight_digest":
        return base + """
Freight digest requirements:
- Start with "# Freight Digest".
- Include a short operational overview.
- Include lane-specific notes.
- Include weather, parking, detention, fuel/routing, documentation, and driver safety notes.
- Make the content specific to the carrier's region, lanes, equipment, and pain points.
- Avoid repeating the exact same wording under every lane.
"""

    if content_type == "safety_reminders":
        return base + """
Safety reminders requirements:
- Start with "# Safety Reminders".
- Write for active drivers, not corporate executives.
- Include equipment-specific reminders.
- Include route/weather/customer safety.
- Include parking, fatigue, backing, documentation, and dispatch communication.
- Keep the tone firm, practical, and safety-first.
- Do not invent accidents, violations, pay, bonuses, or guarantees.
- Make the reminders specific to the carrier's region, lanes, equipment, and pain points.
"""

    if content_type == "company_update":
        return base + """
Company update requirements:
- Start with "# Company Update".
- Write as a weekly driver-facing operations update.
- Include quick status, lane notes, operating risks, paperwork/detention, equipment/maintenance, HOS/fatigue, and weekly priorities.
- Make it specific to the carrier's region, equipment, lanes, and pain points.
- Keep the tone professional, practical, and dispatch-realistic.
- Do not invent company announcements, accidents, pay changes, bonuses, policy changes, or guarantees.
- Do not make legal or regulatory claims beyond normal safe trucking practices.
"""

    return base


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
                    "content": "You generate concise, operationally realistic trucking fleet content.",
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
