import json
import os
import requests

NOTION_VERSION = "2022-06-28"

api_key = os.getenv("NOTION_API_KEY", "").strip()
database_id = os.getenv("NOTION_DATABASE_ID", "").strip()

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

print("NOTION_DATABASE_ID:", database_id)

print("\n--- Search accessible objects ---")
r = requests.post(
    "https://api.notion.com/v1/search",
    headers=headers,
    json={"page_size": 20},
    timeout=30,
)
print(r.status_code)
print(r.text[:5000])

print("\n--- Try retrieve database ---")
r = requests.get(
    f"https://api.notion.com/v1/databases/{database_id}",
    headers=headers,
    timeout=30,
)
print(r.status_code)
print(r.text[:5000])
