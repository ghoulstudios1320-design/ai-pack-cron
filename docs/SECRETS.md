# Required GitHub Secrets

These secrets are configured in:

```text
GitHub repo → Settings → Secrets and variables → Actions
```

---

# OpenAI

## OPENAI_API_KEY

Required for AI-generated content.

Used by:

```text
src/generate_trucking_pack.py
src/ai_content.py
```

Optional model override:

```text
OPENAI_MODEL
```

Default model if unset:

```text
gpt-4.1-mini
```

---

# Google Drive

## GOOGLE_SERVICE_ACCOUNT_JSON

Required for real Google Drive uploads.

This should contain the full Google service account JSON.

## GOOGLE_DRIVE_FOLDER_ID

Required for uploading generated packs into the target Drive folder.

Used by:

```text
src/upload_drive_artifacts.py
```

---

# Notion

## NOTION_API_KEY

Required for publishing pages to Notion.

## NOTION_DATABASE_ID

Required Notion database target.

Used by:

```text
src/publish_to_notion.py
```

The Notion integration must have access to the target database.

---

# Webhook

## WEBHOOK_URL

Required for real webhook notifications.

Used by:

```text
src/send_webhook_notifications.py
```

Expected success:

```json
"webhook_mode": "real",
"webhook_failed_client_count": 0
```

---

# Email / SMTP

Used by:

```text
src/send_email_notifications.py
```

## SMTP_HOST

For Gmail:

```text
smtp.gmail.com
```

## SMTP_PORT

For Gmail:

```text
587
```

## SMTP_USERNAME

The sending email account.

Example:

```text
example@gmail.com
```

## SMTP_PASSWORD

SMTP password or app password.

For Gmail, this should be a Gmail App Password, not the normal account password.

## SMTP_FROM_EMAIL

The sender email address.

Usually the same as SMTP_USERNAME.

## SMTP_FROM_NAME

Sender display name.

Example:

```text
Trucking Pack Automation
```

## PACK_EMAIL_TO

Global email recipient list for testing or simple delivery.

Single email:

```text
you@example.com
```

Multiple emails:

```text
you@example.com,dispatch@example.com,recruiting@example.com
```

---

# Expected Email Success

When SMTP secrets are correct:

```json
"email_mode": "real",
"email_sent_client_count": 3,
"email_failed_client_count": 0,
"email_skipped_client_count": 0
```

Production summary should show:

```text
Email Notifications | ✅ | mode=`real`, sent=`3`, failed=`0`, skipped=`0`
```

---

# Expected Email Skip

If SMTP secrets are missing, the workflow should not fail.

Expected manifest:

```json
"email_mode": "skipped",
"email_sent_client_count": 0,
"email_failed_client_count": 0,
"email_skipped_client_count": 3
```

This is non-blocking by design.

---

# Secret Checklist

Required for full production:

```text
OPENAI_API_KEY
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_DRIVE_FOLDER_ID
NOTION_API_KEY
NOTION_DATABASE_ID
WEBHOOK_URL
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM_EMAIL
SMTP_FROM_NAME
PACK_EMAIL_TO
```
