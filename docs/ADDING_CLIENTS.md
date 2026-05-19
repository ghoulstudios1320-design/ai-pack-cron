# Adding a New Trucking Client

Client configuration files live in:

```text
clients/
```

Each client should have one JSON file.

Example:

```text
clients/example_carrier.json
```

---

# Required Fields

Minimum useful client config:

```json
{
  "client_id": "example_carrier",
  "company_name": "Example Carrier",
  "fleet_size": "25 trucks",
  "region": "Pacific Northwest",
  "equipment": "dry van",
  "hiring_for": "CDL-A regional drivers",
  "tagline": "Practical freight. Clear communication.",
  "contact_email": "recruiting@examplecarrier.com",
  "contact_phone": "555-555-0100",
  "website": "examplecarrier.com/drivers",
  "operation_type": "regional trucking",
  "target_driver": "experienced CDL-A drivers",
  "experience_required": "CDL-A experience preferred",
  "home_time": "home time varies by lane",
  "pay_angle": "steady freight and practical dispatch communication",
  "common_lanes": [
    "Spokane, WA to Portland, OR",
    "Boise, ID to Seattle, WA"
  ],
  "pain_points": [
    "weather",
    "parking",
    "detention",
    "appointment pressure"
  ],
  "benefits": [
    "practical dispatch communication",
    "documented detention support",
    "safe routing decisions"
  ],
  "brand": {
    "primary_color": "#1F2937",
    "secondary_color": "#374151",
    "accent_color": "#2563EB",
    "footer_color": "#111827"
  }
}
```

---

# Optional Logo

Add logo path:

```json
"logo_path": "assets/logos/example_carrier.png"
```

Supported logo types:

```text
.png
.jpg
.jpeg
```

Recommended location:

```text
assets/logos/
```

If the logo is missing or invalid, the pipeline skips it instead of failing.

---

# Optional Email Routing

Global email delivery can use:

```text
PACK_EMAIL_TO
```

For client-specific email routing, add one of these fields:

```json
"email_recipients": [
  "dispatch@examplecarrier.com",
  "recruiting@examplecarrier.com"
]
```

Alternative supported names:

```json
"distribution_emails": [
  "ops@examplecarrier.com"
]
```

```json
"delivery_emails": [
  "owner@examplecarrier.com"
]
```

Priority order:

```text
email_recipients
distribution_emails
delivery_emails
PACK_EMAIL_TO
```

---

# AI Content

Current AI sections:

```text
recruiting_posts
social_posts
safety_reminders
company_update
freight_digest
```

The AI prompt uses the client config fields to customize content.

Most important customization fields:

```text
company_name
region
equipment
hiring_for
common_lanes
pain_points
benefits
operation_type
target_driver
experience_required
home_time
pay_angle
tagline
```

---

# Brand Colors

Each client can define:

```json
"brand": {
  "primary_color": "#1F2937",
  "secondary_color": "#374151",
  "accent_color": "#2563EB",
  "footer_color": "#111827"
}
```

These affect generated PDF cover and footer styling.

---

# After Adding a Client

Commit the client file:

```bash
git add clients/example_carrier.json
git commit -m "Add Example Carrier client config"
git push
```

Run workflow manually:

```text
GitHub → Actions → weekly-pack → Run workflow
```

Then check the artifact:

```text
output/<YYYY-W##>/example_carrier/
```

Expected files:

```text
full_pack.md
full_pack.pdf
recruiting_posts.md
social_posts.md
safety_reminders.md
company_update.md
freight_digest.md
meta.json
```

---

# Validation Checklist

After the run, open:

```text
production_summary.md
```

Confirm:

```text
Client Count increased
AI Content Status includes new client
Content Quality Guardrail passed
Drive Upload passed
Notion Publish passed
Webhook passed
Email passed or skipped intentionally
Retry Recovery passed
```

Also check:

```text
content_quality_report.json
distribution_manifest.json
master_index.json
```

---

# Do Not Add Unsupported Claims

Do not put fake or unconfirmed claims into client config.

Avoid unverified claims like:

```text
guaranteed pay
guaranteed miles
guaranteed home time
sign-on bonus
top paying
best carrier
```

The content quality validator is designed to catch risky output, but client configs should also stay grounded.
