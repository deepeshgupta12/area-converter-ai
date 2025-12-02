# src/section_regen.py
import json
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI

from .config.settings import settings

load_dotenv()

if not settings.openai_api_key:
    raise RuntimeError("OPENAI_API_KEY is not set.")

client = OpenAI(api_key=settings.openai_api_key)

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"


SectionName = Literal[
    "why_convert",
    "from_unit",
    "to_unit",
    "examples",
    "technical",
    "faq_block",
]


def load_base_child_prompt() -> str:
    """We reuse the main child prompt as context, then ask to regenerate just one section."""
    path = PROMPTS_DIR / "child_prompt.txt"
    return path.read_text(encoding="utf-8")


def build_section_regen_prompt(
    section: SectionName,
    *,
    from_unit_code: str,
    to_unit_code: str,
    from_unit_label: str,
    to_unit_label: str,
    factor_to_unit: float | None,
    from_unit_region: str | None,
    to_unit_region: str | None,
    city_name: str | None,
) -> str:
    base_context = load_base_child_prompt()

    directional_note = (
        f"This is a SECTION REGENERATION request. "
        f"You must ONLY regenerate the section '{section}' for a page that converts "
        f"FROM {from_unit_label} TO {to_unit_label}. "
        f"Do not change the direction and do not generate the full JSON. "
        f"Return ONLY a JSON object with a single key matching the section."
    )

    # small description per section
    section_instruction_map = {
        "why_convert": "Regenerate the WHY CONVERT section html, respecting the 220–260 word constraint.",
        "from_unit": "Regenerate the FROM UNIT section html ('What is FROM'), 230–290 words, with history and usage domains.",
        "to_unit": "Regenerate the TO UNIT section html ('What is TO'), 230–290 words, with history and usage domains.",
        "examples": "Regenerate the EXAMPLES section html, 90–200 words, with 3–5 practical conversions.",
        "technical": "Regenerate the TECHNICAL DETAILS section html, 150–200 words, with a clear explanation.",
        "faq_block": "Regenerate the entire FAQ block as an array of 4–5 FAQs (question + answer_html), each answer 90–140 words.",
    }

    section_note = section_instruction_map[section]

    factor_str = "N/A" if factor_to_unit is None else str(factor_to_unit)
    from_region = from_unit_region or "Pan-India"
    to_region = to_unit_region or "Pan-India"
    city = city_name or "a major Indian city"

    # We don't need whole base prompt, but including ensures same style.
    return f"""
{base_context}

{directional_note}

Use the following context:
- FROM unit code: {from_unit_code}
- FROM unit label: {from_unit_label}
- FROM unit region: {from_region}
- TO unit code: {to_unit_code}
- TO unit label: {to_unit_label}
- TO unit region: {to_region}
- Approximate factor (1 FROM ≈ X TO): {factor_str}
- Primary city context: {city}

{section_note}

Output format:
Return a single JSON object with:
- If section = "why_convert": key "why_convert_section_html"
- If section = "from_unit": key "from_unit_section_html"
- If section = "to_unit": key "to_unit_section_html"
- If section = "examples": key "examples_section_html"
- If section = "technical": key "technical_details_html"
- If section = "faq_block": key "faqs" (array of objects with question and answer_html)

Do NOT wrap the JSON in backticks.
    """.strip()


def call_model(prompt: str) -> dict:
    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    text = response.output[0].content[0].text
    return json.loads(text)


def regenerate_section(
    section: SectionName,
    *,
    from_unit_code: str,
    to_unit_code: str,
    from_unit_label: str,
    to_unit_label: str,
    factor_to_unit: float | None,
    from_unit_region: str | None,
    to_unit_region: str | None,
    city_name: str | None,
) -> dict:
    prompt = build_section_regen_prompt(
        section,
        from_unit_code=from_unit_code,
        to_unit_code=to_unit_code,
        from_unit_label=from_unit_label,
        to_unit_label=to_unit_label,
        factor_to_unit=factor_to_unit,
        from_unit_region=from_unit_region,
        to_unit_region=to_unit_region,
        city_name=city_name,
    )
    return call_model(prompt)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate a specific child-page section.")
    parser.add_argument("--section", required=True, choices=[
        "why_convert",
        "from_unit",
        "to_unit",
        "examples",
        "technical",
        "faq_block",
    ])

    parser.add_argument("--from_unit_code", required=True)
    parser.add_argument("--to_unit_code", required=True)
    parser.add_argument("--from_unit_label", required=True)
    parser.add_argument("--to_unit_label", required=True)
    parser.add_argument("--factor_to_unit", type=float)
    parser.add_argument("--from_unit_region", type=str)
    parser.add_argument("--to_unit_region", type=str)
    parser.add_argument("--city_name", type=str)

    args = parser.parse_args()

    out = regenerate_section(
        section=args.section,
        from_unit_code=args.from_unit_code,
        to_unit_code=args.to_unit_code,
        from_unit_label=args.from_unit_label,
        to_unit_label=args.to_unit_label,
        factor_to_unit=args.factor_to_unit,
        from_unit_region=args.from_unit_region,
        to_unit_region=args.to_unit_region,
        city_name=args.city_name,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))