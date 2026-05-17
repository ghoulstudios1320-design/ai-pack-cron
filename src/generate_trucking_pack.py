import json
from pathlib import Path

# Load client profile
client_path = Path("clients/iron_mile_freight.json")

with open(client_path, "r") as f:
    client = json.load(f)

# Create output folder
output_dir = Path("output/sample_week")
output_dir.mkdir(parents=True, exist_ok=True)

# Build markdown pack
pack = f"""
# Weekly Fleet Recruiting & Communication Pack

## Company
{client['company_name']}

## Region
{client['region']}

## Hiring For
{client['hiring_for']}

---

# Recruiting Posts

1. Looking for experienced CDL-A drivers who want steady freight and weekly home time? Join {client['company_name']} and drive with a team that respects your time on the road.

2. At {client['company_name']}, we keep drivers moving with consistent regional freight and reliable dispatch communication.

3. Tired of feeling like just another truck number? We're hiring CDL-A regional drivers who want professionalism and steady work.

4. Drive newer equipment, run consistent lanes, and get home weekly with {client['company_name']}.

5. Join a fleet focused on steady miles, paid detention, and driver communication that actually matters.

---

# Social Posts

1. Safety, communication, and consistency — that's how we operate at {client['company_name']}.

2. Regional freight doesn't have to mean chaos. We focus on steady work and reliable routes.

3. Good drivers deserve good communication. That's the standard at {client['company_name']}.

---

# Safety Reminders

1. Wet spring conditions across the Pacific Northwest mean increased stopping distance. Slow down and leave room.

2. Always verify trailer lights and tire conditions before departure, especially during heavy rain conditions.

---

# Company Update

Freight volume remained steady this week across our regional lanes. We appreciate the hard work from all drivers continuing to deliver safely and professionally.

---

# Freight / Industry Digest

Diesel prices remained relatively stable this week while regional freight demand across the Pacific Northwest continues to hold steady.
"""

# Save markdown file
output_file = output_dir / "full_pack.md"

with open(output_file, "w") as f:
    f.write(pack)

print(f"Pack generated: {output_file}")
