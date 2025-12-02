# Area Converter AI Content Generator

This repository contains a local tooling project that generates **SEO- and AEO-friendly content** for the Square Yards **Area Converter** ecosystem:

- Landing page: `/area-convertor`
- Child pages: `/area-convertor/{from}-to-{to}` (e.g. `sq-ft-to-sq-m`, `ankanam-to-acre`, etc.)

The tool uses an LLM to create **non-generic, India-focused** content that is:
- Unique per unit pair (sq ft → sq m ≠ sq m → sq ft)
- Understandable to a layperson (no jargon)
- Optimised for search engines (Muvera / SEO / AEO considerations)
- Structured for direct ingestion into a **MongoDB-backed CMS**

---

## Key Capabilities

- Generate **landing page** content in one shot (JSON or Mongo-shaped).
- Generate **child page** content for each unit pair:
  - `whyConvert` section
  - `what is FROM unit?` section
  - `what is TO unit?` section
  - examples block
  - technical details block
  - FAQs (multi-persona: first-time buyer, investor, broker, builder, lay user)
- Enforce **length and quality constraints** (e.g. 200–300 words for specific sections).
- Handle Indian real-estate context:
  - Recognises regional units (Ankanam, Bigha – Assam, etc.).
  - Distinguishes between regional vs Pan-India / global units (Acre, Hectare, Square Meter, Square Foot, Are, etc.).
- City-aware but **not city-biased**:
  - Uses `city_name` (e.g. Mumbai) as a context hint only.
  - Treats global units as Pan-India and uses cities as examples, not owners.
- Batch pipeline:
  - Reads a CSV mapping of units & factors (e.g. `AreaCalculation - Sheet2.csv`).
  - Generates content for all unit pairs.
  - Validates length constraints.
  - Optionally auto-regenerates weak sections.
  - Writes Mongo-ready JSON and/or HTML preview files for review.

---

## Project Structure

```text
area-converter-ai/
  ├─ src/
  │   ├─ generator.py
  │   │   # CLI for single-page generation (landing / child, JSON or Mongo mode)
  │   ├─ section_regen.py
  │   │   # Regenerate a single section for a given unit pair (why, what_is_from, faqs, etc.)
  │   ├─ config/
  │   │   └─ settings.py
  │   │       # Pydantic Settings: reads env vars like OPENAI_API_KEY, OPENAI_MODEL
  │   ├─ prompts/
  │   │   ├─ landing_prompt.txt
  │   │   └─ child_prompt.txt
  │   │       # Prompt templates for landing/child generators
  │   └─ models/
  │       # Pydantic models for outputs and Mongo document shapes
  │
  ├─ scripts/
  │   └─ batch_generate_children_from_csv.py
  │       # Batch pipeline:
  │       # - Read CSV with unit mapping + factors + regions + city hint
  │       # - Generate child content per pair
  │       # - Validate length + structure
  │       # - Optionally auto-regenerate sections
  │       # - Optionally write to Mongo
  │       # - Optionally write HTML preview pages
  │
  ├─ previews/              # Local HTML previews (gitignored)
  ├─ requirements.txt
  ├─ .gitignore
  └─ README.md
```

---

## Technology Stack

- **Python 3.10+**
- **pydantic v2 + pydantic-settings**
- **OpenAI-compatible LLM API** (configured via environment variables)
- **pandas** (for CSV processing)
- **pymongo** (for optional MongoDB writes)
- Local environment:
  - macOS (M1/ARM), `pyenv` + `venv` (developer’s setup)

---

## Setup

### 1. Clone & create virtual environment

```bash
git clone https://github.com/deepeshgupta12/area-converter-ai.git
cd area-converter-ai

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root (this file is gitignored):

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini          # or the model you are using
OPENAI_API_BASE=https://api.openai.com/v1   # if needed
```

`src/config/settings.py` uses `pydantic-settings` to load these.

If you are using a self-hosted or Azure-style endpoint, adjust `OPENAI_API_BASE` and any other model/provider variables accordingly.

---

## Usage

### 1. Generate Landing Page Content

**Plain JSON output**:

```bash
source .venv/bin/activate

python -m src.generator --type landing
```

**Mongo-shaped JSON** (e.g. `area_convertor_landing` doc):

```bash
python -m src.generator --type landing --mode mongo
```

This prints a Mongo-ready document like:

```json
{
  "slug": "area-convertor",
  "pageType": "landing",
  "locale": "en-IN",
  "siteCode": "sqy-india-web",
  "status": "draft",
  "seo": {
    "metaTitle": "...",
    "metaDescription": "...",
    "h1Heading": "...",
    "canonicalUrl": "https://www.squareyards.com/area-convertor"
  },
  "descriptionSection": { ... },
  "formulasSection": { ... },
  "faqs": [ ... ],
  ...
}
```

You can redirect this output to a file or pipe it into an internal ingestion script.

---

### 2. Generate a Single Child Page

Example: **Square Meter → Square Foot** for Mumbai (Pan-India context):

```bash
python -m src.generator   --type child   --mode mongo   --from_unit_code SQ_M   --to_unit_code SQ_FT   --from_unit_label "Square Meter"   --to_unit_label "Square Foot"   --factor_to_unit 10.7639   --from_unit_region "Pan-India"   --to_unit_region "Pan-India"   --city_name "Mumbai"
```

This prints a child-page Mongo document, for example:

```json
{
  "parentSlug": "area-convertor",
  "slug": "sq-m-to-sq-ft",
  "urlPath": "/area-convertor/sq-m-to-sq-ft",
  "fromUnitCode": "SQ_M",
  "toUnitCode": "SQ_FT",
  "locale": "en-IN",
  "siteCode": "sqy-india-web",
  "seo": { ... },
  "whyConvertSection": { ... },
  "standaloneSections": [
    { "sectionKey": "fromUnit", ... },
    { "sectionKey": "toUnit", ... }
  ],
  "examplesSection": { ... },
  "technicalDetailsSection": { ... },
  "faqs": [ ... ],
  "pageSettings": { ... }
}
```

This is directly compatible with a Mongo-backed CMS or backend service.

---

### 3. Batch Generation from CSV

The batch script expects a CSV similar to `AreaCalculation - Sheet2.csv` with:

- Row units & labels
- Column units & labels
- Factor (1 row-unit ≈ X column-unit)
- Optional region / city columns

#### Dry run with previews only

```bash
python -m scripts.batch_generate_children_from_csv   --csv_path "/absolute/path/to/AreaCalculation - Sheet2.csv"   --limit_pairs 5   --preview_only   --auto_fix_lengths   --max_fix_passes 2   --html_out_dir "previews"
```

Flags:

- `--limit_pairs N`  
  Limit how many unit pairs to generate (useful for testing).
- `--preview_only`  
  Do not write anything to Mongo; just log and write previews.
- `--auto_fix_lengths` / `--max_fix_passes`  
  Re-run the model for sections that violate length constraints up to N times.
- `--html_out_dir`  
  Directory to write `.html` preview files (ignored by git).

You can open any preview:

```bash
open previews/sq-m-to-sq-ft.html
```

#### Full batch run with Mongo write

```bash
python -m scripts.batch_generate_children_from_csv   --csv_path "/absolute/path/to/AreaCalculation - Sheet2.csv"   --mongo_uri "mongodb://localhost:27017"   --db_name "squareyards"   --collection_name "area_converter_child_pages"   --default_city "Mumbai"   --auto_fix_lengths   --max_fix_passes 2   --html_out_dir "previews_full"
```

- Each valid page is upserted into the given Mongo collection.
- HTML previews are still written for review.

---

## Localisation & Geographic Behaviour

The child page prompt is designed to:

- **Infer scope from the unit names and regions**, not just from the `city_name`:
  - Regional units (e.g. *Ankanam*, *Bigha – Assam*) → tied to the correct states/regions.
  - Global / metric units (e.g. *Acre*, *Are*, *Square Meter*, *Square Foot*) → treated as Pan-India / global.
- Use `city_name` (e.g. *Mumbai*) as a **hint**, not as an owner of the unit:
  - The city may be referenced as an example (“in metro cities like Mumbai…”).
  - Content remains valid for users across India.

This balances:
- SEO/AEO needs (city + region cues),
- With correctness (not misrepresenting metric units as city-specific),
- And readability for real buyers / investors.

---

## Section Regeneration Tool

If a single section needs to be updated without regenerating the entire page, use:

```bash
python -m src.section_regen   --section why_convert   --from_unit_code ANKANAM   --to_unit_code ACRE   --from_unit_label "Ankanam"   --to_unit_label "Acre"   --factor_to_unit 0.0000247105   --from_unit_region "Andhra Pradesh"   --to_unit_region "Pan-India"   --city_name "Hyderabad"
```

This prints fresh HTML for just that section, which you can manually merge into the stored document or hook up to a CMS endpoint.

Supported sections (depending on implementation):

- `why_convert`
- `what_is_from`
- `what_is_to`
- `examples`
- `technical`
- `faqs`

---

## Git & Project Hygiene

Key points:

- `.venv/`, `.env`, and local previews are **gitignored**.
- All secrets must live in your local `.env` and **never be committed**.
- The repo is designed as a **local generator tool**, not a public API.

Typical workflow:

```bash
# edit prompts, scripts, or models
git status
git add src/ scripts/ README.md
git commit -m "Improve child prompt localisation + batch HTML previews"
git push
```

---

## Roadmap / Possible Extensions

- Add an index HTML page listing all previews with links.
- Add quality checks:
  - automated tests for length, presence of required sections, basic HTML sanity.
- Add support for:
  - Multiple locales (e.g. en-IN, hi-IN) using the same core models.
  - Different site codes (e.g. web vs app vs international).

---

## License

This project is intended as internal tooling for content generation.
Consult your organization’s policies before open-sourcing or reusing it in other contexts.
