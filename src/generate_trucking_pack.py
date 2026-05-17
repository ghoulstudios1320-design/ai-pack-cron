import json
from pathlib import Path
from datetime import datetime
from src.openai_utils import generate_text

# =========================
# LOAD CLIENT PROFILE
# =========================

client_path = Path("clients/iron_mile_freight.json")

with open(client_path, "r") as f:
    client = json.load(f)

# =========================
# CREATE OUTPUT FOLDER
# =========================

week_label = datetime.now().strftime("%Y-W%U")

output_dir = Path(f"output/{week_label}/{client['client_id']}")
output_dir.mkdir(parents=True, exist_ok=True)

# =========================
# AI GENERATED CONTENT
# =========================

recruiting_prompt = f"""
Create 5 realistic recruiting posts for a small trucking company.

Company Name:
{client['company_name']}

Region:
{client['region']}

Hiring For:
{client['hiring_for']}

Benefits:
{', '.join(client['benefits'])}

Target Driver:
{client['target_driver']}

Tone:
{client['tone']}

Requirements:
- Sound realistic
- Avoid corporate fluff
- Avoid emojis
- Avoid hashtags
- Make the posts feel authentic to trucking culture
- Separate each post clearly
"""

social_prompt = f"""
Create 3 realistic social media posts for a trucking company.

Company Name:
{client['company_name']}

Region:
{client['region']}

Tone:
{client['tone']}

Requirements:
- Sound authentic
- Professional but human
- No hashtags
- No emojis
- Focus on trucking culture, safety, consistency, professionalism
"""

safety_prompt = f"""
Create 2 trucking safety reminders for drivers operating in the Pacific Northwest.

Requirements:
- Practical
- Realistic
- Short
- Professional
"""

company_update_prompt = f"""
Write a short weekly company update/newsletter for a trucking company.

Company Name:
{client['company_name']}

Tone:
{client['tone']}

Requirements:
- Professional
- Appreciative toward drivers
- Mention freight conditions
- Keep concise
"""

freight_digest_prompt = f"""
Write a short freight and trucking industry digest for a small regional carrier operating in the Pacific Northwest.

Requirements:
- Mention freight trends
- Mention diesel/fuel conditions
- Mention weather/logistics concerns if relevant
- Keep concise
"""

# =========================
# GENERATE CONTENT
# =========================

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

# =========================
# BUILD FULL PACK
# =========================

full_pack = f"""
# Weekly Fleet Recruiting & Communication Pack

## Client
{client['company_name']}

## Fleet Size
{client['fleet_size']}

## Region
{client['region']}

## Hiring For
{client['hiring_for']}

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

# =========================
# SAVE FILES
# =========================

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

# =========================
# SUCCESS
# =========================

print("\nPack generated successfully.")
print(f"Output directory: {output_dir}")
