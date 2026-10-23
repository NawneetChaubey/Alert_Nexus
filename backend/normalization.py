"""Normalization + enrichment layer.

Takes a mapped record (from mapping.py) and produces a canonical normalized recall.
Uses the ingredient master + product->ingredient map + banned-substance seed data
to infer missing fields. Tracks all inferred fields for data completeness scoring and data lineage.

Semantics Note:
- `confidence_score` (and `data_completeness_score`) measures the proportion of core fields
  explicitly provided in the raw record versus inferred via heuristics.
- It represents source data completeness, NOT the probability or confidence that a watchlist
  match is correct (which is measured by `match_score` in matching.py).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple


# ---------------------------------------------------------------------------
# Severity inference
# ---------------------------------------------------------------------------
HIGH_KEYWORDS = [
    "toxic", "contamination", "contaminated", "carcinogen", "death",
    "life threatening", "serious", "severe", "prohibited", "banned",
    "poisoning", "burkholderia", "salmonella", "listeria", "mercury",
    "hydroquinone", "clobetasol", "nitrosamine", "ndma", "asbestos",
    "benzene", "lead", "e. coli", "cyanide",
]
MEDIUM_KEYWORDS = [
    "adverse reaction", "allergic", "irritation", "sensitisation",
    "chemical risk", "microbiological risk", "health risk", "rash",
    "moderate", "injury",
]
LOW_KEYWORDS = [
    "labeling", "label", "mislabel", "packaging", "misbranded",
    "undeclared", "cosmetic defect", "minor",
]


def infer_severity(text: str) -> str:
    """Return 'high' | 'medium' | 'low' | 'unknown' based on keywords."""
    if not text:
        return "unknown"
    t = text.lower()
    if any(k in t for k in HIGH_KEYWORDS):
        return "high"
    if any(k in t for k in MEDIUM_KEYWORDS):
        return "medium"
    if any(k in t for k in LOW_KEYWORDS):
        return "low"
    return "unknown"


def normalize_severity(raw: str | None, fallback_text: str | None) -> Tuple[str, bool]:
    """Normalize provided severity_raw, or infer from hazard text. Returns (severity, inferred)."""
    if raw:
        r = raw.strip().lower()
        if "serious" in r or "high" in r or r in ("i", "class i", "1"):
            return "high", False
        if "medium" in r or "moderate" in r or r in ("ii", "class ii", "2"):
            return "medium", False
        if "low" in r or r in ("iii", "class iii", "3"):
            return "low", False
        # Fall-through: try keyword inference on the raw string
    inferred = infer_severity(raw or "") or "unknown"
    if inferred == "unknown" and fallback_text:
        inferred = infer_severity(fallback_text)
    return inferred, True


# ---------------------------------------------------------------------------
# Region inference
# ---------------------------------------------------------------------------
EU_COUNTRIES = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia",
    "czech republic", "denmark", "estonia", "finland", "france", "germany",
    "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg",
    "malta", "netherlands", "poland", "portugal", "romania", "slovakia",
    "slovenia", "spain", "sweden", "eu", "european union",
}


def normalize_region(raw: str | None, source_file: str) -> Tuple[str, bool]:
    """Return (region, inferred). Region is a short code/name like 'EU', 'US', or a country name."""
    if raw:
        r = raw.strip()
        rl = r.lower()
        if rl in EU_COUNTRIES:
            return "EU", False
        if rl in ("united states", "usa", "us", "u.s.", "u.s.a.", "fda"):
            return "US", False
        # Keep the country string but not inferred
        return r.title(), False
    sf = (source_file or "").lower()
    if "eu_notification" in sf or "eu notification" in sf or "safety" in sf:
        return "EU", True
    # US FDA-style files
    return "US", True


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------
def normalize_category(raw: str | None, product_name: str | None) -> Tuple[str, bool]:
    src = " ".join(filter(None, [raw, product_name])).lower()
    if not src:
        return "unknown", True
    if any(k in src for k in ["cosmetic", "lipstick", "cream", "lotion", "shampoo", "perfume", "shaving", "sunscreen", "nail", "hair", "makeup", "skin"]):
        return "cosmetic", raw is None
    if any(k in src for k in ["drug", "tablet", "capsule", "syrup", "pharmaceut", "medicin", "injection", "ointment", "otc"]):
        return "drug", raw is None
    if any(k in src for k in ["device", "implant", "monitor", "catheter", "stent", "syringe", "ventilator"]):
        return "device", raw is None
    if any(k in src for k in ["food", "snack", "beverage", "infant formula", "baby food"]):
        return "food", raw is None
    return "unknown", True


# ---------------------------------------------------------------------------
# Ingredient resolution
# ---------------------------------------------------------------------------
def _token_set(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9\- ]+", s.lower()))


def extract_ingredients_from_text(
    text: str,
    ingredient_index: List[Dict[str, Any]],
) -> List[str]:
    """Search the free-text for any known ingredient name/synonym. Returns canonical names."""
    if not text:
        return []
    t = text.lower()
    hits: List[str] = []
    for ing in ingredient_index:
        names = [ing["name"]] + list(ing.get("synonyms") or [])
        for n in names:
            n_lc = n.lower()
            if n_lc and n_lc in t:
                if ing["name"] not in hits:
                    hits.append(ing["name"])
                break
    return hits


def resolve_ingredients(
    ingredients_raw: str | None,
    recall_reason: str | None,
    product_name: str | None,
    ingredient_index: List[Dict[str, Any]],
    product_map: Dict[str, List[str]],
) -> Tuple[List[str], bool, str]:
    """Return (canonical_ingredients, inferred, method)."""
    # 1. explicit list
    if ingredients_raw:
        parts = [p.strip().lower() for p in re.split(r"[;,/\n]", ingredients_raw) if p.strip()]
        # Also try to canonicalize via ingredient index
        canon: List[str] = []
        for p in parts:
            matched = None
            for ing in ingredient_index:
                names = [ing["name"]] + list(ing.get("synonyms") or [])
                if any(p == n.lower() or p in n.lower() or n.lower() in p for n in names):
                    matched = ing["name"]
                    break
            canon.append(matched or p)
        if canon:
            return canon, False, "explicit"
    # 2. extract from recall reason / description
    ings = extract_ingredients_from_text(recall_reason or "", ingredient_index)
    if ings:
        return ings, True, "keyword_extract_from_reason"
    # 3. lookup product name in product->ingredient map
    if product_name:
        pn = product_name.lower()
        for key, mapped in product_map.items():
            if key in pn:
                return list(mapped), True, f"product_map:{key}"
    # 4. placeholder
    return [f"unknown_compound_{uuid.uuid4().hex[:8]}"], True, "placeholder"


# ---------------------------------------------------------------------------
# Normalize a whole record
# ---------------------------------------------------------------------------
def normalize_record(
    mapped: Dict[str, Any],
    ingredient_index: List[Dict[str, Any]],
    product_map: Dict[str, List[str]],
    source_display: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return (normalized, lineage_rows)."""
    inferred_fields: List[str] = []
    lineage: List[Dict[str, Any]] = []

    # Core fields
    product_name = mapped.get("product_name_full") or mapped.get("product_name") or mapped.get("brand") or "Unknown product"
    if not mapped.get("product_name"):
        inferred_fields.append("product_name")
        lineage.append({"field_name": "product_name", "original_value": None, "inferred_value": product_name, "inference_method": "brand_fallback"})

    # Severity
    sev_raw = mapped.get("severity_raw")
    fallback_text = " ".join(filter(None, [mapped.get("recall_reason"), mapped.get("description")]))
    severity, sev_inferred = normalize_severity(sev_raw, fallback_text)
    if sev_inferred:
        inferred_fields.append("severity")
        lineage.append({"field_name": "severity", "original_value": sev_raw, "inferred_value": severity, "inference_method": "keyword_rule"})

    # Region
    region, region_inferred = normalize_region(mapped.get("region_raw"), mapped.get("source_file", ""))
    if region_inferred:
        inferred_fields.append("region")
        lineage.append({"field_name": "region", "original_value": mapped.get("region_raw"), "inferred_value": region, "inference_method": "source_file_origin"})

    # Category
    category, cat_inferred = normalize_category(mapped.get("category_raw"), product_name)
    if cat_inferred:
        inferred_fields.append("category")
        lineage.append({"field_name": "category", "original_value": mapped.get("category_raw"), "inferred_value": category, "inference_method": "keyword_rule"})

    # Ingredients
    ingredients, ing_inferred, ing_method = resolve_ingredients(
        mapped.get("ingredients_raw"),
        " ".join(filter(None, [mapped.get("recall_reason"), mapped.get("description")])),
        product_name,
        ingredient_index,
        product_map,
    )
    if ing_inferred:
        inferred_fields.append("ingredients")
        lineage.append({
            "field_name": "ingredients",
            "original_value": mapped.get("ingredients_raw"),
            "inferred_value": ", ".join(ingredients),
            "inference_method": ing_method,
        })

    # Recall reason (required but may be missing)
    recall_reason = mapped.get("recall_reason") or mapped.get("description") or "No reason provided"
    if not mapped.get("recall_reason"):
        inferred_fields.append("recall_reason")
        lineage.append({"field_name": "recall_reason", "original_value": None, "inferred_value": recall_reason, "inference_method": "description_fallback"})

    # Data completeness score:
    # Measures the proportion of core fields explicitly provided in the raw record
    # rather than inferred via heuristic rules or external knowledge bases.
    # Note: This reflects source data completeness, NOT match probability or match accuracy.
    total_fields = 5  # product_name, severity, region, category, ingredients
    inferred_core_count = len(set(inferred_fields) & {"product_name", "severity", "region", "category", "ingredients"})
    data_completeness_score = round(max(0.0, 1.0 - (inferred_core_count / total_fields)), 3)
    # Retain 'confidence_score' key for backward compatibility with existing storage, API, and UI schemas
    confidence_score = data_completeness_score

    normalized = {
        "recall_id": f"rec_{uuid.uuid4().hex[:12]}",
        "product_name": product_name,
        "ingredients": ingredients,
        "category": category,
        "recall_reason": recall_reason,
        "severity": severity,
        "region": region,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source_display,
        "source_file": mapped.get("source_file"),
        "external_id": mapped.get("external_id"),
        "source_url": mapped.get("source_url"),
        "barcode": mapped.get("barcode"),
        "batch_number": mapped.get("batch_number"),
        "corrective_action": mapped.get("corrective_action"),
        "confidence_score": confidence_score,
        "data_completeness_score": data_completeness_score,
        "inferred_fields": sorted(set(inferred_fields)),
    }
    return normalized, lineage
