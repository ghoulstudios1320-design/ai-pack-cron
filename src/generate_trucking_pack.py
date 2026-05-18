import json
import re
from pathlib import Path
from datetime import datetime

from src.openai_utils import generate_text

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


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
        "CDL-A": "CDL-A",
        "CDL–A": "CDL-A",
        "CDL—A": "CDL-A",
        "dry-van": "dry-van",
        "pre-trip": "pre-trip",
        "post-trip": "post-trip",
        "high-wind": "high-wind",
        "short-term": "short-term",
        "small-fleet": "small-fleet",
        "safety-minded": "safety-minded",
        "securement-focused": "securement-focused",
        "hands-on": "hands-on",
        "time-stamped": "time-stamped",
        "timestamped": "time-stamped",
        "check-ins": "check-ins",
        "I-5": "I-5",
        "I-84": "I-84",
        "I-90": "I-90",
        "II-90": "I-90",
        "CDL/DRIVER": "CDL-A driver",
        "DRIVER record": "driving record",
        "NorCal": "Northern California",
        "ballast of regional lanes": "base of regional lanes",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = remove_emojis(text)
    return text.strip()


def clean_pdf_text(text):
    text = clean_common_typos(text)

    replacements = {
        "—": "-",
        "–": "-",
        "-": "-",
        "→": "to",
        "↔": "to/from",
        "⇄": "to/from",
        "■": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "±": "+/-",
        "°": " degrees ",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text.strip()


def proofread_content(section_name, content):
    prompt = f"""
Proofread and clean the following trucking-company content.

Section:
{section_name}

Content:
{content}

Rules:
- Fix typos and awkward wording
- Remove emojis
- Remove hashtags
- Keep the trucking tone practical and realistic
- Do not add fake statistics
- Do not make it sound corporate
- Keep the original meaning
- Preserve headings and post numbering where possible
- Return only the cleaned content
"""

    cleaned = generate_text(prompt)
    cleaned = clean_common_typos(cleaned)
    return cleaned


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

    recruiting_prompt = f"""
Create 5 realistic recruiting posts for this trucking company.

Company:
{company_name}

Fleet Size:
{client.get("fleet_size")}

Home Base:
{client.get("home_base")}

Region:
{client.get("region")}

Primary States:
{primary_states}

Equipment:
{client.get("equipment")}

Operation Type:
{client.get("operation_type")}

Hiring For:
{client.get("hiring_for")}

Experience Required:
{client.get("experience_required")}

Home Time:
{client.get("home_time")}

Pay/Work Angle:
{client.get("pay_angle")}

Benefits:
{benefits}

Common Lanes:
{common_lanes}

Pain Points:
{pain_points}

Target Driver:
{client.get("target_driver")}

Contact Email:
{client.get("contact_email")}

Contact Phone:
{client.get("contact_phone")}

Tone:
{client.get("tone")}

Requirements:
- Write for real truck drivers, not office executives
- Avoid corporate fluff
- Do not use emojis
- Do not use hashtags
- Make each post distinct
- Include a realistic call to action
"""

    social_prompt = f"""
Create 3 realistic social media posts for this trucking company.

Company:
{company_name}

Region:
{client.get("region")}

Home Base:
{client.get("home_base")}

Equipment:
{client.get("equipment")}

Operation Type:
{client.get("operation_type")}

Common Lanes:
{common_lanes}

Pain Points:
{pain_points}

Tone:
{client.get("tone")}

Requirements:
- Make the posts sound like they came from a small trucking company
- Professional but human
- Avoid corporate fluff
- Do not use emojis
- Do not use hashtags
- Focus on operational reality, drivers, safety, equipment, lanes, weather, or communication
"""

    safety_prompt = f"""
Create 2 practical trucking safety reminders for this company.

Company:
{company_name}

Region:
{client.get("region")}

Primary States:
{primary_states}

Equipment:
{client.get("equipment")}

Operation Type:
{client.get("operation_type")}

Common Lanes:
{common_lanes}

Pain Points:
{pain_points}

Tone:
{client.get("tone")}

Requirements:
- Practical
- Specific to the equipment and region
- Avoid generic safety slogans
- Avoid corporate language
- Do not use emojis
- Do not use hashtags
"""

    company_update_prompt = f"""
Write a short weekly company update/newsletter for this trucking company.

Company:
{company_name}

Fleet Size:
{client.get("fleet_size")}

Region:
{client.get("region")}

Home Base:
{client.get("home_base")}

Equipment:
{client.get("equipment")}

Operation Type:
{client.get("operation_type")}

Common Lanes:
{common_lanes}

Pain Points:
{pain_points}

Tone:
{client.get("tone")}

Requirements:
- Write like an owner, dispatcher, or operations manager talking to drivers
- Mention freight conditions
- Mention operational reminders relevant to this company
- Keep concise
- Avoid corporate fluff
- Do not use emojis
- Do not use hashtags
"""

    freight_digest_prompt = f"""
Write a concise freight and trucking industry digest for this company.

Company:
{company_name}

Region:
{client.get("region")}

Primary States:
{primary_states}

Equipment:
{client.get("equipment")}

Operation Type:
{client.get("operation_type")}

Common Lanes:
{common_lanes}

Pain Points:
{pain_points}

Tone:
{client.get("tone")}

Requirements:
- Mention freight trends relevant to this operation
- Mention diesel/fuel conditions generally
- Mention weather/logistics concerns relevant to their lanes
- Include practical operational tips
- Do not invent exact prices or statistics
- Do not use emojis
- Do not use hashtags
"""

    print(f"\n=== Generating pack for {company_name} ===")

    print("Generating recruiting posts...")
    recruiting_posts = proofread_content(
        "Recruiting Posts",
        generate_text(recruiting_prompt)
    )

    print("Generating social posts...")
    social_posts = proofread_content(
        "Social Posts",
        generate_text(social_prompt)
    )

    print("Generating safety reminders...")
    safety_reminders = proofread_content(
        "Safety Reminders",
        generate_text(safety_prompt)
    )

    print("Generating company update...")
    company_update = proofread_content(
        "Company Update",
        generate_text(company_update_prompt)
    )

    print("Generating freight digest...")
    freight_digest = proofread_content(
        "Freight Digest",
        generate_text(freight_digest_prompt)
    )

    full_pack = f"""
# Weekly Fleet Recruiting & Communication Pack

## Client
{company_name}

## Fleet Size
{client.get("fleet_size")}

## Region
{client.get("region")}

## Home Base
{client.get("home_base")}

## Equipment
{client.get("equipment")}

## Operation Type
{client.get("operation_type")}

## Hiring For
{client.get("hiring_for")}

## Week
{week_label}

---

# 1. Recruiting Posts

{recruiting_posts}

---

# 2. Social Posts

{social_posts}

---

# 3. Safety Reminders

{safety_reminders}

---

# 4. Company Update

{company_update}

---

# 5. Freight Digest

{freight_digest}
"""

    full_pack = clean_common_typos(full_pack)

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

    pdf_pack = clean_pdf_text(full_pack)

    for line in pdf_pack.splitlines():
        line = clean_pdf_text(line)

        if not line:
            story.append(Spacer(1, 8))
            continue

        if line.startswith("# "):
            story.append(Paragraph(line.replace("# ", ""), styles["Title"]))
            story.append(Spacer(1, 12))

        elif line.startswith("## "):
            story.append(Paragraph(line.replace("## ", ""), styles["Heading2"]))
            story.append(Spacer(1, 8))

        elif line.startswith("---"):
            story.append(Spacer(1, 12))

        else:
            story.append(Paragraph(line, styles["BodyText"]))
            story.append(Spacer(1, 6))

    doc.build(story)

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
