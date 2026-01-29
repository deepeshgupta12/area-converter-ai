# src/section_regen.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .models import ChildPageOutput
from .validation import validate_child_lengths


# -------------------------
# Helpers
# -------------------------
def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _issue_to_section_keys(issues: List[str]) -> List[str]:
    """
    Map validation issue strings to regen section identifiers.

    These identifiers are used to build a contract and merge a snippet into the
    alias-shaped JSON (camelCase / nested keys).
    """
    keys: List[str] = []

    for msg in issues:
        if msg.startswith("hero.subtitle"):
            keys.append("hero.subtitle")

        elif msg.startswith("whyConvert.contentHtml"):
            keys.append("whyConvert")

        elif msg.startswith("majorUnitsExplained.fromUnitCard.descriptionHtml"):
            keys.append("majorUnitsExplained.fromUnitCard")

        elif msg.startswith("majorUnitsExplained.toUnitCard.descriptionHtml"):
            keys.append("majorUnitsExplained.toUnitCard")

        elif msg.startswith("technicalBackground.technicalExplanationHtml"):
            keys.append("technicalBackground.technicalExplanationHtml")

        elif msg.startswith("technicalBackground.precisionNotesHtml"):
            keys.append("technicalBackground.precisionNotesHtml")

        elif msg.startswith("faqs[") or msg.startswith("faqs should contain"):
            keys.append("faqs")  # regen all FAQs if any fails

        elif msg.startswith("quickConversionReference.rows"):
            keys.append("quickConversionReference.rows")

        elif msg.startswith("realWorldExamples.cards"):
            keys.append("realWorldExamples.cards")

    return _dedupe_keep_order(keys)


def _require(snippet: Dict[str, Any], key: str, section_key: str) -> Any:
    if key not in snippet:
        raise ValueError(f"Regen snippet missing required key '{key}' for section '{section_key}'. Got keys: {list(snippet.keys())}")
    return snippet[key]


def build_regen_prompt(
    child_input: Dict[str, Any],
    current_child_json_alias: Dict[str, Any],
    section_key: str,
) -> str:
    """
    Build a strict prompt for regenerating ONLY ONE SECTION.
    Must return a JSON snippet with ALIAS keys (camelCase).
    """
    ctx = {
        "fromUnitLabel": child_input.get("from_unit_label"),
        "toUnitLabel": child_input.get("to_unit_label"),
        "fromUnitSymbol": child_input.get("from_unit_symbol"),
        "toUnitSymbol": child_input.get("to_unit_symbol"),
        "factorToUnit": child_input.get("factor_to_unit"),
        "fromUnitRegion": child_input.get("from_unit_region") or "Pan-India",
        "toUnitRegion": child_input.get("to_unit_region") or "Pan-India",
        "cityName": child_input.get("city_name") or "Pan-India",
        "directionNote": child_input.get("direction_note") or "",
    }

    # IMPORTANT: Contracts MUST match your models.py aliases and child_prompt schema.
    # Also: Aim mid-band to reduce repeated failures.
    contract_map = {
        "hero.subtitle": (
            'Return ONLY JSON: {"subtitle": "..."}.\n'
            "- subtitle MUST be 50–56 words (plain text, no HTML).\n"
            "- Make it directional and India + real estate relevant.\n"
            "- Avoid being too short; add 1 extra context sentence if needed."
        ),

        "whyConvert": (
            'Return ONLY JSON: {"contentHtml": "...", "commonUseCases": ["...","...","...","..."], "conversionCard": {"left":"...","right":"..."}}.\n'
            "- contentHtml MUST be 230–260 words (HTML, 2–3 paragraphs + one short <ul>).\n"
            "- commonUseCases MUST be exactly 4 strings.\n"
            "- conversionCard.left/right must match factor and symbols, e.g., '1 m²' and '10.7639 ft²'.\n"
            "- Include contexts for: first-time buyer, upgrader, investor, broker/agent, developer docs.\n"
        ),

        "majorUnitsExplained.fromUnitCard": (
            'Return ONLY JSON: {"descriptionHtml":"...","whereUsedBullets":["...","...","...","..."],"quickEquivalence":"..."}.\n'
            "- descriptionHtml MUST be 220–260 words (HTML).\n"
            "- Must include: India real estate usage, origin/history, states/regions (only if relevant), and domains.\n"
            "- whereUsedBullets MUST be exactly 4 bullets.\n"
            "- quickEquivalence must be directional and include symbols."
        ),

        "majorUnitsExplained.toUnitCard": (
            'Return ONLY JSON: {"descriptionHtml":"...","whereUsedBullets":["...","...","...","..."],"quickEquivalence":"..."}.\n'
            "- descriptionHtml MUST be 220–260 words (HTML).\n"
            "- Must include: India real estate usage, origin/history, states/regions (only if relevant), and domains.\n"
            "- whereUsedBullets MUST be exactly 4 bullets.\n"
            "- quickEquivalence must be directional and include symbols."
        ),

        "technicalBackground.technicalExplanationHtml": (
            'Return ONLY JSON: {"technicalExplanationHtml":"..."}.\n'
            "- MUST be 170–185 words (HTML).\n"
            "- Explain factor intuition + why round-off happens + directional phrasing."
        ),

        "technicalBackground.precisionNotesHtml": (
            'Return ONLY JSON: {"precisionNotesHtml":"..."}.\n'
            "- MUST be 55–70 words (HTML).\n"
            "- Mention rounding, measurement standards, and using official documents if legal/loan context."
        ),

        "faqs": (
            'Return ONLY JSON: {"faqs":[{"question":"...","answerHtml":"..."}, ...]}.\n'
            "- MUST be exactly 10 FAQs.\n"
            "- Each answerHtml MUST be 75–95 words (HTML, usually 1 <p> + optional 1 short <ul>).\n"
            "- Questions must feel like real user queries in India property context.\n"
            "- Keep them directional; avoid mirrored phrasing that would fit the reverse page."
        ),

        "quickConversionReference.rows": (
            'Return ONLY JSON: {"rows":[{"from":10,"to":107.639,"commonUse":"..."}, ...]}.\n'
            "- MUST be exactly 8 rows.\n"
            "- from values should be sensible (10, 25, 50, 100, 150, 200, 500, 1000 when appropriate).\n"
            "- to MUST be numeric and computed using the factorToUnit (round to 4 decimals max).\n"
            "- commonUse must be a short realistic usage note."
        ),

        "realWorldExamples.cards": (
            'Return ONLY JSON: {"cards":[{"title":"Small Apartment","fromValue":"...","toValue":"...","note":"..."}, ...]}.\n'
            "- MUST be exactly 3 cards.\n"
            "- Keep titles as: Small Apartment, Family Home, Big Apartment.\n"
            "- fromValue/toValue must include units & symbols and be directional.\n"
            "- note should explain why this example matters (India listing/plan/negotiation context)."
        ),
    }

    if section_key not in contract_map:
        raise ValueError(f"Unknown section_key: {section_key}")

    contract = contract_map[section_key]

    # Provide current JSON for tone continuity but instruct not to copy.
    # Keep this bounded to avoid huge prompts.
    current_preview = json.dumps(current_child_json_alias, ensure_ascii=False)
    current_preview = current_preview[:3500]

    return f"""
You are regenerating ONLY ONE SECTION of a Square Yards India area conversion CHILD page.

SECTION TO REGENERATE: {section_key}

STRICT OUTPUT RULES:
- Output ONLY valid JSON for the section snippet. No markdown, no extra text.
- Use keys EXACTLY as required by the contract (camelCase like contentHtml, answerHtml, commonUseCases).
- Keep it strictly directional: {ctx["fromUnitLabel"]} → {ctx["toUnitLabel"]}. Do not write reversible copy.
- Do not fabricate facts beyond general, widely-known context; stay within real estate usage norms.
- Use the provided factorToUnit if numeric.

INPUT CONTEXT:
{json.dumps(ctx, ensure_ascii=False, indent=2)}

SECTION CONTRACT:
{contract}

CURRENT PAGE JSON (for tone consistency; DO NOT copy verbatim):
{current_preview}
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
    """
    Merge regen snippet into the alias-shaped full page JSON.
    """
    out = json.loads(json.dumps(child_json_alias))  # deep copy

    if section_key == "hero.subtitle":
        subtitle = _require(snippet, "subtitle", section_key)
        _set_path(out, ["hero", "subtitle"], subtitle)

    elif section_key == "whyConvert":
        # snippet: contentHtml, commonUseCases, conversionCard
        content = _require(snippet, "contentHtml", section_key)
        _set_path(out, ["whyConvert", "contentHtml"], content)

        cuc = snippet.get("commonUseCases")
        if cuc is not None:
            _set_path(out, ["whyConvert", "commonUseCases"], cuc)

        cc = snippet.get("conversionCard")
        if cc is not None:
            _set_path(out, ["whyConvert", "conversionCard"], cc)

    elif section_key == "majorUnitsExplained.fromUnitCard":
        desc = _require(snippet, "descriptionHtml", section_key)
        _set_path(out, ["majorUnitsExplained", "fromUnitCard", "descriptionHtml"], desc)

        wub = snippet.get("whereUsedBullets")
        if wub is not None:
            _set_path(out, ["majorUnitsExplained", "fromUnitCard", "whereUsedBullets"], wub)

        qe = snippet.get("quickEquivalence")
        if qe is not None:
            _set_path(out, ["majorUnitsExplained", "fromUnitCard", "quickEquivalence"], qe)

    elif section_key == "majorUnitsExplained.toUnitCard":
        desc = _require(snippet, "descriptionHtml", section_key)
        _set_path(out, ["majorUnitsExplained", "toUnitCard", "descriptionHtml"], desc)

        wub = snippet.get("whereUsedBullets")
        if wub is not None:
            _set_path(out, ["majorUnitsExplained", "toUnitCard", "whereUsedBullets"], wub)

        qe = snippet.get("quickEquivalence")
        if qe is not None:
            _set_path(out, ["majorUnitsExplained", "toUnitCard", "quickEquivalence"], qe)

    elif section_key == "technicalBackground.technicalExplanationHtml":
        val = _require(snippet, "technicalExplanationHtml", section_key)
        _set_path(out, ["technicalBackground", "technicalExplanationHtml"], val)

    elif section_key == "technicalBackground.precisionNotesHtml":
        val = _require(snippet, "precisionNotesHtml", section_key)
        _set_path(out, ["technicalBackground", "precisionNotesHtml"], val)

    elif section_key == "faqs":
        faqs = _require(snippet, "faqs", section_key)
        _set_path(out, ["faqs"], faqs)

    elif section_key == "quickConversionReference.rows":
        rows = _require(snippet, "rows", section_key)
        _set_path(out, ["quickConversionReference", "rows"], rows)

    elif section_key == "realWorldExamples.cards":
        cards = _require(snippet, "cards", section_key)
        _set_path(out, ["realWorldExamples", "cards"], cards)

    else:
        raise ValueError(f"Unhandled section_key: {section_key}")

    return out


def regen_until_valid(
    call_model_fn,
    child_input: Dict[str, Any],
    child_output: ChildPageOutput,
    max_rounds: int = 3,
) -> Tuple[ChildPageOutput, List[str]]:
    """
    Regen flow:
    - Work ONLY on alias-shaped dict to avoid snake/camel mismatch.
    - After each round merge, validate by rebuilding ChildPageOutput then running validate_child_lengths().
    """
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