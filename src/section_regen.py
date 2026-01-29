# src/section_regen.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .models import ChildPageOutput
from .validation import validate_child_lengths


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _issue_to_section_keys(issues: List[str]) -> List[str]:
    keys: List[str] = []
    for msg in issues:
        if msg.startswith("hero.subtitle"):
            keys.append("hero.subtitle")
        elif msg.startswith("whyConvert.contentHtml"):
            keys.append("whyConvert.contentHtml")
        elif msg.startswith("majorUnitsExplained.fromUnitCard.descriptionHtml"):
            keys.append("majorUnitsExplained.fromUnitCard")
        elif msg.startswith("majorUnitsExplained.toUnitCard.descriptionHtml"):
            keys.append("majorUnitsExplained.toUnitCard")
        elif msg.startswith("technicalBackground.technicalExplanationHtml"):
            keys.append("technicalBackground.technicalExplanationHtml")
        elif msg.startswith("technicalBackground.precisionNotesHtml"):
            keys.append("technicalBackground.precisionNotesHtml")
        elif msg.startswith("faqs[") or msg.startswith("faqs should contain"):
            keys.append("faqs")
        elif msg.startswith("quickConversionReference.rows"):
            keys.append("quickConversionReference.rows")
        elif msg.startswith("realWorldExamples.cards"):
            keys.append("realWorldExamples.cards")
    return _dedupe_keep_order(keys)


def build_regen_prompt(
    child_input: Dict[str, Any],
    current_child_json_alias: Dict[str, Any],
    section_key: str,
) -> str:
    ctx = {
        "fromUnitLabel": child_input.get("from_unit_label"),
        "toUnitLabel": child_input.get("to_unit_label"),
        "fromUnitSymbol": child_input.get("from_unit_symbol"),
        "toUnitSymbol": child_input.get("to_unit_symbol"),
        "factorToUnit": child_input.get("factor_to_unit"),
        "fromUnitRegion": child_input.get("from_unit_region"),
        "toUnitRegion": child_input.get("to_unit_region"),
        "cityName": child_input.get("city_name"),
        "directionNote": child_input.get("direction_note"),
    }

    contract_map = {
        "hero.subtitle": (
            "Return JSON: {\"subtitle\": \"...\"}. "
            "subtitle MUST be 50–55 words plain text (no HTML, no newlines)."
        ),
        "whyConvert.contentHtml": (
            "Return JSON: {\"contentHtml\": \"...\", \"commonUseCases\": [\"...\",\"...\",\"...\",\"...\"]}. "
            "contentHtml MUST be 220–280 words (HTML). "
            "commonUseCases MUST be exactly 4 items (short, specific Indian real-estate contexts)."
        ),
        "majorUnitsExplained.fromUnitCard": (
            "Return JSON: {\"descriptionHtml\": \"...\", \"whereUsedBullets\": [\"...\",\"...\",\"...\",\"...\"]}. "
            "descriptionHtml MUST be 220–280 words (HTML). "
            "whereUsedBullets MUST be exactly 4 items."
        ),
        "majorUnitsExplained.toUnitCard": (
            "Return JSON: {\"descriptionHtml\": \"...\", \"whereUsedBullets\": [\"...\",\"...\",\"...\",\"...\"]}. "
            "descriptionHtml MUST be 220–280 words (HTML). "
            "whereUsedBullets MUST be exactly 4 items."
        ),
        "technicalBackground.technicalExplanationHtml": (
            "Return JSON: {\"technicalExplanationHtml\": \"...\"}. "
            "MUST be 160–190 words (HTML)."
        ),
        "technicalBackground.precisionNotesHtml": (
            "Return JSON: {\"precisionNotesHtml\": \"...\"}. "
            "MUST be 50–70 words (HTML)."
        ),
        "faqs": (
            "Return JSON: {\"faqs\": [{\"question\":\"...\",\"answerHtml\":\"...\"}, ...]}. "
            "MUST be exactly 10 FAQs. "
            "Each answerHtml MUST be 30–120 words (HTML) and MUST include exactly TWO <p> paragraphs. "
            "Do not use <ul> in FAQs. "
            "Each answer must include: (1) a real-estate context line (listing/doc/loan/valuation), "
            "(2) a directional conversion hint (from → to), and (3) a small practical note about rounding/units. "
            "Use India-first wording. No filler, but long enough to meet word count."
        ),
        "quickConversionReference.rows": (
            "Return JSON: {\"rows\": [{\"from\": 10, \"to\": 107.639, \"commonUse\": \"...\"}, ...]}. "
            "MUST be exactly 8 rows. Use sensible from-values for the unit scale."
        ),
        "realWorldExamples.cards": (
            "Return JSON: {\"cards\": [{\"title\":\"Small Apartment\",\"fromValue\":\"...\",\"toValue\":\"...\",\"note\":\"...\"}, ...]}. "
            "MUST be exactly 3 cards, titles must remain: Small Apartment, Family Home, Big Apartment. "
            "Keep values realistic and math-consistent with factorToUnit."
        ),
    }

    if section_key not in contract_map:
        raise ValueError(f"Unknown section_key: {section_key}")

    contract = contract_map[section_key]

    return f"""
You are regenerating ONLY ONE SECTION of a Square Yards India area conversion child page.

SECTION TO REGENERATE: {section_key}

STRICT OUTPUT RULES:
- Output ONLY valid JSON for the section snippet. No markdown. No extra keys.
- Do NOT include raw newlines inside JSON strings. If needed, use HTML <p> tags (but keep JSON string single-line).
- Use alias keys EXACTLY as requested (camelCase like contentHtml, answerHtml).
- Keep it directional: {ctx["fromUnitLabel"]} → {ctx["toUnitLabel"]}. Do not write reversible content.
- Mention {ctx["cityName"]} only if genuinely relevant; otherwise keep Pan-India phrasing.

SECTION CONTRACT:
{contract}

INPUT CONTEXT:
{json.dumps(ctx, ensure_ascii=False, indent=2)}

CURRENT PAGE JSON (for tone consistency, do not copy verbatim):
{json.dumps(current_child_json_alias, ensure_ascii=False)[:3500]}
""".strip()


def _set_path(d: Dict[str, Any], path: List[str], value: Any) -> None:
    cur = d
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
    cur[path[-1]] = value


def apply_regen_snippet_alias(
    child_json_alias: Dict[str, Any],
    section_key: str,
    snippet: Dict[str, Any],
) -> Dict[str, Any]:
    out = json.loads(json.dumps(child_json_alias))  # deep copy

    if section_key == "hero.subtitle":
        _set_path(out, ["hero", "subtitle"], snippet["subtitle"])

    elif section_key == "whyConvert.contentHtml":
        _set_path(out, ["whyConvert", "contentHtml"], snippet["contentHtml"])
        _set_path(out, ["whyConvert", "commonUseCases"], snippet["commonUseCases"])

    elif section_key == "majorUnitsExplained.fromUnitCard":
        _set_path(out, ["majorUnitsExplained", "fromUnitCard", "descriptionHtml"], snippet["descriptionHtml"])
        _set_path(out, ["majorUnitsExplained", "fromUnitCard", "whereUsedBullets"], snippet["whereUsedBullets"])

    elif section_key == "majorUnitsExplained.toUnitCard":
        _set_path(out, ["majorUnitsExplained", "toUnitCard", "descriptionHtml"], snippet["descriptionHtml"])
        _set_path(out, ["majorUnitsExplained", "toUnitCard", "whereUsedBullets"], snippet["whereUsedBullets"])

    elif section_key == "technicalBackground.technicalExplanationHtml":
        _set_path(out, ["technicalBackground", "technicalExplanationHtml"], snippet["technicalExplanationHtml"])

    elif section_key == "technicalBackground.precisionNotesHtml":
        _set_path(out, ["technicalBackground", "precisionNotesHtml"], snippet["precisionNotesHtml"])

    elif section_key == "faqs":
        _set_path(out, ["faqs"], snippet["faqs"])

    elif section_key == "quickConversionReference.rows":
        _set_path(out, ["quickConversionReference", "rows"], snippet["rows"])

    elif section_key == "realWorldExamples.cards":
        _set_path(out, ["realWorldExamples", "cards"], snippet["cards"])

    else:
        raise ValueError(f"Unhandled section_key: {section_key}")

    return out


def regen_until_valid(
    call_model_fn,
    child_input: Dict[str, Any],
    child_output: ChildPageOutput,
    max_rounds: int = 3,
) -> Tuple[ChildPageOutput, List[str]]:
    current_alias = child_output.model_dump(by_alias=True)
    issues = validate_child_lengths(child_output)

    if not issues:
        return child_output, []

    for _round in range(max_rounds):
        section_keys = _issue_to_section_keys(issues)
        if not section_keys:
            break

        for section_key in section_keys:
            prompt = build_regen_prompt(child_input, current_alias, section_key)
            snippet = call_model_fn(prompt)
            current_alias = apply_regen_snippet_alias(current_alias, section_key, snippet)

        updated = ChildPageOutput.model_validate(current_alias)
        issues = validate_child_lengths(updated)

        if not issues:
            return updated, []

    final_obj = ChildPageOutput.model_validate(current_alias)
    return final_obj, issues