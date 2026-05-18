import os
from typing import Dict, Any, Optional

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

    return f"""
You are writing operationally realistic trucking company content.

Company: {company}
Region: {region}
Equipment: {equipment}
Hiring focus: {hiring_for}
Common lanes: {lanes}
Operating pain points: {pain_points}
Content type: {content_type}

Rules:
- Write like a real trucking operations/recruiting coordinator.
- No fake pay numbers.
- No fake guarantees.
- No exaggerated marketing claims.
- Mention practical trucking realities.
- Keep it useful, grounded, and client-ready.
- Use clear headings.
- Do not include markdown code fences.
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
