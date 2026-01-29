# src/models.py
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================
# Inputs
# ============================================================

class LandingPageInput(BaseModel):
    locale: str = "en-IN"
    site_code: str = "sqy-india-web"
    slug: str = "area-convertor"
    canonical_base: str = "https://www.squareyards.com"
    landing_context: Dict[str, Any] = Field(default_factory=dict)


class ChildPageInput(BaseModel):
    from_unit_code: str
    to_unit_code: str
    from_unit_label: str
    to_unit_label: str
    factor_to_unit: Optional[float] = None
    from_unit_region: Optional[str] = None
    to_unit_region: Optional[str] = None
    city_name: Optional[str] = None
    direction_note: Optional[str] = None

    # NEW (needed for hero + UI parity with your screenshots)
    # If you don't pass these, prompt can still infer, but it's better to provide.
    from_unit_symbol: Optional[str] = None
    to_unit_symbol: Optional[str] = None


# ============================================================
# Child Outputs (RAW) — Enhanced schema for child pages
# This matches the new child prompt + validation.py you shared.
# ============================================================

class ChildSEO(BaseModel):
    meta_title: str = Field(..., alias="metaTitle")
    meta_description: str = Field(..., alias="metaDescription")
    h1_heading: str = Field(..., alias="h1Heading")


class ChildHeroUnit(BaseModel):
    code: str
    name: str
    symbol: str
    region: str


class ChildHero(BaseModel):
    slug: str
    h1: str
    subtitle: str  # ~45–60 words plain text

    from_unit: ChildHeroUnit = Field(..., alias="fromUnit")
    to_unit: ChildHeroUnit = Field(..., alias="toUnit")

    one_from_equals: str = Field(..., alias="oneFromEquals")
    city_context: str = Field(..., alias="cityContext")


class WhyConvertConversionCard(BaseModel):
    left: str
    right: str


class WhyConvertSection(BaseModel):
    heading: str
    content_html: str = Field(..., alias="contentHtml")  # 200–300 words HTML
    common_use_cases: List[str] = Field(default_factory=list, alias="commonUseCases")
    conversion_card: WhyConvertConversionCard = Field(..., alias="conversionCard")


class MajorUnitCard(BaseModel):
    title: str
    description_html: str = Field(..., alias="descriptionHtml")  # 200–300 words HTML
    where_used_bullets: List[str] = Field(default_factory=list, alias="whereUsedBullets")
    quick_equivalence: str = Field(..., alias="quickEquivalence")


class MajorUnitsExplainedSection(BaseModel):
    from_unit_card: MajorUnitCard = Field(..., alias="fromUnitCard")
    to_unit_card: MajorUnitCard = Field(..., alias="toUnitCard")


class RealWorldExampleCard(BaseModel):
    title: str
    from_value: str = Field(..., alias="fromValue")
    to_value: str = Field(..., alias="toValue")
    note: str


class RealWorldExamplesSection(BaseModel):
    heading: str
    cards: List[RealWorldExampleCard]  # exactly 3 cards


class TechnicalBackgroundSection(BaseModel):
    heading: str
    technical_explanation_html: str = Field(..., alias="technicalExplanationHtml")  # 150–200 words HTML
    differences_bullets: List[str] = Field(default_factory=list, alias="differencesBullets")
    precision_notes_html: str = Field(..., alias="precisionNotesHtml")  # 40–80 words HTML


class QuickConversionReferenceRow(BaseModel):
    from_value: float = Field(..., alias="from")
    to_value: float = Field(..., alias="to")
    common_use: str = Field(..., alias="commonUse")


class QuickConversionReferenceSection(BaseModel):
    heading: str
    columns: List[str]
    rows: List[QuickConversionReferenceRow]  # recommended 8 rows


class ChildFAQ(BaseModel):
    question: str
    answer_html: str = Field(..., alias="answerHtml")


class ChildPageOutput(BaseModel):
    # Top-level blocks
    seo: ChildSEO
    hero: ChildHero

    why_convert: WhyConvertSection = Field(..., alias="whyConvert")
    major_units_explained: MajorUnitsExplainedSection = Field(..., alias="majorUnitsExplained")
    real_world_examples: RealWorldExamplesSection = Field(..., alias="realWorldExamples")
    technical_background: TechnicalBackgroundSection = Field(..., alias="technicalBackground")
    quick_conversion_reference: QuickConversionReferenceSection = Field(..., alias="quickConversionReference")

    # Exactly 10 FAQs
    faqs: List[ChildFAQ]


# ============================================================
# Landing Outputs (RAW) — KEEP AS-IS (your current landing schema)
# ============================================================

class LandingCard(BaseModel):
    card_key: str
    title: str
    description: str


class UnitPill(BaseModel):
    label: str
    from_unit_code: Optional[str] = None
    to_unit_code: Optional[str] = None


class AllUnitsUnit(BaseModel):
    unit_name: str
    unit_symbol: str = ""
    one_liner: str
    where_used: str
    pills: List[UnitPill] = Field(default_factory=list)


class AllUnitsGroup(BaseModel):
    letter: str
    units: List[AllUnitsUnit]


class MajorUnitItem(BaseModel):
    unit_name: str
    unit_symbol: str = ""
    one_liner: str
    where_used: str
    conversion_label: str


class QuickRefRow(BaseModel):
    from_unit_label: str
    to_unit_label: str
    factor: float
    region: str
    usage: str


class LandingFAQ(BaseModel):
    question: str
    answer_html: str


class LandingPageOutput(BaseModel):
    # SEO
    seo_meta_title: str
    seo_meta_description: str
    h1_heading: str
    h1_subheading_2liner: str

    # What is area converter section
    what_is_section_title: str
    what_is_description_html: str
    what_is_cards: List[LandingCard]

    # All Units A–Z
    all_units_groups: List[AllUnitsGroup]

    # How Area Conversion Works (Square Yards)
    how_it_works_heading: str
    how_it_works_description_html: str
    how_it_works_formula_html: str
    how_it_works_example_html: str

    # Major Units Explained
    major_units: List[MajorUnitItem]

    # Quick Conversion Reference
    quick_ref_rows: List[QuickRefRow]

    # FAQs
    faqs: List[LandingFAQ]