import os, json, yaml, textwrap, random
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from datetime import date

# Optional OpenAI
HAS_OPENAI = bool(os.environ.get("OPENAI_API_KEY"))
if HAS_OPENAI:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    except Exception:
        HAS_OPENAI = False

def render_pdf(md_text: str, pdf_path: Path, title="Weekly Pack"):
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER
    left, top = 0.75*inch, height - 0.75*inch
    y = top
    c.setFont("Courier", 10)
    for line in md_text.splitlines():
        for chunk in textwrap.wrap(line, width=100) or [""]:
            if y < 1*inch:
                c.showPage(); c.setFont("Courier", 10); y = top
            c.drawString(left, y, chunk); y -= 14
    c.save()

def call_llm(system, user, model=os.getenv("OPENAI_MODEL","gpt-4o-mini")):
    import time
    backoffs = [1, 2, 4, 8]
    for i, b in enumerate(backoffs + [None]):  # last try no sleep
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.7,
                messages=[{"role":"system","content":system},
                          {"role":"user","content":user}]
            )
            return resp.choices[0].message.content
        except Exception:
            if b is None:
                raise
            time.sleep(b)

def fallback_pack(niche: str, week: int, bank: dict) -> str:
    cats = ["Research", "Writing", "Personalization", "QA"]
    prompts = []
    num_per = 30 // len(cats)
    sample_topics = bank.get("long_tail_queries", []) or [
        "etsy seo for [sub-niche]", "best titles for [product]", "tags for [theme]"
    ]
    for cat in cats:
        prompts.append(f"## {cat}")
        for i in range(1, num_per+1):
            topic = random.choice(sample_topics)
            prompts.append(
                f"- **Prompt {i}**: Create {cat.lower()} guidance for '{topic}'.\n"
                f"  - *Example input:* product='[your product]', niche='[your niche]'\n"
                f"  - *Swap-in variables:* product, niche, audience, tone"
            )
    mini = (
        "## Notion Mini-Template\n"
        "- Properties: Status (Select), Week (Number), Year (Number), Keywords (Multi-select)\n"
        "- Template blocks:\n"
        "  1) Checklist: Research → Draft → Edit → Publish\n"
        "  2) Callout: Title formula\n"
        "  3) Code block: Tag list\n"
        "  4) Toggle: Personalization ideas\n"
        "  5) Divider\n"
        "  6) Gallery view link\n"
        "  7) CTA snippet\n"
        "- How to use (SOP):\n"
        "  1) Duplicate the template\n"
        "  2) Fill product + keywords\n"
        "  3) Generate titles/tags\n"
        "  4) Paste description\n"
        "  5) QA then publish\n"
    )
    cases = (
        "## Micro Cases\n"
        "- **Before:** Generic title → **After:** Keyword-rich title with benefit\n"
        "- **Before:** Random tags → **After:** 13 focused tags mapped to sub-niche\n"
        "- **Before:** Wall of text → **After:** Scannable bullets + CTA\n"
    )
    header = f"# {niche} — Week {week}\n\n"
    return header + "\n".join(prompts) + "\n\n" + mini + "\n\n" + cases + f"\n\n_Changelog Week {week}: baseline template generated._\n"

def fallback_seo_article(niche: str, bank: dict) -> str:
    q = (bank.get("long_tail_queries") or ["how to write etsy descriptions fast"])[0]
    return f"""# {q.title()}

## Why it matters
Clear, keyword-aligned listings rank and convert better for **{niche}**.

## Steps
1) Collect 10 seed keywords (use Etsy search suggestions).
2) Pick 1 primary + 2 secondary keywords.
3) Write a benefit-first title using a formula: [Primary] + [Style/Material] + [Use/Occasion].
4) Description:
   - Hook (1–2 lines)
   - Specs bullets
   - Personalization prompt
   - Care/Shipping
   - CTA
5) Tags (13): mix of exact match + modifiers.

## Example title formulas
- [Primary keyword] • [Material] • [Audience/Occasion]
- [Primary keyword] – [Style] – [Benefit]

## CTA
Grab the free starter kit in the Members Hub.
"""

def main():
    out_dir = None
    # Compute output folder (same logic as earlier utils)
    from src.utils import ensure_output_dir, read_file, write_file
    out_dir, year, week = ensure_output_dir()

    bank = yaml.safe_load(Path("data/topic_bank.yaml").read_text(encoding="utf-8"))
    niche = bank.get("niche", "Etsy SEO Pack")
    system = Path("src/prompts/system_prompt.txt").read_text(encoding="utf-8")

    user = f"""
Niche: {niche}
Persona: {bank['personas'][0]['name']} who wants to {bank['personas'][0]['outcome']}
Angles: {", ".join(bank['content_angles'])}
Rules: {", ".join(bank['weekly_variation_rules'])}

Deliver TWO sections:
1) Weekly Prompt Pack (30 prompts grouped by Research, Writing, Personalization, QA; each with example input + swap-in vars)
2) Notion Mini-Template (properties, 5–7 blocks, 5-step SOP)
Also add 3 micro cases + Changelog Week {week}.
""".strip()

    if HAS_OPENAI:
        try:
            md = call_llm(system, user)
        except Exception:
            md = fallback_pack(niche, week, bank)
    else:
        md = fallback_pack(niche, week, bank)

    md_name = f"Week-{week:02d}-{year}-pack.md"
    pdf_name = f"Week-{week:02d}-{year}-pack.pdf"
    write_file(out_dir / md_name, md)
    render_pdf(md, out_dir / pdf_name, title=f"Week {week} Pack")

    seo_user = f"Create a 500-700 word actionable article for {niche} answering one long-tail query from: {', '.join(bank.get('long_tail_queries', []))}"
    if HAS_OPENAI:
        try:
            seo_md = call_llm(system, seo_user)
        except Exception:
            seo_md = fallback_seo_article(niche, bank)
    else:
        seo_md = fallback_seo_article(niche, bank)

    write_file(out_dir / "seo_post.md", seo_md)

    meta = {
        "title": f"{niche} — Week {week} ({year})",
        "date": str(date.today()),
        "md_name": md_name,
        "pdf_name": pdf_name
    }
    (out_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"[OK] Generated (fallback={'no' if HAS_OPENAI else 'yes'}) in {out_dir}")

if __name__ == "__main__":
    main()
