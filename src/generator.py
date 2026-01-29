# src/generator.py
import json
import sys
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, List
from .section_regen import regen_until_valid

from dotenv import load_dotenv
from openai import OpenAI

from .config.settings import settings
from .models import (
    LandingPageInput,
    ChildPageInput,
    LandingPageOutput,
    ChildPageOutput,
)
from .mappers import build_landing_mongo_doc, build_child_mongo_doc
from .validation import validate_child_lengths

# Load .env early
load_dotenv()

client = OpenAI(api_key=settings.openai_api_key)

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
TEMPLATES_DIR = BASE_DIR / "templates"


# -------------------------
# Prompt loading / rendering
# -------------------------
def load_prompt(template_name: Literal["landing", "child"]) -> str:
    file_map = {
        "landing": PROMPTS_DIR / "landing_prompt.txt",
        "child": PROMPTS_DIR / "child_prompt.txt",
    }
    path = file_map[template_name]
    if not path.exists():
        raise SystemExit(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_child_prompt(template: str, child_input: ChildPageInput) -> str:
    text = template

    # Required directional tokens
    text = text.replace("{{from_unit_code}}", child_input.from_unit_code)
    text = text.replace("{{from_unit_label}}", child_input.from_unit_label)
    text = text.replace("{{to_unit_code}}", child_input.to_unit_code)
    text = text.replace("{{to_unit_label}}", child_input.to_unit_label)
    text = text.replace("{{from_unit_symbol}}", child_input.from_unit_symbol or "")
    text = text.replace("{{to_unit_symbol}}", child_input.to_unit_symbol or "")

    text = text.replace(
        "{{factor_to_unit}}",
        str(child_input.factor_to_unit) if child_input.factor_to_unit is not None else "N/A",
    )
    text = text.replace("{{from_unit_region}}", child_input.from_unit_region or "Pan-India")
    text = text.replace("{{to_unit_region}}", child_input.to_unit_region or "Pan-India")
    text = text.replace("{{city_name}}", child_input.city_name or "a major Indian city")
    text = text.replace("{{direction_note}}", child_input.direction_note or "")

    return text


def render_landing_prompt(
    template: str,
    landing_input: LandingPageInput,
    injected_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Renders landing prompt by injecting CSV-derived landing context.
    injected_context overrides landing_input.landing_context if provided.

    NOTE: landing_prompt.txt must contain placeholder: {{landing_context_json}}
    """
    ctx = injected_context if injected_context is not None else landing_input.landing_context

    text = template
    text = text.replace(
        "{{landing_context_json}}",
        json.dumps(ctx or {}, ensure_ascii=False, indent=2),
    )
    return text


# -------------------------
# OpenAI call / JSON parsing
# -------------------------
def _extract_text_from_response(response: Any) -> str:
    """
    OpenAI Responses API can return different shapes. We try robust extraction.
    """
    try:
        return response.output[0].content[0].text
    except Exception:
        pass

    txt = getattr(response, "output_text", None)
    if isinstance(txt, str) and txt.strip():
        return txt

    try:
        chunks = []
        for out in getattr(response, "output", []) or []:
            for c in getattr(out, "content", []) or []:
                t = getattr(c, "text", None)
                if isinstance(t, str) and t.strip():
                    chunks.append(t)
        if chunks:
            return "\n".join(chunks)
    except Exception:
        pass

    raise ValueError("Could not extract text from OpenAI response.")


def call_model(prompt: str) -> Dict[str, Any]:
    """
    Calls OpenAI and returns parsed JSON dict.
    Expect the prompt to enforce JSON-only output.
    """
    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    text = _extract_text_from_response(response).strip()

    # Defensive: strip accidental fences
    if text.startswith("```"):
        text = text.strip().strip("`").strip()
        # If it still contains ```json blocks, strip more aggressively
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(
            "Model did not return valid JSON.\n"
            f"JSON error: {e}\n\n"
            f"Raw output (first 2000 chars):\n{text[:2000]}"
        )


# -------------------------
# CSV-driven landing context (deterministic + robust headers)
# -------------------------
def _norm_col(c: str) -> str:
    return (c or "").strip().lower()


def _choose_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    """
    Choose a column from cols matching one of candidates after normalization.
    """
    norm_to_real = {_norm_col(c): c for c in cols}
    for cand in candidates:
        if _norm_col(cand) in norm_to_real:
            return norm_to_real[_norm_col(cand)]
    return None


def _parse_keyword_pair(keyword: str) -> Optional[Tuple[str, str]]:
    """
    Parse "X to Y" from a keyword string.
    """
    if not isinstance(keyword, str):
        return None
    k = keyword.strip()
    if not k:
        return None

    # Allow "to" in varying case / spacing
    lower = k.lower()
    if " to " not in lower:
        return None

    # Split on the first ' to ' occurrence in a case-insensitive way
    idx = lower.find(" to ")
    left = k[:idx].strip()
    right = k[idx + 4 :].strip()
    if not left or not right:
        return None
    return left, right


def build_landing_context_from_csvs(search_volume_csv: Path, conversion_master_csv: Path) -> Dict[str, Any]:
    """
    Builds a structured (JSON) landing context for the prompt:
    - Top conversion intents (from search-volume sheet)
    - Unit catalog A–Z (from conversion master)
    - Guardrails + selection rules

    IMPORTANT: Do not compute/claim numeric factors here.
    Numeric factors used in content must be sourced from conversion master via code (or passed explicitly).
    """
    try:
        import pandas as pd
    except Exception:
        raise SystemExit("pandas is required for landing CSV context. Install: pip install pandas")

    if not search_volume_csv.exists():
        raise SystemExit(f"search_volume_csv not found: {search_volume_csv}")
    if not conversion_master_csv.exists():
        raise SystemExit(f"conversion_master_csv not found: {conversion_master_csv}")

    sv = pd.read_csv(search_volume_csv, encoding="utf-8-sig")
    cm = pd.read_csv(conversion_master_csv, encoding="utf-8-sig")

    # ---- Normalize headers (fixes BOM/whitespace) ----
    sv.columns = [str(c).strip() for c in sv.columns]
    cm.columns = [str(c).strip() for c in cm.columns]

    # Choose columns robustly (your sheet might have "Are Keywords" etc.)
    kw_col = _choose_col(sv.columns.tolist(), ["Area Keywords", "Are Keywords", "Keywords", "Keyword"])
    vol_col = _choose_col(sv.columns.tolist(), ["Search Volume", "Volume", "SV"])

    if not kw_col:
        raise SystemExit("Search volume CSV must contain a keywords column like: 'Area Keywords' / 'Are Keywords'.")
    if not vol_col:
        raise SystemExit("Search volume CSV must contain a volume column like: 'Search Volume'.")

    # ---- Extract intents ----
    intents = []
    for _, r in sv.iterrows():
        pair = _parse_keyword_pair(r.get(kw_col))
        if not pair:
            continue
        from_u, to_u = pair

        v = r.get(vol_col, 0)
        try:
            v = int(v)
        except Exception:
            try:
                v = int(float(v))
            except Exception:
                v = 0

        intents.append({"from": from_u, "to": to_u, "volume": v, "keyword": str(r.get(kw_col)).strip()})

    intents.sort(key=lambda x: x["volume"], reverse=True)
    top10 = intents[:10]
    top50 = intents[:50]

    # ---- Unit catalog A–Z from conversion master ----
    # Expected matrix-like file:
    # - First column: from-unit names
    # - Headers (from col 2 onwards): to-unit names
    if len(cm.columns) < 2:
        raise SystemExit("conversion_master_csv looks invalid: expected a matrix with headers + rows (>= 2 columns).")

    first_col = cm.columns[0]
    unit_set = set()

    # first column values
    unit_set.update([str(x).strip() for x in cm[first_col].dropna().tolist() if str(x).strip()])

    # header names (excluding first col)
    unit_set.update([str(c).strip() for c in cm.columns[1:].tolist() if str(c).strip()])

    units = sorted({u for u in unit_set if u and u.lower() != "nan"}, key=lambda s: s.lower())

    az: Dict[str, List[str]] = {}
    for u in units:
        letter = u[0].upper()
        if not letter.isalpha():
            letter = "#"
        az.setdefault(letter, []).append(u)

    # Keep each letter reasonably sized for prompt token efficiency
    az_compact = {k: v[:200] for k, v in az.items()}  # safety cap

    return {
        "source": {
            "search_volume_csv": str(search_volume_csv),
            "conversion_master_csv": str(conversion_master_csv),
        },
        "top_intents": {
            "top10": top10,
            "top50": top50,
        },
        "units_catalog_az": az_compact,
        "rules": {
            "india_first": True,
            "no_factor_fabrication": True,
            "use_top10_for_pills": True,
            "avoid_city_mentions_unless_unit_is_regional": True,
        },
    }


# -------------------------
# HTML rendering
# -------------------------
def render_html(mode_type: Literal["landing", "child"], mongo_doc: Dict[str, Any]) -> str:
    """
    Renders HTML using Jinja2 templates. Expects:
      - src/templates/landing.html.j2
      - src/templates/child.html.j2
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except Exception:
        raise SystemExit("jinja2 is required for --mode html. Install: pip install jinja2")

    if not TEMPLATES_DIR.exists():
        raise SystemExit(f"Templates dir not found: {TEMPLATES_DIR}")

    template_name = "landing.html.j2" if mode_type == "landing" else "child.html.j2"
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise SystemExit(f"Template file not found: {template_path}")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template(template_name)
    html = tpl.render(page=mongo_doc)

    # Guardrail: avoid empty HTML files
    if len(html.strip()) < 200:
        raise SystemExit("Rendered HTML is unexpectedly small/empty. Check template + mongo_doc keys.")
    return html


# -------------------------
# Generators
# -------------------------
def generate_landing_content(landing_input: LandingPageInput, injected_context: Optional[Dict[str, Any]] = None) -> LandingPageOutput:
    template = load_prompt("landing")
    prompt = render_landing_prompt(template, landing_input, injected_context=injected_context)
    raw = call_model(prompt)
    return LandingPageOutput(**raw)


def generate_child_content(params: dict) -> ChildPageOutput:
    child_input = ChildPageInput(**params)
    template = load_prompt("child")
    prompt = render_child_prompt(template, child_input)
    raw = call_model(prompt)
    return ChildPageOutput(**raw)


# -------------------------
# Output writing helper
# -------------------------
def write_or_print(content: str, out_path: Optional[str]) -> None:
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"Wrote: {p}")
    else:
        print(content)


# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Area Converter Content Generator")

    parser.add_argument("--type", choices=["landing", "child"], required=True)
    parser.add_argument("--mode", choices=["raw", "mongo", "html"], default="raw")
    parser.add_argument("--out", type=str, default=None, help="Optional output file path")
    # Back-compat alias
    parser.add_argument("--output_file", dest="out", help="Alias for --out")

    # Landing inputs (CSV-driven)
    parser.add_argument("--search_volume_csv", type=str, default=None)
    parser.add_argument("--conversion_master_csv", type=str, default=None)
    # Back-compat alias
    parser.add_argument("--conversion_matrix_csv", dest="conversion_master_csv", help="Alias for --conversion_master_csv")

    # Optional landing metadata (cleanest structure)
    parser.add_argument("--landing_slug", type=str, default="area-convertor")
    parser.add_argument("--landing_locale", type=str, default="en-IN")
    parser.add_argument("--landing_site_code", type=str, default="sqy-india-web")
    parser.add_argument("--canonical_base", type=str, default="https://www.squareyards.com")

    # Child-specific args
    parser.add_argument("--from_unit_code", type=str)
    parser.add_argument("--to_unit_code", type=str)
    parser.add_argument("--from_unit_label", type=str)
    parser.add_argument("--to_unit_label", type=str)
    parser.add_argument("--from_unit_symbol", type=str)
    parser.add_argument("--to_unit_symbol", type=str)
    parser.add_argument("--factor_to_unit", type=float)
    parser.add_argument("--from_unit_region", type=str)
    parser.add_argument("--to_unit_region", type=str)
    parser.add_argument("--city_name", type=str)

    # Validation flags (for child)
    parser.add_argument("--validate_lengths", action="store_true")
    parser.add_argument("--strict_lengths", action="store_true")
    parser.add_argument("--auto_regen_failed_sections", action="store_true")
    parser.add_argument("--regen_rounds", type=int, default=3)

    args = parser.parse_args()

    if args.type == "landing":
        # 1) Build landing context (dict) from CSVs if provided
        landing_context: Dict[str, Any] = {}
        if args.search_volume_csv and args.conversion_master_csv:
            landing_context = build_landing_context_from_csvs(
                Path(args.search_volume_csv),
                Path(args.conversion_master_csv),
            )

        # 2) Cleanest structure: build landing_input once and reuse for raw/mongo/html
        landing_input = LandingPageInput(
            slug=args.landing_slug,
            locale=args.landing_locale,
            site_code=args.landing_site_code,
            canonical_base=args.canonical_base,
            landing_context=landing_context,
        )

        # 3) Generate raw AI output
        ai_output = generate_landing_content(landing_input, injected_context=landing_context)

        if args.mode == "raw":
            write_or_print(ai_output.model_dump_json(indent=2, ensure_ascii=False), args.out)

        elif args.mode == "mongo":
            mongo_doc = build_landing_mongo_doc(
                ai_output,
                slug=landing_input.slug,
                locale=landing_input.locale,
                site_code=landing_input.site_code,
                canonical_base=landing_input.canonical_base,
            )
            write_or_print(json.dumps(mongo_doc, default=str, indent=2, ensure_ascii=False), args.out)

        else:  # html
            mongo_doc = build_landing_mongo_doc(
                ai_output,
                slug=landing_input.slug,
                locale=landing_input.locale,
                site_code=landing_input.site_code,
                canonical_base=landing_input.canonical_base,
            )
            html = render_html("landing", mongo_doc)
            write_or_print(html, args.out)

    else:
        # child
        if not (args.from_unit_code and args.to_unit_code and args.from_unit_label and args.to_unit_label):
            raise SystemExit("For child type, you must provide from/to unit codes and labels.")

        payload = {
            "from_unit_code": args.from_unit_code,
            "to_unit_code": args.to_unit_code,
            "from_unit_label": args.from_unit_label,
            "to_unit_label": args.to_unit_label,
            "factor_to_unit": args.factor_to_unit,
            "from_unit_symbol": args.from_unit_symbol,  # <-- ADD
            "to_unit_symbol": args.to_unit_symbol,      # <-- ADD
            "from_unit_region": args.from_unit_region,
            "to_unit_region": args.to_unit_region,
            "city_name": args.city_name,
            "direction_note": (
                f"This page is specifically about converting FROM {args.from_unit_label} "
                f"TO {args.to_unit_label}. Make the content clearly directional and do not "
                f"write generic text that would equally fit the reverse ({args.to_unit_label} "
                f"to {args.from_unit_label})."
            ),
        }

        ai_output = generate_child_content(payload)

        # Optional length validation for child pages
        if args.validate_lengths or args.strict_lengths:
            issues = validate_child_lengths(ai_output)
            if issues and args.auto_regen_failed_sections:
                ai_output, issues = regen_until_valid(call_model, payload, ai_output, max_rounds=args.regen_rounds)

            if issues:
                msg = "\n".join(["Length validation issues:"] + issues)
                if args.strict_lengths:
                    raise SystemExit(msg)
                else:
                    print(msg)

        if args.mode == "raw":
            write_or_print(ai_output.model_dump_json(indent=2, ensure_ascii=False), args.out)
            raise SystemExit(0)

        # build mongo doc for both mongo/html
        slug = f"{args.from_unit_code.lower().replace('_', '-')}-to-{args.to_unit_code.lower().replace('_', '-')}"
        url_path = f"/area-convertor/{slug}"

        mongo_doc = build_child_mongo_doc(
            ai_output,
            parent_slug="area-convertor",
            slug=slug,
            url_path=url_path,
            from_unit_code=args.from_unit_code,
            to_unit_code=args.to_unit_code,
            from_unit_label=args.from_unit_label,
            to_unit_label=args.to_unit_label,
        )

        if args.mode == "mongo":
            write_or_print(json.dumps(mongo_doc, default=str, indent=2, ensure_ascii=False), args.out)
        else:
            html = render_html("child", mongo_doc)
            write_or_print(html, args.out)