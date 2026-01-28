# src/mappers.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from .models import LandingPageOutput, ChildPageOutput


def build_landing_mongo_doc(
    ai_output: LandingPageOutput,
    *,
    slug: str,
    locale: str,
    site_code: str,
    canonical_base: str,
) -> Dict[str, Any]:
    now = datetime.utcnow()

    return {
        "slug": slug,
        "pageType": "landing",
        "locale": locale,
        "siteCode": site_code,
        "status": "draft",
        "version": 1,
        "createdAt": now,
        "updatedAt": now,
        "seo": {
            "metaTitle": ai_output.seo_meta_title,
            "metaDescription": ai_output.seo_meta_description,
            "h1Heading": ai_output.h1_heading,
            "canonicalUrl": f"{canonical_base}/{slug}",
        },
        "hero": {
            "h1": ai_output.h1_heading,
            "subheading2Liner": ai_output.h1_subheading_2liner,
        },
        "whatIsAreaConverter": {
            "sectionTitle": ai_output.what_is_section_title,
            "descriptionHtml": ai_output.what_is_description_html,
            "cards": [
                {
                    "cardKey": c.card_key,
                    "title": c.title,
                    "description": c.description,
                }
                for c in ai_output.what_is_cards
            ],
        },
        "allUnitsAZ": [
            {
                "letter": g.letter,
                "units": [
                    {
                        "unitName": u.unit_name,
                        "unitSymbol": u.unit_symbol,
                        "oneLiner": u.one_liner,
                        "whereUsed": u.where_used,
                        "pills": [{"label": p.label} for p in u.pills],
                    }
                    for u in g.units
                ],
            }
            for g in ai_output.all_units_groups
        ],
        "howAreaConversionWorks": {
            "sectionHeading": ai_output.how_it_works_heading,
            "descriptionHtml": ai_output.how_it_works_description_html,
            "formulaHtml": ai_output.how_it_works_formula_html,
            "exampleHtml": ai_output.how_it_works_example_html,
        },
        "majorUnitsExplained": [
            {
                "unitName": m.unit_name,
                "unitSymbol": m.unit_symbol,
                "oneLiner": m.one_liner,
                "whereUsed": m.where_used,
                "conversionLabel": m.conversion_label,
            }
            for m in ai_output.major_units
        ],
        "quickConversionReference": {
            "rows": [
                {
                    "fromUnitLabel": r.from_unit_label,
                    "toUnitLabel": r.to_unit_label,
                    "factor": r.factor,
                    "region": r.region,
                    "usage": r.usage,
                }
                for r in ai_output.quick_ref_rows
            ]
        },
        "faqs": [
            {
                "question": f.question,
                "answerHtml": f.answer_html,
                "isActive": True,
                "sortOrder": i + 1,
            }
            for i, f in enumerate(ai_output.faqs)
        ],
    }


def build_child_mongo_doc(
    ai_output: ChildPageOutput,
    *,
    parent_slug: str,
    slug: str,
    url_path: str,
    locale: str,
    site_code: str,
    canonical_base: str,
    from_unit_code: str,
    to_unit_code: str,
) -> Dict[str, Any]:
    now = datetime.utcnow()

    return {
        "parentSlug": parent_slug,
        "slug": slug,
        "urlPath": url_path,
        "fromUnitCode": from_unit_code,
        "toUnitCode": to_unit_code,
        "locale": locale,
        "siteCode": site_code,
        "status": "draft",
        "version": 1,
        "createdAt": now,
        "updatedAt": now,
        "lastUpdatedDisplayDate": now,
        "seo": {
            "metaTitle": ai_output.seo_meta_title,
            "metaDescription": ai_output.seo_meta_description,
            "h1Heading": ai_output.h1_heading,
            "canonicalUrl": f"{canonical_base}{url_path}",
        },
        "popularConversions": [],
        "whyConvertSection": {
            "sectionHeading": f"Why convert {from_unit_code} to {to_unit_code}?",
            "explanationHtml": ai_output.why_convert_section_html,
        },
        "standaloneSections": [
            {
                "unitCode": from_unit_code,
                "sectionHeading": f"What is {from_unit_code}?",
                "descriptionHtml": ai_output.from_unit_section_html,
                "sectionKey": "fromUnit",
                "sortOrder": 1,
            },
            {
                "unitCode": to_unit_code,
                "sectionHeading": f"What is {to_unit_code}?",
                "descriptionHtml": ai_output.to_unit_section_html,
                "sectionKey": "toUnit",
                "sortOrder": 2,
            },
        ],
        "faqs": [
            {
                "question": faq.get("question", ""),
                "answerHtml": faq.get("answer_html", ""),
                "isActive": True,
                "sortOrder": i + 1,
            }
            for i, faq in enumerate(ai_output.faqs)
        ],
        "examplesSection": {"contentHtml": ai_output.examples_section_html},
        "technicalDetailsSection": {
            "technicalExplanationHtml": ai_output.technical_details_html,
            "conversionTableRows": [],
            "precisionNotesHtml": "",
        },
        "pageSettings": {
            "noIndex": False,
            "includeInSitemap": True,
            "enableSchemaMarkup": True,
            "showBreadcrumbs": True,
            "pagePriority": 0.7,
            "changeFrequency": "monthly",
        },
    }