# src/validation.py
import re
from typing import List

from .models import ChildPageOutput


def html_word_count(html: str) -> int:
    """Rough word count: strip tags and split on whitespace."""
    if not html:
        return 0
    # remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return 0
    return len(text.split(" "))


def validate_child_lengths(child: ChildPageOutput) -> List[str]:
    """
    Returns a list of human-readable validation issues for word-count ranges.
    If list is empty, everything is within the desired ranges.
    """
    issues: List[str] = []

    # Why convert
    wc_why = html_word_count(child.why_convert_section_html)
    if not (220 <= wc_why <= 260):
        issues.append(f"why_convert_section_html: {wc_why} words (expected 220–260).")

    # From unit
    wc_from = html_word_count(child.from_unit_section_html)
    if not (230 <= wc_from <= 290):
        issues.append(f"from_unit_section_html: {wc_from} words (expected 230–290).")

    # To unit
    wc_to = html_word_count(child.to_unit_section_html)
    if not (230 <= wc_to <= 290):
        issues.append(f"to_unit_section_html: {wc_to} words (expected 230–290).")

    # Examples
    wc_examples = html_word_count(child.examples_section_html)
    if not (90 <= wc_examples <= 200):
        issues.append(f"examples_section_html: {wc_examples} words (expected 90–200).")

    # Technical
    wc_tech = html_word_count(child.technical_details_html)
    if not (150 <= wc_tech <= 200):
        issues.append(f"technical_details_html: {wc_tech} words (expected 150–200).")

    # FAQ answers
    for idx, faq in enumerate(child.faqs):
        wc_ans = html_word_count(faq.get("answer_html", ""))
        if not (90 <= wc_ans <= 140):
            issues.append(
                f"faqs[{idx}].answer_html: {wc_ans} words (expected 90–140)."
            )

    return issues