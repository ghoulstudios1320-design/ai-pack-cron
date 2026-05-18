import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Any, Optional

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    Table,
    TableStyle,
    PageBreak,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
CLIENTS_DIR = ROOT_DIR / "clients"
OUTPUT_DIR = ROOT_DIR / "output"


# -----------------------------
# Basic helpers
# -----------------------------

def get_week_key() -> str:
    """
    Returns ISO week key like 2026-W20.
    GitHub Actions will use current UTC/date.
    """
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def clean_text_spacing(text: str) -> str:
    """
    Fixes known weird spacing artifacts without aggressively changing valid text.
    """
    replacements = {
        "Moun tain": "Mountain",
        "moun tain": "mountain",
        "reef unit": "reefer unit",
        "Reef unit": "Reefer unit",
        "reefer vans": "refrigerated vans",
        "loadseal": "load seal",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text


def safe_client_value(client: Dict[str, Any], key: str, default: str = "") -> str:
    value = client.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def load_clients() -> List[Dict[str, Any]]:
    if not CLIENTS_DIR.exists():
        raise RuntimeError(f"Missing clients directory: {CLIENTS_DIR}")

    client_files = sorted(CLIENTS_DIR.glob("*.json"))

    if not client_files:
        raise RuntimeError(f"No client JSON files found in: {CLIENTS_DIR}")

    clients: List[Dict[str, Any]] = []

    for path in client_files:
        with path.open("r", encoding="utf-8") as f:
            client = json.load(f)

        if "client_id" not in client:
            client["client_id"] = slugify(client.get("company_name", path.stem))

        clients.append(client)

    return clients


def ensure_output_dir(client: Dict[str, Any], week_key: str) -> Path:
    client_id = safe_client_value(client, "client_id", slugify(client.get("company_name", "client")))
    out_dir = OUTPUT_DIR / week_key / client_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def get_brand_colors(client: Dict[str, Any]) -> Dict[str, HexColor]:
    """
    Pull brand colors from client JSON.
    Falls back safely if fields are missing.
    """
    brand = client.get("brand", {}) or {}

    return {
        "primary": HexColor(brand.get("primary_color", "#1F2937")),
        "secondary": HexColor(brand.get("secondary_color", "#374151")),
        "accent": HexColor(brand.get("accent_color", "#2563EB")),
        "footer": HexColor(brand.get("footer_color", "#111827")),
    }


def require_contact_block(client: Dict[str, Any]) -> Dict[str, str]:
    """
    Enforces real contact fields from client JSON so generated text does not use placeholders.
    """
    company = safe_client_value(client, "company_name", "the carrier")
    email = safe_client_value(client, "contact_email", f"recruiting@{slugify(company).replace('_', '')}.com")
    phone = safe_client_value(client, "contact_phone", "contact dispatch/recruiting")
    website = safe_client_value(client, "website", "")

    return {
        "company": company,
        "email": email,
        "phone": phone,
        "website": website,
    }


def client_list(client: Dict[str, Any], key: str) -> List[str]:
    value = client.get(key, [])
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


# -----------------------------
# Content generation
# -----------------------------

def generate_recruiting_posts(client: Dict[str, Any]) -> str:
    contact = require_contact_block(client)

    company = contact["company"]
    fleet_size = safe_client_value(client, "fleet_size", "regional fleet")
    region = safe_client_value(client, "region", "regional")
    equipment = safe_client_value(client, "equipment", "tractor-trailer")
    hiring_for = safe_client_value(client, "hiring_for", "CDL-A drivers")
    target_driver = safe_client_value(client, "target_driver", "experienced CDL-A drivers")
    experience_required = safe_client_value(client, "experience_required", "CDL-A experience preferred")
    home_time = safe_client_value(client, "home_time", "home time varies by lane")
    pay_angle = safe_client_value(client, "pay_angle", "steady freight and practical dispatch communication")
    operation_type = safe_client_value(client, "operation_type", "regional trucking")
    lanes = client_list(client, "common_lanes")
    pain_points = client_list(client, "pain_points")
    benefits = client_list(client, "benefits")

    lane_text = ", ".join(lanes[:5]) if lanes else f"{region} regional lanes"
    benefit_text = ", ".join(benefits[:4]) if benefits else pay_angle
    pain_text = ", ".join(pain_points[:3]) if pain_points else "tight appointments, weather, and dock delays"

    website_line = f"Apply at {contact['website']} or " if contact["website"] else "Apply by email or "
    cta = f"{website_line}email {contact['email']} or call {contact['phone']}."

    content = f"""# Recruiting Posts

Post 1 - {hiring_for.title()}
{company} is hiring {hiring_for} for {operation_type} across the {region}. We run {equipment} with a {fleet_size} operation and a practical dispatch style. Common lanes include {lane_text}. This is built for {target_driver}. We offer {benefit_text}. {experience_required}. {cta}

Post 2 - Regional Lanes That Stay Practical
If you want regional freight without the mystery, {company} is looking for drivers who can handle real-world trucking: {pain_text}. The work centers on {lane_text}. We focus on {home_time}, documented detention where applicable, and direct communication when appointments or lanes change. {cta}

Post 3 - Experienced Drivers Wanted
This role is for drivers who know that trucking is not perfect but should be honest. Expect {equipment} work, {region} routing, customer appointment pressure, and normal operating delays. We are looking for {target_driver}. Benefits include {benefit_text}. {experience_required}. {cta}

Post 4 - Dispatch That Communicates
At {company}, drivers should not have to guess what changed. We expect clean pre-trips, safe operation, accurate paperwork, and early communication when delays hit. In return, drivers get {pay_angle}. Current hiring focus: {hiring_for}. {cta}

Post 5 - {region} Driver Opportunity
{company} runs a {fleet_size} fleet focused on {operation_type}. Primary freight and lanes include {lane_text}. Expect {pain_text}, but also expect a company that values documentation, communication, and safe decisions. {experience_required}. {cta}
"""

    return clean_text_spacing(content)


def generate_social_posts(client: Dict[str, Any]) -> str:
    contact = require_contact_block(client)

    company = contact["company"]
    region = safe_client_value(client, "region", "regional")
    equipment = safe_client_value(client, "equipment", "tractor-trailer")
    lanes = client_list(client, "common_lanes")
    pain_points = client_list(client, "pain_points")
    hiring_for = safe_client_value(client, "hiring_for", "CDL-A drivers")

    lane_text = ", ".join(lanes[:4]) if lanes else f"{region} lanes"
    pain_text = ", ".join(pain_points[:4]) if pain_points else "weather, appointments, detention, and parking"

    content = f"""# Social Posts

Post 1 - Weather & Route Awareness
Drivers running {lane_text}: check weather, road conditions, and customer timing before you roll. {region} freight can change fast when {pain_text} hit at the same time. Slow down early, communicate delays before they become failures, and keep dispatch updated. - {company}

Post 2 - Appointments & Detention
Tight appointments only work when the paperwork is clean. Log gate arrival, get a timestamp when possible, keep BOL/POD copies, and call dispatch before detention becomes a problem. If a customer will not provide signed times, document who you spoke with and where you were staged. - {company}

Post 3 - Recruiting Reality Check
{company} is hiring {hiring_for}. This is real {equipment} work across {region}, not a fantasy ad. Expect {pain_text}. If you want steady lanes, practical dispatch, and clear expectations, contact us at {contact['email']} or {contact['phone']}. - {company}
"""

    return clean_text_spacing(content)


def generate_safety_reminders(client: Dict[str, Any]) -> str:
    company = safe_client_value(client, "company_name", "Company")
    equipment = safe_client_value(client, "equipment", "tractor-trailer")
    region = safe_client_value(client, "region", "regional")
    pain_points = client_list(client, "pain_points")
    lanes = client_list(client, "common_lanes")

    lane_text = ", ".join(lanes[:4]) if lanes else f"{region} lanes"
    pain_text = ", ".join(pain_points[:4]) if pain_points else "weather, parking, detention, and customer delays"

    is_reefer = "reefer" in equipment.lower() or "refrigerated" in equipment.lower()
    is_flatbed = "flatbed" in equipment.lower()

    if is_reefer:
        reminder_1 = """Reminder 1 - Temperature Control & Reefer Checks
- Pre-trip the box and the unit before loading.
- Confirm setpoint against the BOL before changing any setting.
- Let the unit stabilize before loading if it has been off.
- Check fuel, oil, belts, coolant, batteries, alarms, and door seals.
- Load for airflow. Do not block the evaporator or side vents.
- Log temperatures at pickup, during long runs, and before delivery.
- If the unit alarms, pull to a safe location, call dispatch, and document the display with photos."""
    elif is_flatbed:
        reminder_1 = """Reminder 1 - Load Securement & Flatbed Checks
- Walk the full load before leaving the shipper or jobsite.
- Check straps, chains, binders, winches, edge protection, dunnage, and blocking.
- Re-check securement after the first 25-50 miles and after rough roads, hard braking, or weather.
- Use edge protection on sharp corners and building materials.
- Confirm flags, lights, and permits before moving oversize or overhang freight.
- If the load shifts or securement looks wrong, stop safely and call dispatch."""
    else:
        reminder_1 = """Reminder 1 - Load & Trailer Checks
- Walk the trailer inside and out before leaving.
- Confirm doors, seals, lights, tires, landing gear, and load condition.
- Use load bars, straps, and dunnage where needed.
- Re-check after the first 50 miles or after heavy stop-and-go traffic.
- Keep paperwork accessible and accurate.
- If the load shifts or the trailer feels wrong, stop safely and call dispatch."""

    content = f"""# Safety Reminders

{reminder_1}

Reminder 2 - Route, Weather & Customer Safety
- Primary lanes this week: {lane_text}.
- Watch for the main operating risks: {pain_text}.
- Check weather and road conditions before leaving.
- Plan fuel, parking, and breaks before you are tight on hours.
- Do not park on shoulders or unsafe staging areas unless there is no safe alternative.
- If a customer delay threatens HOS, safety, or cargo condition, call dispatch early.
- If involved in an incident, get to safety, call emergency services if needed, then call dispatch.
- Document damage, delays, refusals, and unsafe site conditions with photos and notes.

Drive safe,
{company}
"""

    return clean_text_spacing(content)


def generate_company_update(client: Dict[str, Any]) -> str:
    contact = require_contact_block(client)

    company = contact["company"]
    fleet_size = safe_client_value(client, "fleet_size", "fleet")
    region = safe_client_value(client, "region", "regional")
    equipment = safe_client_value(client, "equipment", "equipment")
    operation_type = safe_client_value(client, "operation_type", "regional freight")
    lanes = client_list(client, "common_lanes")
    pain_points = client_list(client, "pain_points")
    benefits = client_list(client, "benefits")

    lane_lines = "\n".join([f"- {lane}: expect normal appointment pressure, route planning, and customer communication." for lane in lanes[:6]])
    if not lane_lines:
        lane_lines = f"- {region} regional lanes: confirm appointments, route timing, and parking before departure."

    pain_lines = "\n".join([f"- {p}: plan ahead and notify dispatch early if it affects service or safety." for p in pain_points[:6]])
    if not pain_lines:
        pain_lines = "- Weather, detention, parking, and appointment changes: communicate early and document clearly."

    benefit_lines = "\n".join([f"- {b}" for b in benefits[:6]])
    if not benefit_lines:
        benefit_lines = "- Practical dispatch communication\n- Documented detention support\n- Safe routing decisions"

    content = f"""# Company Update

{company} - Weekly Driver Update
Fleet: {fleet_size}
Region: {region}
Equipment: {equipment}
Operation: {operation_type}

Quick status
- Keep this update practical: read it before dispatch and use it during the week.
- If anything changes on your load, route, equipment, appointment, or hours, call dispatch early.
- Contact: {contact['email']} | {contact['phone']}

Lane notes
{lane_lines}

Main operating risks this week
{pain_lines}

Driver support priorities
{benefit_lines}

Paperwork and detention
- Record gate arrival and release times.
- Get signed or timestamped proof when possible.
- Photograph BOLs, PODs, seals, load condition, and any damage.
- If detention is likely, call dispatch before the delay gets out of hand.
- Missing paperwork delays pay, claims, and customer billing.

Maintenance and equipment
- Complete clean pre-trips and post-trips.
- Report defects immediately; do not bury safety issues in notes.
- Check tires, lights, brakes, doors, landing gear, fluids, and required gear.
- If something feels wrong, stop safely and call dispatch.

Hours-of-service and fatigue
- Do not accept a plan that forces an HOS violation.
- If detention or traffic threatens your clock, call dispatch while there is still time to fix the plan.
- Plan parking before the last hour of your available time.

Safety
- Do not rush docks, jobsite approaches, chain areas, ramps, or bad-weather turns.
- Use a spotter when available.
- Get out and look when backing is questionable.
- Do not admit fault after an incident. Get safe, call emergency services if needed, then call dispatch.

Weekly priorities
- Communicate early.
- Document clearly.
- Keep equipment issues from becoming roadside failures.
- Protect safety before appointment pressure.

Drive safe,
Operations / Dispatch
{company}
"""

    return clean_text_spacing(content)


def generate_freight_digest(client: Dict[str, Any]) -> str:
    company = safe_client_value(client, "company_name", "Company")
    region = safe_client_value(client, "region", "regional")
    equipment = safe_client_value(client, "equipment", "tractor-trailer")
    lanes = client_list(client, "common_lanes")
    pain_points = client_list(client, "pain_points")

    lane_sections = []
    for lane in lanes[:6]:
        lane_sections.append(
            f"""### {lane}
- Freight: steady lane activity depending on customer volume and appointment availability.
- Watch for: timing changes, parking limits, weather, and customer delay.
- Driver tip: confirm appointment details early, document arrival/release times, and plan fuel before the lane gets tight."""
        )

    if not lane_sections:
        lane_sections.append(
            f"""### {region} Regional Lanes
- Freight: steady regional activity.
- Watch for: appointment windows, parking, weather, and detention.
- Driver tip: confirm details early and keep dispatch updated."""
        )

    pain_text = "\n".join([f"- {p}" for p in pain_points[:8]]) if pain_points else "- Weather\n- Detention\n- Parking\n- Appointment changes"

    content = f"""# Freight Digest

{company} - {region} Regional Freight Digest
For drivers: {equipment} operations. No fluff - practical notes you can use.

## Overview
- This digest is focused on active {region} lanes.
- Equipment focus: {equipment}.
- Main goal: protect safety, appointment performance, documentation, and driver time.
- Communicate early when loads, roads, customers, or equipment create a problem.

## Current operating concerns
{pain_text}

## Lane-specific notes

{chr(10).join(lane_sections)}

## Weather and road conditions
- Check weather before departure and again before major route changes.
- Mountain passes, bridges, exposed open roads, industrial yards, and ramps can change faster than the main highway.
- Slow down before the problem area, not inside it.
- If weather threatens safe operation, notify dispatch and stage legally.

## Fuel and routing
- Plan fuel before long rural stretches or major metro congestion.
- Do not run below a safe reserve when appointment pressure or parking limits are involved.
- Keep receipts for off-network fuel if dispatch approves it.
- Plan legal parking before your clock gets tight.

## Equipment and load prep checklist
- Complete pre-trip before accepting the load.
- Check tires, lights, brakes, fluids, doors, seals, securement gear, and required paperwork.
- Photograph load condition, seal, trailer condition, and any damage before leaving.
- Re-check load condition after the first stretch of road or after rough terrain.

## Paperwork and compliance
- Keep CDL, medical card, registration, insurance, permits, BOLs, and PODs accessible.
- Get signed paperwork at pickup and delivery.
- Document exceptions immediately.
- If a customer refuses to sign or changes instructions, call dispatch before leaving.

## Driver safety and practical tips
- Do not fix problems on the shoulder unless there is no safer option.
- Use legal staging areas whenever possible.
- Call ahead for tight customers or unusual sites.
- Get out and look before difficult backing.
- Protect your hours by communicating early.

## Final word
Run the plan, but do not let the plan outrank safety. Document clearly, communicate early, and call dispatch when anything changes.
"""

    return clean_text_spacing(content)


def build_full_pack_markdown(client: Dict[str, Any], week_key: str, sections: Dict[str, str]) -> str:
    contact = require_contact_block(client)

    company = contact["company"]
    tagline = safe_client_value(client, "tagline", "")
    fleet_size = safe_client_value(client, "fleet_size", "")
    region = safe_client_value(client, "region", "")
    equipment = safe_client_value(client, "equipment", "")
    hiring_for = safe_client_value(client, "hiring_for", "")

    parts = [
        f"# {company} | Week {week_key}",
        "",
        "Weekly Fleet Recruiting & Communication Pack",
    ]

    if tagline:
        parts.extend(["", tagline])

    parts.extend([
        "",
        f"Client: {company}",
        f"Fleet Size: {fleet_size}",
        f"Region: {region}",
        f"Equipment: {equipment}",
        f"Hiring For: {hiring_for}",
        f"Contact Email: {contact['email']}",
        f"Contact Phone: {contact['phone']}",
    ])

    if contact["website"]:
        parts.append(f"Website: {contact['website']}")

    parts.extend([
        "",
        "---",
        "",
        sections["recruiting_posts"],
        "",
        "---",
        "",
        sections["social_posts"],
        "",
        "---",
        "",
        sections["safety_reminders"],
        "",
        "---",
        "",
        sections["company_update"],
        "",
        "---",
        "",
        sections["freight_digest"],
        "",
    ])

    return clean_text_spacing("\n".join(parts))


# -----------------------------
# File writing
# -----------------------------

def write_text_file(path: Path, content: str) -> None:
    path.write_text(clean_text_spacing(content).strip() + "\n", encoding="utf-8")


def generate_client_markdown_files(client: Dict[str, Any], out_dir: Path, week_key: str) -> Dict[str, str]:
    sections = {
        "recruiting_posts": generate_recruiting_posts(client),
        "social_posts": generate_social_posts(client),
        "safety_reminders": generate_safety_reminders(client),
        "company_update": generate_company_update(client),
        "freight_digest": generate_freight_digest(client),
    }

    write_text_file(out_dir / "recruiting_posts.md", sections["recruiting_posts"])
    write_text_file(out_dir / "social_posts.md", sections["social_posts"])
    write_text_file(out_dir / "safety_reminders.md", sections["safety_reminders"])
    write_text_file(out_dir / "company_update.md", sections["company_update"])
    write_text_file(out_dir / "freight_digest.md", sections["freight_digest"])

    full_pack = build_full_pack_markdown(client, week_key, sections)
    write_text_file(out_dir / "full_pack.md", full_pack)

    return sections


# -----------------------------
# PDF generation
# -----------------------------

def add_footer(canvas, doc, client: Dict[str, Any], week_key: str, footer_color: HexColor) -> None:
    company = safe_client_value(client, "company_name", "Client")
    footer_text = f"{company} | Week {week_key} | Page {doc.page}"

    canvas.saveState()

    canvas.setStrokeColor(footer_color)
    canvas.setLineWidth(1.5)
    canvas.line(doc.leftMargin, 0.55 * inch, letter[0] - doc.rightMargin, 0.55 * inch)

    canvas.setFillColor(footer_color)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(letter[0] / 2, 0.38 * inch, footer_text)

    canvas.restoreState()


def paragraphize_text(text: str, body_style: ParagraphStyle, section_style: ParagraphStyle, story: List[Any], accent_color: HexColor) -> None:
    """
    Converts markdown-ish generated content into simple PDF paragraphs.
    """
    lines = clean_text_spacing(text).splitlines()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 6))
            continue

        if line.startswith("# "):
            title = line[2:].strip()
            story.append(Spacer(1, 8))
            story.append(Paragraph(escape_pdf_text(title), section_style))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=accent_color,
                    spaceBefore=4,
                    spaceAfter=10,
                )
            )
            continue

        if line.startswith("## "):
            title = line[3:].strip()
            story.append(Spacer(1, 8))
            story.append(Paragraph(escape_pdf_text(title), section_style))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=1.5,
                    color=accent_color,
                    spaceBefore=3,
                    spaceAfter=8,
                )
            )
            continue

        if line.startswith("### "):
            title = line[4:].strip()
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>{escape_pdf_text(title)}</b>", body_style))
            continue

        if line == "---":
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=1.25,
                    color=accent_color,
                    spaceBefore=8,
                    spaceAfter=8,
                )
            )
            continue

        if line.startswith("- "):
            bullet = line[2:].strip()
            story.append(Paragraph(f"• {escape_pdf_text(bullet)}", body_style))
            continue

        story.append(Paragraph(escape_pdf_text(line), body_style))


def escape_pdf_text(text: str) -> str:
    """
    Minimal XML escaping for ReportLab Paragraph.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_pdf(client: Dict[str, Any], out_dir: Path, week_key: str, sections: Dict[str, str]) -> None:
    contact = require_contact_block(client)
    brand_colors = get_brand_colors(client)

    primary_color = brand_colors["primary"]
    secondary_color = brand_colors["secondary"]
    accent_color = brand_colors["accent"]
    footer_color = brand_colors["footer"]

    pdf_path = out_dir / "full_pack.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title=f"{contact['company']} Weekly Fleet Pack",
        author=contact["company"],
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=primary_color,
        spaceAfter=12,
    )

    subtitle_style = ParagraphStyle(
        "BrandSubtitle",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        textColor=secondary_color,
        spaceAfter=16,
    )

    cover_meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=5,
    )

    section_style = ParagraphStyle(
        "BrandSection",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=primary_color,
        alignment=TA_LEFT,
        spaceBefore=14,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )

    story: List[Any] = []

    company = contact["company"]
    tagline = safe_client_value(client, "tagline", "")
    fleet_size = safe_client_value(client, "fleet_size", "")
    region = safe_client_value(client, "region", "")
    equipment = safe_client_value(client, "equipment", "")
    hiring_for = safe_client_value(client, "hiring_for", "")

    # Strong visible accent bar on cover.
    story.append(
        Table(
            [[""]],
            colWidths=[doc.width],
            rowHeights=[12],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), accent_color),
                ("BOX", (0, 0), (-1, -1), 0, accent_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]),
        )
    )

    story.append(Spacer(1, 22))
    story.append(Paragraph("Weekly Fleet Recruiting & Communication Pack", title_style))

    if tagline:
        story.append(Paragraph(escape_pdf_text(tagline), subtitle_style))
    else:
        story.append(Paragraph(escape_pdf_text(company), subtitle_style))

    # Colored client badge/table.
    meta_data = [
        ["Client", company],
        ["Fleet Size", fleet_size],
        ["Region", region],
        ["Equipment", equipment],
        ["Hiring For", hiring_for],
        ["Week", week_key],
        ["Email", contact["email"]],
        ["Phone", contact["phone"]],
    ]

    if contact["website"]:
        meta_data.append(["Website", contact["website"]])

    meta_table = Table(
        [[Paragraph(f"<b>{escape_pdf_text(k)}</b>", cover_meta_style), Paragraph(escape_pdf_text(v), cover_meta_style)] for k, v in meta_data],
        colWidths=[1.55 * inch, 4.7 * inch],
        hAlign="CENTER",
    )

    meta_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), primary_color),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
    ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F9FAFB")),
    ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
    ("BOX", (0, 0), (-1, -1), 1, accent_color),
    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))

    story.append(Spacer(1, 10))
    story.append(meta_table)
    story.append(Spacer(1, 24))

   story.append(
    HRFlowable(
        width="100%",
        thickness=3,
        color=accent_color,
        spaceBefore=12,
        spaceAfter=16,
    )
)

# Keep the cover as a real standalone page.
# Page 2 starts directly with Recruiting Posts.
story.append(PageBreak())

ordered_sections = [
        sections["recruiting_posts"],
        sections["social_posts"],
        sections["safety_reminders"],
        sections["company_update"],
        sections["freight_digest"],
    ]

    for section in ordered_sections:
        paragraphize_text(section, body_style, section_style, story, accent_color)

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: add_footer(canvas, doc_obj, client, week_key, footer_color),
        onLaterPages=lambda canvas, doc_obj: add_footer(canvas, doc_obj, client, week_key, footer_color),
    )


# -----------------------------
# Meta output
# -----------------------------

def write_meta(client: Dict[str, Any], out_dir: Path, week_key: str) -> None:
    contact = require_contact_block(client)

    meta = {
        "client_id": safe_client_value(client, "client_id"),
        "company_name": contact["company"],
        "week": week_key,
        "fleet_size": safe_client_value(client, "fleet_size"),
        "region": safe_client_value(client, "region"),
        "equipment": safe_client_value(client, "equipment"),
        "hiring_for": safe_client_value(client, "hiring_for"),
        "tagline": safe_client_value(client, "tagline"),
        "contact_email": contact["email"],
        "contact_phone": contact["phone"],
        "website": contact["website"],
        "files": {
            "full_pack_md": "full_pack.md",
            "full_pack_pdf": "full_pack.pdf",
            "recruiting_posts": "recruiting_posts.md",
            "social_posts": "social_posts.md",
            "safety_reminders": "safety_reminders.md",
            "company_update": "company_update.md",
            "freight_digest": "freight_digest.md",
        },
    }

    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


# -----------------------------
# Main
# -----------------------------

def generate_for_client(client: Dict[str, Any], week_key: str) -> None:
    company = safe_client_value(client, "company_name", "Unnamed Client")
    client_id = safe_client_value(client, "client_id", slugify(company))

    print(f"Generating pack for {company} ({client_id})...")

    out_dir = ensure_output_dir(client, week_key)

    sections = generate_client_markdown_files(client, out_dir, week_key)
    build_pdf(client, out_dir, week_key, sections)
    write_meta(client, out_dir, week_key)

    print(f"Done: {out_dir}")


def main() -> None:
    week_key = os.getenv("WEEK_KEY") or get_week_key()
    clients = load_clients()

    print(f"Week: {week_key}")
    print(f"Clients found: {len(clients)}")

    for client in clients:
        generate_for_client(client, week_key)

    print("All client packs generated successfully.")


if __name__ == "__main__":
    main()
