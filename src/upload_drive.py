# out is your latest output folder, e.g. "2025-W40"
out = sorted(Path("output").glob("*"))[-1]

# Extract year and week from the folder name
year_str, week_str = out.name.split("-W")
year = int(year_str)
week = int(week_str)

# Build the UTM query once
utm = f"?utm_source=email&utm_medium=members&utm_campaign=week{week}-{year}"

# Collect generated links here
links = {}

# After you upload the PDF, you have pdf_id -> build its link
# pdf_id = _upload_file(svc, weekly_folder_id, pdf_file, "application/pdf")
links["pdf_url"] = f"https://drive.google.com/uc?id={pdf_id}{utm}"

# After you upload the Markdown, you have md_id -> build its link
# md_id = _upload_file(svc, weekly_folder_id, md_file, "text/markdown")
links["md_url"] = f"https://drive.google.com/uc?id={md_id}{utm}"

# (Optional) if you also keep the raw share links, you can add them too
# links["pdf_share"] = pdf_share_link
# links["md_share"]  = md_share_link

# Write links to disk for later steps
(out / "drive_links.json").write_text(json.dumps(links, indent=2), encoding="utf-8")
