import os, json
from pathlib import Path
from notion_client import Client

# ---------- helpers ----------
def latest_out_dir() -> Path:
    out_root = Path("output")
    return sorted(out_root.glob("*"))[-1]

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def github_file_url(path_in_repo: str, branch: str = "main") -> str:
    """
    Build a raw GitHub URL to a file committed in the repo.
    Requires the workflow step that commits packs/ to the repo,
    or you can ignore this if you're only using Drive.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")  # owner/repo (set automatically in Actions)
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path_in_repo}"

def build_links(out_dir: Path) -> dict:
    """
    Prefer Drive links if drive_links.json is present.
    Otherwise, fall back to GitHub raw URLs for files committed to packs/.
    """
    drive_links = out_dir / "drive_links.json"
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))

    if drive_links.exists():
        dl = json.loads(drive_links.read_text(encoding="utf-8"))
        return {"pdf": dl["pdf_url"], "md": dl["md_url"]}

    # Fallback to GitHub links (requires you committed packs/YYYY-WNN/* to the repo)
    folder = out_dir.name  # e.g., 2025-W39
    pdf_url = github_file_url(f"packs/{folder}/{meta['pdf_name']}")
    md_url  = github_file_url(f"packs/{folder}/{meta['md_name']}")
    return {"pdf": pdf_url, "md": md_url}

# ---------- main ----------
def main():
    notion = Client(auth=os.environ["NOTION_API_KEY"])
    db_id  = os.environ["NOTION_DATABASE_ID"]
    hub_id = os.environ["NOTION_MEMBERS_PAGE_ID"]

    out_dir = latest_out_dir()
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    title = meta["title"]
    seo_md = (out_dir / "seo_post.md").read_text(encoding="utf-8")
    links = build_links(out_dir)

    # Derive week/year from folder name "YYYY-WNN"
    year_str, week_str = out_dir.name.split("-W")
    year = int(year_str); week = int(week_str)

    # 1) Create SEO page in Content DB
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

    # 2) Append links to Members Hub
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
                    {
                        "type": "text",
                        "text": {"content": "PDF pack", "link": {"url": links["pdf"]}}
                    }
                ]
            }
        },
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "Markdown pack", "link": {"url": links["md"]}}
                    }
                ]
            }
        }
    ]

    notion.blocks.children.append(block_id=hub_id, children=blocks)
    print(f"[OK] Notion updated. PDF: {links['pdf']} | MD: {links['md']}")

if __name__ == "__main__":
    main()
