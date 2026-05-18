import json
import re
import unicodedata

from pathlib import Path
from datetime import datetime
from xml.sax.saxutils import escape

from src.openai_utils import generate_text

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)

from reportlab.platypus.flowables import PageBreak

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)


CLIENTS_DIR = Path("clients")
week_label = datetime.now().strftime("%Y-W%U")


def as_list_text(items):
    if isinstance(items, list):
        return ", ".join(items)

    return str(items)


def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )

    return emoji_pattern.sub("", text)


def clean_common_typos(text):
    replacements = {
        "CDL–A": "CDL-A",
        "CDL—A": "CDL-A",
        "dry–van": "dry-van",
        "pre–trip": "pre-trip",
        "post–trip": "post-trip",
        "high–wind": "high-wind",
        "small–fleet": "small-fleet",
        "time–stamped": "time-stamped",
        "check–ins": "check-ins",
        "II-90": "I-90",

        "↔": " to/from ",
        "→": " to ",
        "⇄": " to/from ",

        "—": "-",
        "–": "-",
        "•": "-",

        "Portlandto/fromSeattle": "Portland to/from Seattle",
        "Portlandto/fromNorCal": "Portland to/from Northern California",
        "Portlandto/fromNorthern California": "Portland to/from Northern California",
        "Seattleto/fromPortland": "Seattle to/from Portland",

        "fast-early": "fast - early",
        "stops-don't": "stops - don't",
        "lanes-have": "lanes - have",
        "produce lanes-have": "produce lanes - have",
        "fuel stops-don't": "fuel stops - don't",
        "routes-have": "routes - have",
        "weather-check": "weather - check",
        "timing-call": "timing - call",

        "load- handling": "load handling",
        "load - handling": "load handling",
        "fuel-reefer": "fuel - reefer",
        "conditions-reduce": "conditions - reduce",
        "storage-if": "storage - if",
        "freight-Portland": "freight - Portland",
        "season-extra": "season - extra",
        "common-same": "common - same",
        "detention-which": "detention - which",
        "reefing experience": "reefer experience",

        "pretrip": "pre-trip",
        "posttrip": "post-trip",
        "pre - trip": "pre-trip",
        "post - trip": "post-trip",
        "pre - call": "pre-call",
        "on - call": "on-call",
        "ops - trailers": "ops-trailers",
        "time - sensitive": "time-sensitive",
        "cold - storage": "cold-storage",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = re.sub(r"([a-zA-Z])to/from([A-Z])", r"\1 to/from \2", text)

    text = re.sub(
        r"([a-z])-(if|when|which|but|expect|bring|call|dont|don't|early|have)",
        r"\1 - \2",
        text,
    )

    safe_hyphens = {
        "pre - trip": "pre-trip",
        "post - trip": "post-trip",
        "time - sensitive": "time-sensitive",
        "cold - storage": "cold-storage",
        "high - wind": "high-wind",
        "drop - and - hook": "drop-and-hook",
        "on - call": "on-call",
        "pre - call": "pre-call",
    }

    for bad, good in safe_hyphens.items():
        text = text.replace(bad, good)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    text = remove_emojis(text)

    return text.strip()


def clean_pdf_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = clean_common_typos(text)

    replacements = {
        "\u2011": "-",
        "\u2010": "-",
        "\u00ad": "-",
        "\u25a0": "-",
        "■": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "°": " degrees ",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = text.encode("ascii", "ignore").decode("ascii")

    return text.strip()


def strip_junk_headers(text):
    junk = [
        "Section:",
        "Content:",
        "Social Posts",
        "Freight Digest",
        "Company Update",
    ]

    lines = []

    for line in text.splitlines():
        stripped = line.strip()

        if stripped in junk:
            continue

        lines.append(line)

    return "\n".join(lines)


def remove_duplicate_cover_content(text):
    lines = text.splitlines()
    cleaned = []
    skip_next_value = False

    duplicate_headers = {
        "# Weekly Fleet Recruiting & Communication Pack",
        "## Client",
        "## Fleet Size",
        "## Region",
        "## Equipment",
        "## Hiring For",
        "## Week",
    }

    for line in lines:
        stripped = line.strip()

        if skip_next_value:
            skip_next_value = False
            continue

        if stripped in duplicate_headers:
            skip_next_value = stripped.startswith("## ")
            continue

        cleaned.append(line)

    cleaned_text = "\n".join(cleaned)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    return cleaned_text


def paragraph_text(line):
    return escape(clean_pdf_text(line))


def safe_hex_color(value, fallback):
    if not value:
        return fallback

    value = str(value).strip()

    if not value.startswith("#"):
        return fallback

    if len(value) not in [4, 7]:
        return fallback

    return value


def generate_pack_for_client(client_path):
    with open(client_path, "r") as f:
        client = json.load(f)

    client_id = client["client_id"]
    company_name = client["company_name"]

    output_dir = Path(f"output/{week_label}/{client_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    common_lanes = as_list_text(client.get("common_lanes", []))
    pain_points = as_list_text(client.get("pain_points", []))
    benefits = as_list_text(client.get("benefits", []))

    brand_color = safe_hex_color(
        client.get("brand_color"),
        "#1f2937",
    )

    accent_color = safe_hex_color(
        client.get("accent_color"),
        "#9ca3af",
    )

    tagline = client.get("tagline", "")

    base_rules = """
- Write for real truck drivers
- No emojis
- No hashtags
- No corporate fluff
- Use practical trucking language
- Keep wording realistic and believable
"""

    recruiting_prompt = f"""
Create 5 realistic recruiting posts.

Company: {company_name}
Fleet Size: {client.get("fleet_size")}
Region: {client.get("region")}
Equipment: {client.get("equipment")}
Operation Type: {client.get("operation_type")}
Hiring For: {client.get("hiring_for")}
Common Lanes: {common_lanes}
Benefits: {benefits}
Pain Points: {pain_points}
Tone: {client.get("tone")}

Requirements:
{base_rules}

- Include realistic call-to-actions
- Mention home time or lanes when appropriate
"""

    social_prompt = f"""
Create 3 realistic trucking social posts.

Company: {company_name}
Equipment: {client.get("equipment")}
Region: {client.get("region")}
Common Lanes: {common_lanes}
Pain Points: {pain_points}

Requirements:
{base_rules}

- Focus on operations, weather, safety, detention, drivers, or dispatch
"""

    safety_prompt = f"""
Create 2 practical trucking safety reminders.

Company: {company_name}
Equipment: {client.get("equipment")}
Region: {client.get("region")}
Common Lanes: {common_lanes}

Requirements:
{base_rules}

- Keep them practical and field-relevant
"""

    company_update_prompt = f"""
Create a weekly trucking company update.

Company: {company_name}
Fleet Size: {client.get("fleet_size")}
Operation Type: {client.get("operation_type")}
Common Lanes: {common_lanes}

Requirements:
{base_rules}

- Write like operations or dispatch talking to drivers
"""

    freight_digest_prompt = f"""
Create a regional freight digest.

Company: {company_name}
Equipment: {client.get("equipment")}
Region: {client.get("region")}
Common Lanes: {common_lanes}

Requirements:
{base_rules}

- Mention weather, freight conditions, fuel, and operational concerns
"""

    print(f"\n=== Generating pack for {company_name} ===")

    recruiting_posts = generate_text(recruiting_prompt)
    social_posts = generate_text(social_prompt)
    safety_reminders = generate_text(safety_prompt)
    company_update = generate_text(company_update_prompt)
    freight_digest = generate_text(freight_digest_prompt)

    sections = [
        recruiting_posts,
        social_posts,
        safety_reminders,
        company_update,
        freight_digest,
    ]

    cleaned_sections = []

    for section in sections:
        section = clean_common_typos(section)
        section = clean_pdf_text(section)
        section = strip_junk_headers(section)
        cleaned_sections.append(section)

    (
        recruiting_posts,
        social_posts,
        safety_reminders,
        company_update,
        freight_digest,
    ) = cleaned_sections

    full_pack = f"""
# Recruiting Posts

{recruiting_posts}

---

# Social Posts

{social_posts}

---

# Safety Reminders

{safety_reminders}

---

# Company Update

{company_update}

---

# Freight Digest

{freight_digest}
"""

    full_pack = clean_pdf_text(full_pack)
    full_pack = remove_duplicate_cover_content(full_pack)

    files = {
        "recruiting_posts.md": recruiting_posts,
        "social_posts.md": social_posts,
        "safety_reminders.md": safety_reminders,
        "company_update.md": company_update,
        "freight_digest.md": freight_digest,
        "full_pack.md": full_pack,
    }

    for filename, content in files.items():
        with open(output_dir / filename, "w") as f:
            f.write(content)

    pdf_path = output_dir / "full_pack.pdf"

    def add_page_number(canvas, doc):
        canvas.saveState()

        footer_text = (
            f"{company_name} | "
            f"Week {week_label} | "
            f"Page {doc.page}"
        )

        canvas.setStrokeColor(colors.HexColor(accent_color))
        canvas.setLineWidth(1)
        canvas.line(45, 32, 567, 32)

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor(brand_color))
        canvas.drawRightString(560, 18, footer_text)

        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=50,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        alignment=1,
        textColor=colors.HexColor(brand_color),
        spaceAfter=14,
    )

    tagline_style = ParagraphStyle(
        "Tagline",
        parent=styles["BodyText"],
        fontSize=11,
        leading=15,
        alignment=1,
        textColor=colors.HexColor(accent_color),
        spaceAfter=20,
    )

    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor(brand_color),
        spaceBefore=20,
        spaceAfter=12,
    )

    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=16,
        spaceAfter=8,
    )

    small_header_style = ParagraphStyle(
        "SmallHeader",
        parent=styles["Heading2"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#374151"),
        spaceBefore=12,
        spaceAfter=6,
        alignment=1,
    )

    story = []

    story.append(Spacer(1, 90))

    story.append(
        Paragraph(
            "Weekly Fleet Recruiting & Communication Pack",
            title_style,
        )
    )

    if tagline:
        story.append(
            Paragraph(
                escape(str(tagline)),
                tagline_style,
            )
        )
    else:
        story.append(Spacer(1, 20))

    story.append(Spacer(1, 16))

    cover_lines = [
        f"<b>Client:</b> {escape(company_name)}",
        f"<b>Fleet Size:</b> {escape(str(client.get('fleet_size')))}",
        f"<b>Region:</b> {escape(str(client.get('region')))}",
        f"<b>Equipment:</b> {escape(str(client.get('equipment')))}",
        f"<b>Hiring For:</b> {escape(str(client.get('hiring_for')))}",
        f"<b>Week:</b> {escape(week_label)}",
    ]

    for line in cover_lines:
        story.append(
            Paragraph(
                line,
                small_header_style,
            )
        )

    story.append(Spacer(1, 36))

    story.append(
        HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor(accent_color),
        )
    )

    story.append(PageBreak())
    story.append(Spacer(1, 20))

    pdf_content = remove_duplicate_cover_content(full_pack)
    sections = pdf_content.split("\n---\n")

    for section in sections:
        section = section.strip()

        if not section:
            continue

        for line in section.splitlines():
            line = line.strip()

            if not line:
                story.append(Spacer(1, 10))
                continue

            if line.startswith("# "):
                story.append(
                    Paragraph(
                        paragraph_text(line.replace("# ", "")),
                        section_style,
                    )
                )

                story.append(
                    HRFlowable(
                        width="100%",
                        thickness=1,
                        color=colors.HexColor(accent_color),
                    )
                )

                story.append(Spacer(1, 12))

            elif line.startswith("## "):
                story.append(
                    Paragraph(
                        paragraph_text(line.replace("## ", "")),
                        small_header_style,
                    )
                )

                story.append(Spacer(1, 6))

            else:
                story.append(
                    Paragraph(
                        paragraph_text(line),
                        body_style,
                    )
                )

        story.append(Spacer(1, 18))

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    print(f"Pack generated successfully: {output_dir}")
    print(f"PDF generated: {pdf_path}")


def main():
    client_files = sorted(CLIENTS_DIR.glob("*.json"))

    if not client_files:
        raise FileNotFoundError("No client JSON files found in clients/")

    print(f"Found {len(client_files)} client profile(s).")

    for client_path in client_files:
        generate_pack_for_client(client_path)

    print("\nAll client packs generated successfully.")


if __name__ == "__main__":
    main()
