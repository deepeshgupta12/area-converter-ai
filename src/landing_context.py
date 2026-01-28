# src/landing_context.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import re
import pandas as pd


def _norm_unit(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("&", "and")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("sq. ", "sq ").replace("sq.", "sq")
    s = s.replace("square feet", "square foot")  # normalize plural
    s = s.replace("sq ft", "square foot")
    s = s.replace("sq. ft", "square foot")
    s = s.replace("sq m", "square meter")
    s = s.replace("sq. m", "square meter")
    s = s.replace("sqm", "square meter")
    s = s.replace("sqft", "square foot")
    return s


def _make_unit_code(unit_name: str) -> str:
    # Best-effort code generator: "Square Meter" -> "SQUARE_METER" -> "SQUARE_METER"
    # We keep it consistent and stable; front-end can map later if needed.
    s = (unit_name or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:40] if s else "UNIT"


def _parse_keyword(keyword: str) -> Optional[Tuple[str, str]]:
    # Expects "X to Y"
    if not keyword:
        return None
    k = keyword.strip()
    if " to " not in k.lower():
        return None
    parts = re.split(r"\s+to\s+", k, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    return parts[0].strip(), parts[1].strip()


def _infer_region_hint(unit_name: str) -> str:
    # IMPORTANT: No hardcoded “global units” list.
    # Only infer region if name itself suggests it (state/city token in the label).
    name = (unit_name or "").lower()
    # common patterns
    if any(tok in name for tok in ["assam", "bihar", "bengal", "wb", "west bengal", "up", "uttar pradesh", "punjab", "haryana", "rajasthan", "gujarat", "maharashtra", "tamil nadu", "kerala", "karnataka", "andhra", "telangana", "odisha"]):
        return "Region-specific"
    return "Pan-India"


def build_landing_context_from_csvs(
    search_volume_csv: str,
    conversion_matrix_csv: str,
    *,
    top_pills_per_unit: int = 3,
    major_units_count: int = 9,
    quick_ref_rows: int = 10,
) -> Dict:
    """
    Returns a context dict that the LLM uses to:
    - build All Units A–Z (units + pills)
    - choose Major Units Explained
    - build Quick Conversion Reference table
    - keep conversions consistent with your master sheet
    """

    # --- conversion matrix ---
    df_conv = pd.read_csv(conversion_matrix_csv)
    # first column is unit name (e.g. "Ankanam"), rest are conversion targets
    unit_col = df_conv.columns[0]
    unit_names = [str(x).strip() for x in df_conv[unit_col].tolist()]
    target_cols = [c for c in df_conv.columns if c != unit_col]

    # build lookup: factor[from_unit][to_unit] = float
    factor: Dict[str, Dict[str, float]] = {}
    for _, row in df_conv.iterrows():
        frm = str(row[unit_col]).strip()
        factor[frm] = {}
        for to in target_cols:
            v = row[to]
            try:
                fv = float(v)
            except Exception:
                continue
            factor[frm][str(to).strip()] = fv

    # --- search volume ---
    df_sv = pd.read_csv(search_volume_csv)
    # expected columns: Are Keywords, Search Volume
    # tolerate minor naming differences
    kw_col = "Are Keywords" if "Are Keywords" in df_sv.columns else df_sv.columns[0]
    vol_col = "Search Volume" if "Search Volume" in df_sv.columns else df_sv.columns[1]

    parsed_pairs: List[Dict] = []
    for _, r in df_sv.iterrows():
        kw = str(r.get(kw_col, "")).strip()
        vol_raw = r.get(vol_col, 0)
        try:
            vol = int(vol_raw)
        except Exception:
            vol = 0
        parsed = _parse_keyword(kw)
        if not parsed:
            continue
        a, b = parsed
        parsed_pairs.append({"fromLabel": a, "toLabel": b, "volume": vol, "keyword": kw})

    # map labels -> best matching matrix unit name
    norm_to_matrix: Dict[str, str] = {}
    # precompute normalized matrix names
    matrix_norm = {_norm_unit(u): u for u in unit_names}
    for p in parsed_pairs:
        for label in [p["fromLabel"], p["toLabel"]]:
            nl = _norm_unit(label)
            if nl in matrix_norm:
                norm_to_matrix[nl] = matrix_norm[nl]

    def match_matrix_unit(label: str) -> Optional[str]:
        nl = _norm_unit(label)
        if nl in norm_to_matrix:
            return norm_to_matrix[nl]
        # fallback: fuzzy contains
        for nkey, orig in matrix_norm.items():
            if nl == nkey or nl in nkey or nkey in nl:
                return orig
        return None

    # group pills per unit
    pills_by_unit: Dict[str, List[Dict]] = {u: [] for u in unit_names}
    for p in parsed_pairs:
        frm = match_matrix_unit(p["fromLabel"])
        to = match_matrix_unit(p["toLabel"])
        if not frm or not to:
            continue
        pills_by_unit[frm].append(
            {
                "label": f"{p['fromLabel']} → {p['toLabel']}",
                "fromUnitName": frm,
                "toUnitName": to,
                "fromUnitLabel": p["fromLabel"],
                "toUnitLabel": p["toLabel"],
                "volume": p["volume"],
                "fromUnitCode": _make_unit_code(frm),
                "toUnitCode": _make_unit_code(to),
            }
        )

    for u in pills_by_unit:
        pills_by_unit[u].sort(key=lambda x: x["volume"], reverse=True)
        pills_by_unit[u] = pills_by_unit[u][:top_pills_per_unit]

    # All Units A–Z groups
    groups: Dict[str, List[Dict]] = {}
    for u in unit_names:
        letter = (u[:1].upper() if u else "#")
        groups.setdefault(letter, [])
        groups[letter].append(
            {
                "unitName": u,
                "unitSymbol": "",  # optional; let model write if known
                "oneLiner": "",    # model will generate
                "whereUsed": "",   # model will generate
                "regionHint": _infer_region_hint(u),
                "popularConversionPills": pills_by_unit.get(u, []),
            }
        )
    # sort groups/units
    group_list = []
    for letter in sorted(groups.keys()):
        group_list.append({"letter": letter, "units": sorted(groups[letter], key=lambda x: x["unitName"])})

    # Major units (top by total search volume mentions)
    unit_score: Dict[str, int] = {u: 0 for u in unit_names}
    for p in parsed_pairs:
        frm = match_matrix_unit(p["fromLabel"])
        to = match_matrix_unit(p["toLabel"])
        if frm:
            unit_score[frm] += p["volume"]
        if to:
            unit_score[to] += p["volume"]

    major_units = sorted(unit_score.items(), key=lambda x: x[1], reverse=True)[:major_units_count]
    major_units_list = []
    for u, _ in major_units:
        # pick one “popular conversion” for display
        pills = pills_by_unit.get(u, [])
        pop = pills[0] if pills else None
        conversion_label = ""
        conversion_factor = None
        if pop:
            conversion_label = f"1 {u} = {factor.get(u, {}).get(pop['toUnitName'], '')} {pop['toUnitName']}"
            conversion_factor = factor.get(u, {}).get(pop["toUnitName"])
        major_units_list.append(
            {
                "unitName": u,
                "unitSymbol": "",
                "oneLiner": "",
                "whereUsed": "",
                "conversionLabel": conversion_label,
                "regionHint": _infer_region_hint(u),
                "exampleConversion": {
                    "toUnitName": pop["toUnitName"] if pop else "",
                    "factor": conversion_factor,
                },
            }
        )

    # Quick conversion reference rows (top keywords)
    parsed_pairs.sort(key=lambda x: x["volume"], reverse=True)
    quick_rows = []
    for p in parsed_pairs[:quick_ref_rows]:
        frm = match_matrix_unit(p["fromLabel"])
        to = match_matrix_unit(p["toLabel"])
        if not frm or not to:
            continue
        f = factor.get(frm, {}).get(to)
        if f is None:
            continue
        quick_rows.append(
            {
                "fromUnitLabel": p["fromLabel"],
                "toUnitLabel": p["toLabel"],
                "fromUnitName": frm,
                "toUnitName": to,
                "factor": f,
                "regionHint": _infer_region_hint(frm),
                "usageHint": "Real estate listings / documentation",
                "volume": p["volume"],
            }
        )

    return {
        "allUnitsAZ": group_list,
        "majorUnits": major_units_list,
        "quickReferenceRows": quick_rows,
        "unitNames": unit_names,
    }