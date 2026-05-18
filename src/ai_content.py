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
    target_driver = client.get("target_driver", "experienced CDL-A drivers")
    experience_required = client.get("experience_required", "CDL-A experience preferred")
    home_time = client.get("home_time", "home time varies by lane")
    pay_angle = client.get("pay_angle", "steady freight and practical dispatch communication")
    operation_type = client.get("operation_type", "regional trucking")
    lanes = ", ".join(client.get("common_lanes", [])) or region
    pain_points = ", ".join(client.get("pain_points", [])) or "weather, detention, parking, and appointment pressure"
    benefits = ", ".join(client.get("benefits", [])) or "clear communication, safe routing, and practical dispatch support"
    fleet_size = client.get("fleet_size", "regional fleet")
    contact_email = client.get("contact_email", "")
    contact_phone = client.get("contact_phone", "")
    website = client.get("website", "")

    base = f"""
You are writing operationally realistic trucking company content.

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

Rules:
- Write like a real trucking operations/recruiting coordinator.
- No fake pay numbers.
- No fake guarantees.
- No exaggerated marketing claims.
- Do not invent bonuses, sign-on offers, home-time guarantees, mileage guarantees, dedicated lanes, or benefits not listed.
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

    if content_type == "social_posts":
        return base + """
Social posts requirements:
- Start with "# Social Posts".
- Write exactly 3 posts.
- Use headings like "Post 1 - Weather & Route Awareness".
- Keep each post practical and realistic.
- Include one safety/operations post, one paperwork/detention/customer-delay post, and one recruiting/reality-check post.
- Mention the company name naturally.
- Include contact info only where it fits.
- Do not invent pay, guarantees, bonuses, lanes, benefits, or policies.
- Avoid hype language like "best", "guaranteed", "unbeatable", or "top paying".
"""

    if content_type == "recruiting_posts":
        return base + """
Recruiting posts requirements:
- Start with "# Recruiting Posts".
- Write exactly 5 recruiting posts.
- Use headings like "Post 1 - CDL-A Regional Opportunity".
- Keep the tone honest, grounded, and driver-facing.
- Sell the real operating fit without sounding like fake mega-carrier marketing.
- Mention equipment, region, lane realities, driver expectations, and communication style.
- Include the provided contact info or website in each post.
- Do not invent pay numbers, bonuses, guaranteed home time, guaranteed miles, dedicated routes, benefits, or policies.
- Do not say "apply today for top pay" or anything similar.
- Avoid hype language like "best", "guaranteed", "unbeatable", or "top paying".
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
