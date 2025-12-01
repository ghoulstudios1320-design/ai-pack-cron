import os, json, yaml
from pathlib import Path
from notion_client import Client

def latest_out_dir() -> Path:
    return sorted(Path("output").glob("*"))[-1]

def build_links(out_dir: Path) -> dict:
    dl = out_dir / "drive_links.json"
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    if dl.exists():
        info = json.loads(dl.read_text(encoding="utf-8"))
        return {"pdf": info["pdf_url"], "md": info["md_url"]}
    # fallback to GitHub raw if not using Google Drive
    repo = os.environ.get("GITHUB_REPOSITORY")
    folder = out_dir.name
    pdf_url = f"https://raw.githubusercontent.com/{repo}/main/packs/{folder}/{meta['pdf_name']}"
    md_url  = f"https://raw.githubusercontent.com/{repo}/main/packs/{folder}/{meta['md_name']}"
    return {"pdf": pdf_url, "md": md_url}

def get_db_schema(notion: Client, db_id: str):
    return notion.databases.retrieve(db_id)

# ---------- TITLE PROPERTY DETECTION (NEW SAFE VERSION) ----------
def find_title_prop_name(db_schema: dict) -> str:
    """
    Try to find the Notion title property with fallbacks:
      1. Find property with type='title'
      2. If not found, just assume column is named 'Name'
    We also print out the available properties for debugging.
    """
    props = db_schema.get("properties", {})
    print(f"[notion] Available properties: {list(props.keys())}")

    # Normal case — real Notion title property
    for prop_name, prop in props.items():
        if prop.get("type") == "title":
            print(f"[notion] Found real title property: '{prop_name}'")
            return prop_name

    # Fallback — assume default 'Name' column
    print("[notion][WARN] No 'title'-type property found. "
          "Falling back to property name 'Name'.")
    return "Name"
# -----------------------------------------------------------------

def main():
    notion = Client(auth=os.environ["NOTION_API_KEY"])
    db_id  = os.environ["NOTION_DATABASE_ID"]
    hub_id = os.environ["NOTION_MEMBERS_PAGE_ID"]

    print(f"[env] NOTION_DATABASE_ID={db_id}")
    print(f"[env] NOTION_MEMBERS_PAGE_ID={hub_id}")

    # --- outputs & meta
    out_dir = latest_out_dir()
    meta_path = out_dir / "meta.json"
    assert meta_path.exists() and meta_path.stat().st_size > 0, f"meta.json missing/empty at {meta_path}"

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    title = meta["title"]
    seo_md = (out_dir / "seo_post.md").read_text(encoding="utf-8")
    links = build_links(out_dir)

    year_str, week_str = out_dir.name.split("-W")
    year = int(year_str)
    week = int(week_str)

    # --- Notion database schema
    db_schema = get_db_schema(notion, db_id)
    print(f"[notion] Retrieved database: {db_schema.get('title')}")
    title_prop = find_title_prop_name(db_schema)
    print(f"[notion] Using title property: '{title_prop}'")

    # --- 1) Create page in database
    page = notion.pages.create(
        parent={"database_id": db_id},
        properties={
            title_prop: {
                "title": [{"text": {"content": title}}]
            }
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": seo_md[:1900]}}
                    ]
                }
            }
        ]
    )

    page_id = page["id"]
    print(f"[notion] Created page {page_id}")

    # --- 2) Optional property updates
    db_props = db_schema.get("properties", {})
    update_props = {}

    if "Status" in db_props and db_props["Status"].get("type") == "select":
        update_props["Status"] = {"select": {"name": "Published"}}

    if "Week" in db_props and db_props["Week"].get("type") == "number":
        update_props["Week"] = {"number": week}

    if "Year" in db_props and db_props["Year"].get("type") == "number":
        update_props["Year"] = {"number": year}

    if update_props:
        notion.pages.update(page_id=page_id, properties=update_props)
        print(f"[notion] Updated: {list(update_props.keys())}")
    else:
        print("[notion] No Status/Week/Year fields to update.")

    # --- 3) Append links to Members Hub
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"Week {week:02d} ({year})"}}]
            }
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": "PDF pack", "link": {"url": links["pdf"]}}}
                ]
            }
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": "Markdown pack", "link": {"url": links["md"]}}}
                ]
            }
        }
    ]

    notion.blocks.children.append(block_id=hub_id, children=blocks)

    print(f"[OK] Notion updated. PDF: {links['pdf']} | MD: {links['md']}")

if __name__ == "__main__":
    main()
