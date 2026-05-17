import json
import generate_text
from pathlib import Path
from datetime import datetime
from src.openai_utils 
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
# CONTENT SECTIONS
# =========================

recruiting_posts = f"""
1. Looking for experienced CDL-A drivers who want steady freight and weekly home time? Join {client['company_name']} and drive with a team that respects your time on the road.

2. At {client['company_name']}, we keep drivers moving with consistent regional freight and reliable dispatch communication.

3. Tired of feeling like just another truck number? We're hiring CDL-A regional drivers who want professionalism and steady work.

4. Drive newer equipment, run consistent lanes, and get home weekly with {client['company_name']}.

5. Join a fleet focused on steady miles, paid detention, and driver communication that actually matters.
"""

social_posts = f"""
1. Safety, communication, and consistency — that's how we operate at {client['company_name']}.

2. Regional freight doesn't have to mean chaos. We focus on steady work and reliable routes.

3. Good drivers deserve good communication. That's the standard at {client['company_name']}.
"""

safety_reminders = """
1. Wet spring conditions across the Pacific Northwest mean increased stopping distance. Slow down and leave room.

2. Always verify trailer lights and tire conditions before departure, especially during heavy rain conditions.
"""

company_update = """
Freight volume remained steady this week across our regional lanes. We appreciate the hard work from all drivers continuing to deliver safely and professionally.
"""

freight_digest = """
Diesel prices remained relatively stable this week while regional freight demand across the Pacific Northwest continues to hold steady.
"""

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
# SAVE INDIVIDUAL FILES
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
# SUCCESS MESSAGE
# =========================

print(f"\nPack generated successfully.")
print(f"Output directory: {output_dir}")
