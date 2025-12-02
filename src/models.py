# src/models.py
from pydantic import BaseModel
from typing import List, Literal, Optional


PageType = Literal["landing", "child"]


class LandingPageInput(BaseModel):
    page_type: Literal["landing"] = "landing"
    # You can extend later with more SEO hints if needed
    target_country: str = "India"
    primary_use_cases: List[str] = ["real estate", "construction", "land measurement"]


class LandingPageOutput(BaseModel):
    seo_meta_title: str
    seo_meta_description: str
    h1_heading: str

    # Textual sections (mapped to your Mongo fields)
    description_section_html: str
    highlight_blocks: List[dict]  # [{heading, subheading}, ...]

    major_units_copy_html: str
    formulas_section_html: str
    faqs: List[dict]  # [{question, answer_html}, ...]


class ChildPageInput(BaseModel):
    page_type: Literal["child"] = "child"

    from_unit_code: str
    to_unit_code: str
    from_unit_label: str
    to_unit_label: str
    factor_to_unit: Optional[float] = None  # 1 FROM ≈ X TO

    # NEW: region/city context for SEO + examples
    from_unit_region: Optional[str] = None    # e.g. "Assam", "Pan-India"
    to_unit_region: Optional[str] = None      # e.g. "Pan-India"
    city_name: Optional[str] = None           # e.g. "Mumbai", "Lucknow"

    # Optional direction note (we’ll auto-fill in code; model keeps it explicit)
    direction_note: Optional[str] = None


class ChildPageOutput(BaseModel):
    seo_meta_title: str
    seo_meta_description: str
    h1_heading: str

    why_convert_section_html: str
    from_unit_section_html: str
    to_unit_section_html: str
    examples_section_html: str
    technical_details_html: str
    faqs: List[dict]