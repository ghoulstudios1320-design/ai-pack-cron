import os, json, yaml
from pathlib import Path
from notion_client import Client

def latest_out_dir() -> Path:
    return sorted(Path("output").glob("*"))[-1]

def build_links(out_dir: Path) -> dict:
    # Prefer Drive links if present
    dl = out_dir / "drive_links.json"
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    if dl.exists():
        info = json.loads(dl.read_text(encoding="utf-8"))
        return {"pdf": info["pdf_url"], "md": info["md_url"]}

    # Fallback: raw GitHub links if you later commit packs/ to the repo
    repo = os.environ.get("GITHUB_REPOSITORY")
    folder = out_dir.name
    pdf_url = f"https://raw.githubusercontent.com/{repo}/main/packs/{folder}/{meta['pdf_name']}"
    md_url  = f"https://raw.githubusercontent.com/{repo}/main/packs/{folder}/{meta['md_name']}"
    return {"pdf": pdf_url, "md": md_url}

def main():
    notion = Client(auth=os.environ["NOTION_API_KEY"])
    db_id  = os.environ["NOTION_DATABASE_ID"]
    hub_id = os.environ["NOTION_MEMBERS_PAGE_ID"]

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
    year = int(year_str); week = int(week_str)

    # 1) Content DB page
    notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name":   {"title": [{"text": {"content": title}}]},
            "Status": {"select": {"name": "Published"}},
            "Week":   {"number": week},
            "Year":   {"number": year},
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

    # 2) Members Hub section
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": f"Week {week:02d} ({year})"}}]}
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
