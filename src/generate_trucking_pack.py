import json
from pathlib import Path
from datetime import datetime
from src.openai_utils import generate_text

CLIENTS_DIR = Path("clients")
week_label = datetime.now().strftime("%Y-W%U")


def as_list_text(items):
    if isinstance(items, list):
        return ", ".join(items)
    return str(items)


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
- Avoid emojis
- Avoid hashtags
- Mention equipment, lanes, home time, detention, dispatch, or securement only when relevant
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
- Avoid emojis
- Avoid hashtags
- Focus on operational reality, drivers, safety, equipment, lanes, weather, or communication
- Make each post useful, not inspirational filler
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
- Short enough to send to drivers
- Avoid generic safety slogans
- Avoid corporate language
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
- Thank drivers directly
- Mention freight conditions
- Mention 2-4 operational reminders relevant to this company
- Keep it concise
- Avoid fake names unless asked
- Avoid corporate fluff
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
- Do not invent exact prices or hard statistics
- Keep concise and useful
"""

    print(f"\n=== Generating pack for {company_name} ===")

    print("Generating recruiting posts...")
    recruiting_posts = generate_text(recruiting_prompt)

    print("Generating social posts...")
    social_posts = generate_text(social_prompt)

    print("Generating safety reminders...")
    safety_reminders = generate_text(safety_prompt)

    print("Generating company update...")
    company_update = generate_text(company_update_prompt)

    print("Generating freight digest...")
    freight_digest = generate_text(freight_digest_prompt)

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

# Deliverables

- 5 Recruiting Posts
- 3 Social Posts
- 2 Safety Reminders
- 1 Company Update / Newsletter
- 1 Freight / Industry Digest
- Editable Markdown Files

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

# 4. Company Update / Newsletter

{company_update}

---

# 5. Freight / Industry Digest

{freight_digest}
"""

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

    print(f"Pack generated successfully: {output_dir}")


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
