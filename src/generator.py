# src/generator.py
import json
from pathlib import Path
from typing import Literal

from openai import OpenAI
from dotenv import load_dotenv

from .config.settings import settings
from .models import (
    LandingPageInput,
    ChildPageInput,
    LandingPageOutput,
    ChildPageOutput,
)
from .mappers import build_landing_mongo_doc, build_child_mongo_doc
from .validation import validate_child_lengths

# Load .env
load_dotenv()

client = OpenAI(api_key=settings.openai_api_key)

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"


def load_prompt(template_name: Literal["landing", "child"]) -> str:
    file_map = {
        "landing": PROMPTS_DIR / "landing_prompt.txt",
        "child": PROMPTS_DIR / "child_prompt.txt",
    }
    path = file_map[template_name]
    return path.read_text(encoding="utf-8")


def render_child_prompt(template: str, child_input: ChildPageInput) -> str:
    text = template
    text = text.replace("{{from_unit_code}}", child_input.from_unit_code)
    text = text.replace("{{from_unit_label}}", child_input.from_unit_label)
    text = text.replace("{{to_unit_code}}", child_input.to_unit_code)
    text = text.replace("{{to_unit_label}}", child_input.to_unit_label)

    text = text.replace(
        "{{factor_to_unit}}",
        str(child_input.factor_to_unit) if child_input.factor_to_unit is not None else "N/A",
    )
    text = text.replace(
        "{{from_unit_region}}",
        child_input.from_unit_region or "Pan-India",
    )
    text = text.replace(
        "{{to_unit_region}}",
        child_input.to_unit_region or "Pan-India",
    )
    text = text.replace(
        "{{city_name}}",
        child_input.city_name or "a major Indian city",
    )
    text = text.replace(
        "{{direction_note}}",
        child_input.direction_note or "",
    )
    return text


def render_landing_prompt(template: str, landing_input: LandingPageInput) -> str:
    # For now, we don't substitute much; we can enrich later
    return template


def call_model(prompt: str) -> dict:
    """
    Low-level wrapper to call OpenAI and return parsed JSON.
    We will refine this in the next step.
    """
    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    # Get the first text output
    text = response.output[0].content[0].text
    return json.loads(text)


def generate_landing_content(params: dict) -> LandingPageOutput:
    landing_input = LandingPageInput(**params)
    template = load_prompt("landing")
    prompt = render_landing_prompt(template, landing_input)
    raw = call_model(prompt)
    return LandingPageOutput(**raw)


def generate_child_content(params: dict) -> ChildPageOutput:
    child_input = ChildPageInput(**params)
    template = load_prompt("child")
    prompt = render_child_prompt(template, child_input)
    raw = call_model(prompt)
    return ChildPageOutput(**raw)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Area Converter Content Generator")
    parser.add_argument("--type", choices=["landing", "child"], required=True)
    parser.add_argument("--mode", choices=["raw", "mongo"], default="raw")
    

    # Child-specific args
    parser.add_argument("--from_unit_code", type=str)
    parser.add_argument("--to_unit_code", type=str)
    parser.add_argument("--from_unit_label", type=str)
    parser.add_argument("--to_unit_label", type=str)
    parser.add_argument("--factor_to_unit", type=float)
    parser.add_argument("--from_unit_region", type=str)
    parser.add_argument("--to_unit_region", type=str)
    parser.add_argument("--city_name", type=str)

    # Validation flags (for child)
    parser.add_argument("--validate_lengths", action="store_true")
    parser.add_argument("--strict_lengths", action="store_true")

    args = parser.parse_args()

    if args.type == "landing":
        ai_output = generate_landing_content({})

        if args.mode == "raw":
            print(ai_output.model_dump_json(indent=2, ensure_ascii=False))
        else:
            mongo_doc = build_landing_mongo_doc(ai_output)
            print(json.dumps(mongo_doc, default=str, indent=2, ensure_ascii=False))

    else:
        if not (args.from_unit_code and args.to_unit_code and args.from_unit_label and args.to_unit_label):
            raise SystemExit("For child type, you must provide from/to unit codes and labels.")

        payload = {
                    "from_unit_code": args.from_unit_code,
                    "to_unit_code": args.to_unit_code,
                    "from_unit_label": args.from_unit_label,
                    "to_unit_label": args.to_unit_label,
                    "factor_to_unit": args.factor_to_unit,
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
            if issues:
                msg = "\n".join(["Length validation issues:"] + issues)
                if args.strict_lengths:
                    raise SystemExit(msg)
                else:
                    print(msg)

        if args.mode == "raw":
            print(ai_output.model_dump_json(indent=2, ensure_ascii=False))
        else:
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
            print(json.dumps(mongo_doc, default=str, indent=2, ensure_ascii=False))