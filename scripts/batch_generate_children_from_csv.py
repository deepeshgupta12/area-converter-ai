import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

import pandas as pd
from pymongo import MongoClient

from src.models import ChildPageOutput
from src.generator import generate_child_content
from src.mappers import build_child_mongo_doc
from src.validation import validate_child_lengths
from src.section_regen import regenerate_section


# ---------- CONFIG HELPERS ----------

# Special codes for common units; everything else will be normalized
SPECIAL_CODES: Dict[str, str] = {
    "Square Meter": "SQ_M",
    "Square Meter ": "SQ_M",
    "Square Meteres": "SQ_M",  # just in case of typos
    "Square Meters": "SQ_M",
    "Square Feet": "SQ_FT",
    "Square Foot": "SQ_FT",
    " Square Feet": "SQ_FT",
    " Square Foot": "SQ_FT",
    "Square Yard": "SQ_YD",
    " Square Yard": "SQ_YD",
    "Square Inch": "SQ_IN",
    "Square Kilometer": "SQ_KM",
    "Square Mile": "SQ_MI",
    "Acre": "ACRE",
    "Hectare": "HECTARE",
}

# Map region tokens to a representative city (tweak this for SEO as you like)
REGION_TO_CITY: Dict[str, str] = {
    "Assam": "Guwahati",
    "Bengal": "Kolkata",
    "Bihar": "Patna",
    "Jharkhand": "Ranchi",
    "Tripura": "Agartala",
    "Gujarat": "Ahmedabad",
    "Rajasthan": "Jaipur",
    "Punjab": "Chandigarh",
    "Haryana": "Gurugram",
    "HP": "Shimla",
    "Himachal": "Shimla",
    "Uttarakhand": "Dehradun",
    "UP": "Lucknow",
    "MP": "Bhopal",
}

def render_child_html_page(
    ai_output: ChildPageOutput,
    *,
    slug: str,
    from_label: str,
    to_label: str,
    factor: float,
    locale: str,
    site_code: str,
    url_path: str,
) -> str:
    """Builds a simple standalone HTML page for previewing one child page."""
    seo_title = ai_output.seo_meta_title
    seo_desc = ai_output.seo_meta_description
    h1 = ai_output.h1_heading

    canonical = f"https://www.squareyards.com{url_path}"

    why_html = ai_output.why_convert_section_html
    from_html = ai_output.from_unit_section_html
    to_html = ai_output.to_unit_section_html
    examples_html = ai_output.examples_section_html
    tech_html = ai_output.technical_details_html

    faqs_html_parts = []
    for faq in ai_output.faqs:
        q = faq.get("question", "")
        ans = faq.get("answer_html", "")
        faqs_html_parts.append(
            f"<div class='faq-item'><h3>{q}</h3>{ans}</div>"
        )
    faqs_html = "\n".join(faqs_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{seo_title}</title>
  <meta name="description" content="{seo_desc}" />
  <link rel="canonical" href="{canonical}" />
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 960px;
      margin: 2rem auto;
      padding: 0 1.5rem 3rem;
      line-height: 1.6;
      color: #222;
      background: #fafafa;
    }}
    header {{
      border-bottom: 1px solid #ddd;
      margin-bottom: 1.5rem;
      padding-bottom: 0.5rem;
    }}
    h1 {{
      font-size: 1.9rem;
      margin-bottom: 0.5rem;
    }}
    h2 {{
      margin-top: 2rem;
      font-size: 1.4rem;
      border-bottom: 1px solid #eee;
      padding-bottom: 0.25rem;
    }}
    h3 {{
      margin-top: 1.25rem;
      font-size: 1.1rem;
    }}
    .meta {{
      font-size: 0.9rem;
      color: #555;
    }}
    .meta span {{
      display: inline-block;
      margin-right: 1rem;
    }}
    .section {{
      margin-top: 1.5rem;
      background: #fff;
      padding: 1.25rem 1rem;
      border-radius: 6px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .section p {{
      margin: 0.35rem 0;
    }}
    .faq-item {{
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px dashed #e0e0e0;
    }}
    code {{
      font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
      background: #f3f3f3;
      padding: 0.1rem 0.25rem;
      border-radius: 3px;
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{h1}</h1>
    <div class="meta">
      <span><strong>Slug:</strong> {slug}</span>
      <span><strong>URL path:</strong> {url_path}</span>
      <span><strong>From:</strong> {from_label}</span>
      <span><strong>To:</strong> {to_label}</span>
      <span><strong>Factor:</strong> 1 {from_label} ≈ {factor} {to_label}</span>
      <span><strong>Locale:</strong> {locale}</span>
      <span><strong>Site:</strong> {site_code}</span>
    </div>
  </header>

  <section class="section">
    <h2>Why convert {from_label} to {to_label}?</h2>
    {why_html}
  </section>

  <section class="section">
    <h2>What is {from_label}?</h2>
    {from_html}
  </section>

  <section class="section">
    <h2>What is {to_label}?</h2>
    {to_html}
  </section>

  <section class="section">
    <h2>Examples: {from_label} to {to_label}</h2>
    {examples_html}
  </section>

  <section class="section">
    <h2>Technical details</h2>
    {tech_html}
  </section>

  <section class="section">
    <h2>FAQs</h2>
    {faqs_html}
  </section>
</body>
</html>
"""

def normalize_unit_code(label: str) -> str:
    """
    Turn a human-readable unit label into a code (e.g. 'Bigha – Assam' → 'BIGHA_ASSAM').
    Uses SPECIAL_CODES where known.
    """
    clean = label.strip()
    if clean in SPECIAL_CODES:
        return SPECIAL_CODES[clean]

    # generic: uppercase, non-alphanum -> _
    base = re.sub(r"[^0-9a-zA-Z]+", "_", clean)
    base = base.strip("_")
    return base.upper()


def extract_region(label: str) -> Optional[str]:
    """
    Try to extract region/state from things like 'Bigha – Assam', 'Dhur-Bihar', 'Bigha-Uttarakhand-II'.
    If nothing meaningful is found, return None.
    """
    name = label.strip()
    # Try the long dash variants first
    for sep in ["–", "—", "-"]:
        if sep in name:
            parts = [p.strip() for p in name.split(sep) if p.strip()]
            if len(parts) >= 2:
                # last part is often region-ish: 'Assam', 'Bihar', 'Uttarakhand-II'
                return parts[-1]
    return None


def guess_city(from_label: str, to_label: str, default_city: str) -> str:
    """
    Guess a city based on region tokens in the unit names; fall back to default_city.
    """
    candidates = [from_label, to_label]
    for label in candidates:
        for region_key, city in REGION_TO_CITY.items():
            if region_key.lower() in label.lower():
                return city
    return default_city


def build_slug(from_code: str, to_code: str) -> str:
    def norm(c: str) -> str:
        return c.lower().replace("_", "-")

    return f"{norm(from_code)}-to-{norm(to_code)}"


def section_names_from_issues(issues: List[str]) -> Set[str]:
    """
    Map validation issue strings to section names understood by regenerate_section.
    """
    sections: Set[str] = set()
    for msg in issues:
        if "why_convert_section_html" in msg:
            sections.add("why_convert")
        elif "from_unit_section_html" in msg:
            sections.add("from_unit")
        elif "to_unit_section_html" in msg:
            sections.add("to_unit")
        elif "examples_section_html" in msg:
            sections.add("examples")
        elif "technical_details_html" in msg:
            sections.add("technical")
        elif "faqs[" in msg:
            sections.add("faq_block")
    return sections


# ---------- CORE BATCH LOGIC ----------

def process_pair(
    row_label: str,
    col_label: str,
    factor: float,
    *,
    default_city: str,
    locale: str,
    site_code: str,
    mongo_collection,
    auto_fix_lengths: bool,
    max_fix_passes: int,
    preview_only: bool,
    html_out_dir: Optional[Path],
) -> Tuple[bool, List[str]]:
    
    """
    Generate, validate (and optionally auto-fix) one child page for (row_label -> col_label),
    then upsert into Mongo.
    Returns (success_flag, issues_list).
    """
    from_label = row_label.strip()
    to_label = col_label.strip()

    from_code = normalize_unit_code(from_label)
    to_code = normalize_unit_code(to_label)

    # Regions for SEO
    from_region = extract_region(from_label) or "Pan-India"
    to_region = extract_region(to_label) or "Pan-India"

    city_name = guess_city(from_label, to_label, default_city=default_city)

    # Build payload for generate_child_content
    payload = {
        "from_unit_code": from_code,
        "to_unit_code": to_code,
        "from_unit_label": from_label,
        "to_unit_label": to_label,
        "factor_to_unit": factor,
        "from_unit_region": from_region,
        "to_unit_region": to_region,
        "city_name": city_name,
        "direction_note": (
            f"This page is specifically about converting FROM {from_label} "
            f"TO {to_label}. Make the content clearly directional and do not "
            f"write generic text that would equally fit the reverse ({to_label} "
            f"to {from_label})."
        ),
    }

    ai_output: ChildPageOutput = generate_child_content(payload)

    # First validation
    issues = validate_child_lengths(ai_output)

    if issues and auto_fix_lengths:
        for _ in range(max_fix_passes):
            if not issues:
                break

            section_names = section_names_from_issues(issues)
            for section in section_names:
                regen = regenerate_section(
                    section=section,
                    from_unit_code=from_code,
                    to_unit_code=to_code,
                    from_unit_label=from_label,
                    to_unit_label=to_label,
                    factor_to_unit=factor,
                    from_unit_region=from_region,
                    to_unit_region=to_region,
                    city_name=city_name,
                )

                if section == "why_convert":
                    ai_output.why_convert_section_html = regen[
                        "why_convert_section_html"
                    ]
                elif section == "from_unit":
                    ai_output.from_unit_section_html = regen[
                        "from_unit_section_html"
                    ]
                elif section == "to_unit":
                    ai_output.to_unit_section_html = regen[
                        "to_unit_section_html"
                    ]
                elif section == "examples":
                    ai_output.examples_section_html = regen[
                        "examples_section_html"
                    ]
                elif section == "technical":
                    ai_output.technical_details_html = regen[
                        "technical_details_html"
                    ]
                elif section == "faq_block":
                    ai_output.faqs = regen["faqs"]

            # Re-validate after regenerations
            issues = validate_child_lengths(ai_output)

    # Build Mongo document
    slug = build_slug(from_code, to_code)
    url_path = f"/area-convertor/{slug}"

    mongo_doc = build_child_mongo_doc(
        ai_output,
        parent_slug="area-convertor",
        slug=slug,
        url_path=url_path,
        from_unit_code=from_code,
        to_unit_code=to_code,
        from_unit_label=from_label,
        to_unit_label=to_label,
        locale=locale,
        site_code=site_code,
    )

        # Build Mongo document
    slug = build_slug(from_code, to_code)
    url_path = f"/area-convertor/{slug}"

    # Optional HTML preview output
    if html_out_dir is not None:
        html_out_dir.mkdir(parents=True, exist_ok=True)
        html_str = render_child_html_page(
            ai_output,
            slug=slug,
            from_label=from_label,
            to_label=to_label,
            factor=factor,
            locale=locale,
            site_code=site_code,
            url_path=url_path,
        )
        html_path = html_out_dir / f"{slug}.html"
        html_path.write_text(html_str, encoding="utf-8")
        print(f"HTML preview written to {html_path}")

    if preview_only:
        print(json.dumps(mongo_doc, indent=2, ensure_ascii=False, default=str))
    else:
        mongo_collection.update_one(
            {
                "parentSlug": mongo_doc["parentSlug"],
                "slug": mongo_doc["slug"],
                "locale": mongo_doc["locale"],
                "siteCode": mongo_doc["siteCode"],
            },
            {"$set": mongo_doc},
            upsert=True,
        )

    success = not issues
    return success, issues


def main():
    parser = argparse.ArgumentParser(
        description="Batch-generate Area Converter child pages from CSV."
    )

    parser.add_argument(
        "--csv_path",
        type=str,
        default="AreaCalculation - Sheet2.csv",
        help="Path to the area conversion matrix CSV.",
    )
    parser.add_argument(
        "--mongo_uri",
        type=str,
        default="mongodb://localhost:27017",
        help="MongoDB connection URI.",
    )
    parser.add_argument(
        "--db_name",
        type=str,
        default="squareyards",
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        default="area_converter_child_pages",
        help="MongoDB collection for child pages.",
    )
    parser.add_argument(
        "--default_locale",
        type=str,
        default="en-IN",
    )
    parser.add_argument(
        "--site_code",
        type=str,
        default="sqy-india-web",
    )
    parser.add_argument(
        "--default_city",
        type=str,
        default="Mumbai",
        help="Fallback city if none is inferred from unit labels.",
    )
    parser.add_argument(
        "--limit_pairs",
        type=int,
        default=0,
        help="Limit number of pairs to process (0 = no limit).",
    )
    parser.add_argument(
        "--auto_fix_lengths",
        action="store_true",
        help="Automatically try to regenerate sections that fail length validation.",
    )
    parser.add_argument(
        "--max_fix_passes",
        type=int,
        default=2,
        help="Max passes of auto-fix per page.",
    )
    parser.add_argument(
        "--preview_only",
        action="store_true",
        help="Do not write to Mongo; just print JSON docs.",
    )

    parser.add_argument(
        "--html_out_dir",
        type=str,
        default="",
        help="If set, write an HTML preview file for each generated child page into this directory.",
    )

    args = parser.parse_args()

    html_out_dir: Optional[Path] = None
    if args.html_out_dir:
        html_out_dir = Path(args.html_out_dir).expanduser()

    # Load CSV
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Assume first column is the row label (like 'Unnamed: 0')
    row_label_col = df.columns[0]
    row_labels = df[row_label_col].tolist()
    col_labels = df.columns[1:].tolist()

    # Mongo client
    client = MongoClient(args.mongo_uri)
    db = client[args.db_name]
    collection = db[args.collection_name]

    processed = 0
    successes = 0
    failures = 0

    for i, row_label in enumerate(row_labels):
        for col_label in col_labels:
            factor = df.at[i, col_label]

            # Skip NaN or zero factors
            try:
                if factor is None or (isinstance(factor, float) and math.isnan(factor)):
                    continue
            except TypeError:
                continue

            if isinstance(factor, (int, float)) and factor == 0:
                continue

            # Skip self-conversion
            if str(row_label).strip() == str(col_label).strip():
                continue

            processed += 1
            if args.limit_pairs and processed > args.limit_pairs:
                break

            print(
                f"\n=== Processing pair #{processed}: "
                f"{row_label.strip()} -> {col_label.strip()} "
                f"(factor={factor}) ==="
            )
            success, issues = process_pair(
                row_label=row_label,
                col_label=col_label,
                factor=float(factor),
                default_city=args.default_city,
                locale=args.default_locale,
                site_code=args.site_code,
                mongo_collection=collection,
                auto_fix_lengths=args.auto_fix_lengths,
                max_fix_passes=args.max_fix_passes,
                preview_only=args.preview_only,
                html_out_dir=html_out_dir,
            )

            if success:
                successes += 1
                print("Status: OK (all sections within desired length ranges).")
            else:
                failures += 1
                print("Status: Has remaining length issues:")
                for issue in issues:
                    print(f" - {issue}")

        if args.limit_pairs and processed >= args.limit_pairs:
            break

    print("\n===== BATCH SUMMARY =====")
    print(f"Total pairs processed: {processed}")
    print(f"Successful (fully valid): {successes}")
    print(f"With remaining issues:   {failures}")


if __name__ == "__main__":
    main()