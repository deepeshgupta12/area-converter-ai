# src/models.py
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ----------------------------
# Inputs
# ----------------------------
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


# ----------------------------
# Child Outputs (RAW)
# ----------------------------
class ChildFAQ(BaseModel):
    question: str
    answer_html: str


class ChildPageOutput(BaseModel):
    seo_meta_title: str
    seo_meta_description: str
    h1_heading: str

    why_convert_section_html: str
    from_unit_section_html: str
    to_unit_section_html: str

    examples_section_html: str
    technical_details_html: str

    faqs: List[Dict[str, str]]


# ----------------------------
# Landing Outputs (RAW)
# ----------------------------
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