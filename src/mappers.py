# src/mappers.py
from __future__ import annotations

from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)

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
            "canonicalUrl": f"{canonical_base.rstrip('/')}/{slug}",
        },
        "hero": {
            "h1": ai_output.h1_heading,
            "subheading2Liner": ai_output.h1_subheading_2liner,
        },
        "whatIsAreaConverter": {
            "sectionTitle": ai_output.what_is_section_title,
            "descriptionHtml": ai_output.what_is_description_html,
            "cards": [
                {"cardKey": c.card_key, "title": c.title, "description": c.description}
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
            {"question": f.question, "answerHtml": f.answer_html, "isActive": True, "sortOrder": i + 1}
            for i, f in enumerate(ai_output.faqs)
        ],
    }


def build_child_mongo_doc(
    ai: ChildPageOutput,
    *,
    parent_slug: str,
    slug: str,
    url_path: str,
    from_unit_code: str,
    to_unit_code: str,
    from_unit_label: str,
    to_unit_label: str,
    locale: str = "en-IN",
    site_code: str = "sqy-india-web",
    canonical_base: str = "https://www.squareyards.com",
    status: str = "draft",
    version: int = 1,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    canonical_url = canonical_base.rstrip("/") + url_path

    return {
        "parentSlug": parent_slug,
        "slug": slug,
        "urlPath": url_path,
        "pageType": "child",
        "fromUnitCode": from_unit_code,
        "toUnitCode": to_unit_code,
        "locale": locale,
        "siteCode": site_code,
        "status": status,
        "version": version,
        "createdAt": now,
        "updatedAt": now,
        "seo": {
            "metaTitle": ai.seo.meta_title,
            "metaDescription": ai.seo.meta_description,
            "h1Heading": ai.seo.h1_heading,
            "canonicalUrl": canonical_url,
        },
        "hero": {
            "slug": ai.hero.slug,
            "h1": ai.hero.h1,
            "subtitle": ai.hero.subtitle,
            "fromUnit": {
                "code": ai.hero.from_unit.code,
                "name": ai.hero.from_unit.name,
                "symbol": ai.hero.from_unit.symbol,
                "region": ai.hero.from_unit.region,
            },
            "toUnit": {
                "code": ai.hero.to_unit.code,
                "name": ai.hero.to_unit.name,
                "symbol": ai.hero.to_unit.symbol,
                "region": ai.hero.to_unit.region,
            },
            "oneFromEquals": ai.hero.one_from_equals,
            "cityContext": ai.hero.city_context,
        },
        "whyConvertSection": {
            "sectionHeading": ai.why_convert.heading,
            "explanationHtml": ai.why_convert.content_html,
            "commonUseCases": ai.why_convert.common_use_cases,
            "conversionCard": {
                "left": ai.why_convert.conversion_card.left,
                "right": ai.why_convert.conversion_card.right,
            },
        },
        "majorUnitsExplainedSection": {
            "fromUnitCard": {
                "title": ai.major_units_explained.from_unit_card.title,
                "descriptionHtml": ai.major_units_explained.from_unit_card.description_html,
                "whereUsedBullets": ai.major_units_explained.from_unit_card.where_used_bullets,
                "quickEquivalence": ai.major_units_explained.from_unit_card.quick_equivalence,
            },
            "toUnitCard": {
                "title": ai.major_units_explained.to_unit_card.title,
                "descriptionHtml": ai.major_units_explained.to_unit_card.description_html,
                "whereUsedBullets": ai.major_units_explained.to_unit_card.where_used_bullets,
                "quickEquivalence": ai.major_units_explained.to_unit_card.quick_equivalence,
            },
        },
        "realWorldExamplesSection": {
            "heading": ai.real_world_examples.heading,
            "cards": [
                {"title": c.title, "fromValue": c.from_value, "toValue": c.to_value, "note": c.note}
                for c in ai.real_world_examples.cards
            ],
        },
        "technicalBackgroundSection": {
            "heading": ai.technical_background.heading,
            "technicalExplanationHtml": ai.technical_background.technical_explanation_html,
            "differencesBullets": ai.technical_background.differences_bullets,
            "precisionNotesHtml": ai.technical_background.precision_notes_html,
        },
        "quickConversionReferenceSection": {
            "heading": ai.quick_conversion_reference.heading,
            "columns": ai.quick_conversion_reference.columns,
            "rows": [
                {"from": r.from_value, "to": r.to_value, "commonUse": r.common_use}
                for r in ai.quick_conversion_reference.rows
            ],
        },
        "faqs": [
            {"question": f.question, "answerHtml": f.answer_html, "isActive": True, "sortOrder": i}
            for i, f in enumerate(ai.faqs, start=1)
        ],
        "pageSettings": {
            "noIndex": False,
            "includeInSitemap": True,
            "enableSchemaMarkup": True,
            "showBreadcrumbs": True,
            "pagePriority": 0.7,
            "changeFrequency": "monthly",
        },
    }