import os, json
from notion_client import Client
from pathlib import Path
from src.utils import ensure_output_dir

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
DB_ID = os.environ["NOTION_DATABASE_ID"]
MEMBERS_PAGE_ID = os.environ["NOTION_MEMBERS_PAGE_ID"]

def main():
    out_dir, year, week = ensure_output_dir()
    seo_md = Path(out_dir / "seo_post.md").read_text(encoding="utf-8")
    title_line = seo_md.splitlines()[0].lstrip("# ").strip()
    content_md = "\n".join(seo_md.splitlines()[1:])

    drive = json.loads((out_dir/"drive_links.json").read_text(encoding="utf-8"))

    notion = Client(auth=NOTION_API_KEY)

    page = notion.pages.create(
        parent={"database_id": DB_ID},
        properties={
            "Name": {"title": [{"text": {"content": title_line}}]},
            "Status": {"select": {"name": "Published"}},
            "Week": {"number": week},
            "Year": {"number": year},
        },
        children=[
            {"object":"block","type":"paragraph","paragraph":{
                "rich_text":[{"type":"text","text":{"content":content_md}}]
            }}
        ]
    )
    seo_url = page["url"]

    notion.blocks.children.append(
        block_id=MEMBERS_PAGE_ID,
        children=[
            {"object":"block","type":"heading_2","heading_2":{"rich_text":[{"type":"text","text":{"content":f"Week {week} ({year})"}}]}},
            {"object":"block","type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"type":"text","text":{"content":"PDF pack","link":{"url":drive["pdf_url"]}}]}}},
            {"object":"block","type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"type":"text","text":{"content":"Markdown pack","link":{"url":drive["md_url"]}}]}}}
        ]
    )

    Path(out_dir / "notion_urls.json").write_text(json.dumps({"seo_url": seo_url}, indent=2), encoding="utf-8")
    print("Published Notion SEO page and updated Members Hub.")

if __name__ == "__main__":
    main()
