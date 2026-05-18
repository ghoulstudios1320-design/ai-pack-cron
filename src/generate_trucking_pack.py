import json
import re
import unicodedata

from pathlib import Path
from datetime import datetime

from src.openai_utils import generate_text

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)

from reportlab.lib.styles import getSampleStyleSheet


CLIENTS_DIR = Path("clients")
week_label = datetime.now().strftime("%Y-W%U")


def as_list_text(items):
    if isinstance(items, list):
        return ", ".join(items)
    return str(items)


# ==========================================
# REMOVE EMOJIS
# ==========================================

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


# ==========================================
# CLEAN COMMON ISSUES
# ==========================================

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
        "Tri-Cities": "Tri-Cities",
        "I-5": "I-5",
        "I-84": "I-84",
        "I-90": "I-90",
        "II-90": "I-90",
        "Portland ↔ Seattle": "Portland to/from Seattle",
        "Seattle ↔ Portland": "Seattle to/from Portland",
        "↔": "to/from",
        "→": "to",
        "⇄": "to/from",
        "—": "-",
        "–": "-",
        "•": "-",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = remove_emojis(text)

    return text.strip()


# ==========================================
# CLEAN PDF TEXT
# ==========================================

def clean_pdf_text(text):

    text = unicodedata.normalize("NFKD", text)

    text = clean_common_typos(text)

    replacements = {
        "\u2011": "-",  # nonbreaking hyphen
        "\u2010": "-",  # hyphen
        "\u00ad": "-",  # soft hyphen
        "\u25a0": "-",  # black square
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


# ==========================================
# STRIP WEIRD HEADERS
# ==========================================

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


# ==========================================
# GENERATE PACK
# ==========================================

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
    primary_states = as_list_text(client.get("primary_states", []))

    # ==========================================
    # PROMPTS
    # ==========================================

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

    # ==========================================
    # CLEANUP
    # ==========================================

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

    # ==========================================
    # FULL PACK
    # ==========================================

    full_pack = f"""
# Weekly Fleet Recruiting & Communication Pack

## Client
{company_name}

## Fleet Size
{client.get("fleet_size")}

## Region
{client.get("region")}

## Equipment
{client.get("equipment")}

## Hiring For
{client.get("hiring_for")}

## Week
{week_label}

---

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

    files = {
        "recruiting_posts.md": recruiting_posts,
        "social_posts.md": social_posts,
        "safety_reminders.md": safety_reminders,
        "company_update.md": company_update,
        "freight_digest.md": freight_digest,
        "full_pack.md": full_pack,
    }

    # ==========================================
    # WRITE FILES
    # ==========================================

    for filename, content in files.items():

        with open(output_dir / filename, "w") as f:
            f.write(content)

    # ==========================================
    # PDF GENERATION
    # ==========================================

    pdf_path = output_dir / "full_pack.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    story = []

    sections = full_pack.split("\n---\n")

    for section in sections:

        block = []

        for line in section.splitlines():

            line = line.strip()

            if not line:
                block.append(Spacer(1, 8))
                continue

            if line.startswith("# "):

                block.append(
                    Paragraph(
                        line.replace("# ", ""),
                        styles["Title"]
                    )
                )

                block.append(Spacer(1, 12))

            elif line.startswith("## "):

                block.append(
                    Paragraph(
                        line.replace("## ", ""),
                        styles["Heading2"]
                    )
                )

                block.append(Spacer(1, 8))

            else:

                block.append(
                    Paragraph(
                        line,
                        styles["BodyText"]
                    )
                )

                block.append(Spacer(1, 6))

        story.append(KeepTogether(block))
        story.append(PageBreak())

    if story:
        story.pop()

    doc.build(story)

    print(f"Pack generated successfully: {output_dir}")
    print(f"PDF generated: {pdf_path}")


# ==========================================
# MAIN
# ==========================================

def main():

    client_files = sorted(CLIENTS_DIR.glob("*.json"))

    if not client_files:
        raise FileNotFoundError(
            "No client JSON files found in clients/"
        )

    print(f"Found {len(client_files)} client profile(s).")

    for client_path in client_files:
        generate_pack_for_client(client_path)

    print("\nAll client packs generated successfully.")


if __name__ == "__main__":
    main()
