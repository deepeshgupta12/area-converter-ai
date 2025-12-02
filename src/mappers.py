# src/mappers.py
from datetime import datetime
from typing import Any, Dict

from .models import LandingPageOutput, ChildPageOutput


def build_landing_mongo_doc(
    ai: LandingPageOutput,
    *,
    slug: str = "area-convertor",
    locale: str = "en-IN",
    site_code: str = "sqy-india-web",
    status: str = "draft",
    version: int = 1,
) -> Dict[str, Any]:
    """
    Shapes the AI output into the Mongo document structure for area_converter_pages.
    """
    now = datetime.utcnow()

    doc: Dict[str, Any] = {
        "slug": slug,
        "pageType": "landing",
        "locale": locale,
        "siteCode": site_code,
        "status": status,
        "version": version,
        "createdAt": now,
        "updatedAt": now,
        # publishedAt can be set by CMS later
        "seo": {
            "metaTitle": ai.seo_meta_title,
            "metaDescription": ai.seo_meta_description,
            "h1Heading": ai.h1_heading,
            "canonicalUrl": f"https://www.squareyards.com/{slug}",
        },
        # From our LandingPageOutput
        "popularConversions": [],  # still managed manually via CMS
        "descriptionSection": {
            "sectionHeading": "About Our Area Converter Tool",
            "sectionSubheading": "Quick and accurate area conversions for Indian real estate",
            "mainDescriptionHtml": ai.description_section_html,
            "highlightBlocks": [
                {
                    "blockKey": f"BLOCK_{idx+1}",
                    "isVisible": True,
                    "heading": block["heading"],
                    "subheading": block["subheading"],
                    "sortOrder": idx + 1,
                }
                for idx, block in enumerate(ai.highlight_blocks)
            ],
        },
        "majorUnits": [],  # you’ll likely populate this from unit master + your own copy
        "formulasSection": {
            "showFormulasSection": True,
            "sectionTitle": "Common Area Conversion Formulas",
            "sectionDescription": ai.formulas_section_html,
            "formulaExamples": [],  # if you want, you can parse formulas into structured rows later
        },
        "faqs": [
            {
                "question": faq["question"],
                "answerHtml": faq["answer_html"],
                "isActive": True,
                "sortOrder": idx + 1,
            }
            for idx, faq in enumerate(ai.faqs)
        ],
    }

    return doc


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
    status: str = "draft",
    version: int = 1,
    last_updated_display_date: datetime | None = None,
) -> Dict[str, Any]:
    """
    Shapes the AI output into the Mongo document structure for area_converter_child_pages.
    """
    now = datetime.utcnow()
    last_display = last_updated_display_date or now

    doc: Dict[str, Any] = {
        "parentSlug": parent_slug,
        "slug": slug,
        "urlPath": url_path,
        "fromUnitCode": from_unit_code,
        "toUnitCode": to_unit_code,
        "locale": locale,
        "siteCode": site_code,
        "status": status,
        "version": version,
        "createdAt": now,
        "updatedAt": now,
        "lastUpdatedDisplayDate": last_display,
        "seo": {
            "metaTitle": ai.seo_meta_title,
            "metaDescription": ai.seo_meta_description,
            "h1Heading": ai.h1_heading,
            "canonicalUrl": f"https://www.squareyards.com{url_path}",
        },
        "popularConversions": [],  # can be filled from your India-unit master later
        "whyConvertSection": {
            "sectionHeading": f"Why convert {from_unit_label} to {to_unit_label}?",
            "explanationHtml": ai.why_convert_section_html,
        },
        "standaloneSections": [
            {
                "unitCode": from_unit_code,
                "sectionHeading": f"What is {from_unit_label}?",
                "descriptionHtml": ai.from_unit_section_html,
                "sectionKey": "fromUnit",
                "sortOrder": 1,
            },
            {
                "unitCode": to_unit_code,
                "sectionHeading": f"What is {to_unit_label}?",
                "descriptionHtml": ai.to_unit_section_html,
                "sectionKey": "toUnit",
                "sortOrder": 2,
            },
        ],
        "faqs": [
            {
                "question": faq["question"],
                "answerHtml": faq["answer_html"],
                "isActive": True,
                "sortOrder": idx + 1,
            }
            for idx, faq in enumerate(ai.faqs)
        ],
        "examplesSection": {
            "contentHtml": ai.examples_section_html,
        },
        "technicalDetailsSection": {
            "technicalExplanationHtml": ai.technical_details_html,
            "conversionTableRows": [],  # if you later auto-generate numeric rows, they go here
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

    return doc