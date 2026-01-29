# src/validation.py
from __future__ import annotations

import re
from typing import List

from .models import ChildPageOutput


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def _word_count_from_html(html: str) -> int:
    if not html:
        return 0
    # strip tags
    text = re.sub(r"<[^>]+>", " ", html)
    words = _WORD_RE.findall(text)
    return len(words)


def _word_count_plain(text: str) -> int:
    if not text:
        return 0
    return len(_WORD_RE.findall(text))


def validate_child_lengths(child: ChildPageOutput) -> List[str]:
    issues: List[str] = []

    # Hero subtitle: 45–60 words
    wc = _word_count_plain(child.hero.subtitle)
    if wc < 45 or wc > 60:
        issues.append(f"hero.subtitle should be ~45–60 words, got {wc}.")

    # Why convert: 200–300
    wc = _word_count_from_html(child.why_convert.content_html)
    if wc < 200 or wc > 300:
        issues.append(f"whyConvert.contentHtml should be 200–300 words, got {wc}.")

    # Major unit cards: 200–300 each
    wc = _word_count_from_html(child.major_units_explained.from_unit_card.description_html)
    if wc < 200 or wc > 300:
        issues.append(f"majorUnitsExplained.fromUnitCard.descriptionHtml should be 200–300 words, got {wc}.")

    wc = _word_count_from_html(child.major_units_explained.to_unit_card.description_html)
    if wc < 200 or wc > 300:
        issues.append(f"majorUnitsExplained.toUnitCard.descriptionHtml should be 200–300 words, got {wc}.")

    # Technical background: 150–200
    wc = _word_count_from_html(child.technical_background.technical_explanation_html)
    if wc < 150 or wc > 200:
        issues.append(f"technicalBackground.technicalExplanationHtml should be 150–200 words, got {wc}.")

    # Precision note: 40–80
    wc = _word_count_from_html(child.technical_background.precision_notes_html)
    if wc < 40 or wc > 80:
        issues.append(f"technicalBackground.precisionNotesHtml should be 40–80 words, got {wc}.")

    # FAQs: exactly 10
    if len(child.faqs) != 10:
        issues.append(f"faqs should contain exactly 10 items, got {len(child.faqs)}.")

    # FAQ answers: 60–120 words each
    for i, f in enumerate(child.faqs, start=1):
        wc = _word_count_from_html(f.answer_html)
        if wc < 30 or wc > 120:
            issues.append(f"faqs[{i}].answerHtml should be 60–120 words, got {wc}.")

    # Quick reference: 8 rows recommended
    if len(child.quick_conversion_reference.rows) != 8:
        issues.append(
            f"quickConversionReference.rows should contain 8 rows (recommended), got {len(child.quick_conversion_reference.rows)}."
        )

    # Real-world examples: exactly 3 cards
    if len(child.real_world_examples.cards) != 3:
        issues.append(f"realWorldExamples.cards should contain exactly 3 cards, got {len(child.real_world_examples.cards)}.")

    return issues