import sys, json, html
from datetime import datetime

def esc(x):
    return html.escape(str(x)) if x is not None else ""

def as_html_block(label, html_content):
    if not html_content:
        return f"<div class='card'><div class='muted'>{esc(label)}</div><p>(empty)</p></div>"
    return f"<div class='card'><div class='muted'>{esc(label)}</div><div class='content'>{html_content}</div></div>"

def render_faqs(faqs):
    if not faqs:
        return "<p>No FAQs generated.</p>"
    out = []
    for i, f in enumerate(faqs, start=1):
        if not isinstance(f, dict):
            continue
        q = f.get("question", "")
        # raw uses answer_html
        a = f.get("answer_html") or f.get("answerHtml") or ""
        out.append(f"""
          <div class="faq">
            <div class="muted">FAQ {i}</div>
            <h4>{esc(q)}</h4>
            <div class="content">{a}</div>
          </div>
        """)
    return "\n".join(out)

def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("No stdin JSON found.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(raw)

    # Detect RAW child schema
    is_raw_child = "seo_meta_title" in data or "why_convert_section_html" in data

    if not is_raw_child:
        print("This renderer expects --mode raw child JSON.", file=sys.stderr)
        print("Tip: If you used --mode mongo, use a mongo renderer instead.", file=sys.stderr)
        sys.exit(2)

    title = data.get("seo_meta_title", "Area Converter Child Page")
    meta_desc = data.get("seo_meta_description", "")
    h1 = data.get("h1_heading", title)

    why_html = data.get("why_convert_section_html", "")
    from_html = data.get("from_unit_section_html", "")
    to_html = data.get("to_unit_section_html", "")
    examples_html = data.get("examples_section_html", "")
    tech_html = data.get("technical_details_html", "")
    faqs = data.get("faqs", [])

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta_desc)}" />
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      max-width: 980px; margin: 32px auto; padding: 0 18px 60px;
      color: #222; line-height: 1.6;
    }}
    header {{ border-bottom: 1px solid #e5e5e5; padding-bottom: 12px; margin-bottom: 22px; }}
    h1 {{ font-size: 28px; margin: 0 0 6px; }}
    h2 {{ font-size: 20px; margin-top: 28px; }}
    h3 {{ font-size: 17px; margin: 10px 0 6px; }}
    .muted {{ color: #666; font-size: 12px; }}
    .section {{ margin-top: 18px; }}
    .card {{
      border: 1px solid #eee; border-radius: 8px; padding: 12px 14px; margin: 10px 0;
      background: #fafafa;
    }}
    .content p {{ margin: 6px 0; }}
    .faq {{
      border-top: 1px dashed #e0e0e0; padding-top: 12px; margin-top: 12px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="muted">Child Page Preview (RAW) • {esc(datetime.utcnow().isoformat())}Z</div>
    <h1>{esc(h1)}</h1>
    <div class="muted">{esc(title)}</div>
  </header>

  <div class="section">
    <h2>Why Convert</h2>
    {as_html_block("why_convert_section_html", why_html)}
  </div>

  <div class="section">
    <h2>What is the From Unit?</h2>
    {as_html_block("from_unit_section_html", from_html)}
  </div>

  <div class="section">
    <h2>What is the To Unit?</h2>
    {as_html_block("to_unit_section_html", to_html)}
  </div>

  <div class="section">
    <h2>Examples & Use Cases</h2>
    {as_html_block("examples_section_html", examples_html)}
  </div>

  <div class="section">
    <h2>Technical Details</h2>
    {as_html_block("technical_details_html", tech_html)}
  </div>

  <div class="section">
    <h2>FAQs</h2>
    {render_faqs(faqs)}
  </div>

</body>
</html>
"""
    print(html_doc)

if __name__ == "__main__":
    main()
