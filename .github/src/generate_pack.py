import os, yaml, textwrap
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from src.utils import ensure_output_dir, read_file, write_file
from datetime import date
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def render_pdf(md_text: str, pdf_path: Path, title="Weekly Pack"):
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER
    left, top = 0.75*inch, height - 0.75*inch
    y = top
    c.setFont("Courier", 10)
    for line in md_text.splitlines():
        for chunk in textwrap.wrap(line, width=100) or [""]:
            if y < 1*inch:
                c.showPage()
                c.setFont("Courier", 10)
                y = top
            c.drawString(left, y, chunk)
            y -= 14
    c.save()

def call_llm(system, user):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}]
    )
    return resp.choices[0].message.content

def main():
    out_dir, year, week = ensure_output_dir()
    bank = yaml.safe_load(Path("data/topic_bank.yaml").read_text(encoding="utf-8"))
    system = Path("src/prompts/system_prompt.txt").read_text(encoding="utf-8")

    user = f"""
Niche: {bank['niche']}
Persona: {bank['personas'][0]['name']} who wants to {bank['personas'][0]['outcome']}
Angles: {", ".join(bank['content_angles'])}
Rules: {", ".join(bank['weekly_variation_rules'])}

Deliver TWO sections:

# 1) Weekly Prompt Pack (structured)
- 30 prompts grouped by Research, Writing, Personalization, QA
- Each prompt includes a short example input AND a “swap-in variables” line

# 2) Notion Mini-Template (outline only)
- Explain the database properties and 5–7 template blocks (inline checklist)
- Include a brief “How to use” SOP (5 steps)

Also include:
- 3 micro case examples (before → after)
- A short “Changelog Week {week}” (what’s new)
    """.strip()

    md = call_llm(system, user)
    md_name = f"Week-{week:02d}-{year}-pack.md"
    pdf_name = f"Week-{week:02d}-{year}-pack.pdf"
    write_file(out_dir / md_name, md)
    render_pdf(md, out_dir / pdf_name, title=f"Week {week} Pack")

    seo_user = f"""
Create a 500-700 word actionable article answering ONE long-tail query relevant to "{bank['niche']}".
Pick one from: {", ".join(bank['long_tail_queries'])}.
Use H2/H3s, bullet steps, and end with a 3-step CTA to grab a free starter kit.
Return title in first line starting with: # 
    """.strip()
    seo_md = call_llm(system, seo_user)
    write_file(out_dir / "seo_post.md", seo_md)

    meta = {
        "title": f"{bank['niche']} — Week {week} ({year})",
        "date": str(date.today()),
        "md_name": md_name,
        "pdf_name": pdf_name
    }
    write_file(out_dir / "meta.json", yaml.safe_dump(meta))
    print(f"Generated {md_name}, {pdf_name}, and seo_post.md in {out_dir}")

if __name__ == "__main__":
    main()
