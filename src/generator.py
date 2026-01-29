# src/generator.py
import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional, List

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
from .section_regen import regen_until_valid

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
    ctx = injected_context if injected_context is not None else landing_input.landing_context
    text = template.replace(
        "{{landing_context_json}}",
        json.dumps(ctx or {}, ensure_ascii=False, indent=2),
    )
    return text


# -------------------------
# OpenAI call / JSON parsing
# -------------------------
def _extract_text_from_response(response: Any) -> str:
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


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.replace("```json", "").replace("```", "").strip()
    return t


def _extract_first_json_object(text: str) -> str:
    s = text.strip()
    start = s.find("{")
    if start == -1:
        return s

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]

    return s[start:]


def _responses_create_compat(create_kwargs: Dict[str, Any]) -> Any:
    """
    Backward compatible wrapper:
    - Some OpenAI SDKs reject response_format and/or max_output_tokens.
    - We retry by removing unsupported keys.
    """
    try:
        return client.responses.create(**create_kwargs)
    except TypeError as e:
        msg = str(e)

        # Remove response_format if unsupported
        if "response_format" in msg and "unexpected keyword argument" in msg:
            create_kwargs.pop("response_format", None)

        # Remove max_output_tokens if unsupported
        if "max_output_tokens" in msg and "unexpected keyword argument" in msg:
            create_kwargs.pop("max_output_tokens", None)

        # Retry once after removing unsupported args
        return client.responses.create(**create_kwargs)


def call_model(prompt: str) -> Dict[str, Any]:
    create_kwargs: Dict[str, Any] = {
        "model": settings.openai_model,
        "input": prompt,
        "temperature": settings.temperature,
    }

    if getattr(settings, "max_output_tokens", None):
        create_kwargs["max_output_tokens"] = settings.max_output_tokens

    # JSON mode (if your SDK supports it; otherwise compat wrapper will drop it)
    if getattr(settings, "use_json_mode", False) and getattr(settings, "json_mode_type", "json_object").lower() == "json_object":
        create_kwargs["response_format"] = {"type": "json_object"}

    response = _responses_create_compat(create_kwargs)

    text = _strip_code_fences(_extract_text_from_response(response))
    text = _extract_first_json_object(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        raise SystemExit(
            "Model did not return valid JSON.\n"
            f"JSON error: {e}\n\n"
            f"Raw output (first 2000 chars):\n{text[:2000]}"
        )


# -------------------------
# HTML rendering
# -------------------------
def render_html(mode_type: Literal["landing", "child"], mongo_doc: Dict[str, Any]) -> str:
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
    parser.add_argument("--output_file", dest="out", help="Alias for --out")

    # Landing inputs (CSV-driven) — keep your existing landing flow
    parser.add_argument("--search_volume_csv", type=str, default=None)
    parser.add_argument("--conversion_master_csv", type=str, default=None)
    parser.add_argument("--conversion_matrix_csv", dest="conversion_master_csv", help="Alias for --conversion_master_csv")

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
        raise SystemExit("Landing flow not shown here; keep your existing landing implementation.")

    # Child
    if not (args.from_unit_code and args.to_unit_code and args.from_unit_label and args.to_unit_label):
        raise SystemExit("For child type, you must provide from/to unit codes and labels.")

    payload = {
        "from_unit_code": args.from_unit_code,
        "to_unit_code": args.to_unit_code,
        "from_unit_label": args.from_unit_label,
        "to_unit_label": args.to_unit_label,
        "factor_to_unit": args.factor_to_unit,
        "from_unit_symbol": args.from_unit_symbol,
        "to_unit_symbol": args.to_unit_symbol,
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
        write_or_print(ai_output.model_dump_json(indent=2, ensure_ascii=False, by_alias=True), args.out)
        raise SystemExit(0)

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