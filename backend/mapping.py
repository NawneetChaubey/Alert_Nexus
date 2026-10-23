"""Schema mapping layer: map inconsistent source columns to a unified shape."""
import re
from typing import Dict, Any, Optional

# Column aliases -> canonical field name
COLUMN_ALIASES: Dict[str, str] = {
    # product
    "product name": "product_name",
    "product_name": "product_name",
    "product": "product_name",
    "brand_name": "product_name",
    "brand name": "product_name",
    "name": "product_name",
    "title": "product_name",
    "product title": "product_name",
    "product_title": "product_name",
    "product or category": "product_name",
    "product_or_category": "product_name",
    "product item": "product_name",
    "item name": "product_name",
    "item": "product_name",
    "article": "product_name",
    "device name": "product_name",
    "drug name": "product_name",
    "medicine name": "product_name",
    "trade name": "product_name",
    "commercial name": "product_name",
    "proprietary name": "product_name",
    "recalled product": "product_name",
    "affected product": "product_name",
    "product description": "description",
    # brand (kept separate, folded into product_name if needed)
    "brand": "brand",
    "manufacturer": "brand",
    "recalling firm": "brand",
    "recalling_firm": "brand",
    "make": "brand",
    "producer": "brand",
    "company": "brand",
    "distributor": "brand",
    "marketing authorisation holder": "brand",
    # ingredients
    "ingredient": "ingredients_raw",
    "ingredients": "ingredients_raw",
    "substance": "ingredients_raw",
    "active ingredient": "ingredients_raw",
    "active_ingredient": "ingredients_raw",
    "active ingredients": "ingredients_raw",
    "active substance": "ingredients_raw",
    "composition": "ingredients_raw",
    "components": "ingredients_raw",
    # severity
    "class": "severity_raw",
    "severity": "severity_raw",
    "risk type": "severity_raw",
    "risk_type": "severity_raw",
    "type of alert": "severity_raw",
    "type_of_alert": "severity_raw",
    "recall type": "severity_raw",
    "recall_type": "severity_raw",
    "classification": "severity_raw",
    "recall class": "severity_raw",
    "recall_class": "severity_raw",
    "hazard class": "severity_raw",
    "risk level": "severity_raw",
    # region
    "country": "region_raw",
    "authority": "region_raw",
    "country of origin": "region_raw",
    "alert submitted by": "region_raw",
    "region": "region_raw",
    "source country": "region_raw",
    "source_country": "region_raw",
    "distributing country": "region_raw",
    "jurisdiction": "region_raw",
    "notifying country": "region_raw",
    # reason (note: "risk" is intentionally mapped to recall_reason since EU files put hazard text there)
    "risk": "recall_reason",
    "hazard/reason for recall": "recall_reason",
    "hazard reason for recall": "recall_reason",
    "recall reason": "recall_reason",
    "recall_reason": "recall_reason",
    "reason": "recall_reason",
    "issue": "recall_reason",
    "defect": "recall_reason",
    "nature of risk": "recall_reason",
    "danger": "recall_reason",
    "hazard": "recall_reason",
    "reason for recall": "recall_reason",
    "violation": "recall_reason",
    "description": "description",
    # category
    "category": "category_raw",
    "product type": "category_raw",
    "oecd portal category": "category_raw",
    "segment": "category_raw",
    "product category": "category_raw",
    # identifiers
    "barcode": "barcode",
    "upc": "barcode",
    "ean": "barcode",
    "gtin": "barcode",
    "batch number": "batch_number",
    "batch_number": "batch_number",
    "batch no": "batch_number",
    "batch_no": "batch_number",
    "lot number": "batch_number",
    "lot_number": "batch_number",
    "lot no": "batch_number",
    "lot": "batch_number",
    "batch": "batch_number",
    "source/psd number": "external_id",
    "source psd number": "external_id",
    "alert number": "external_id",
    "alert_number": "external_id",
    "recall id": "external_id",
    "recall_id": "external_id",
    "sr no": "external_id",
    "sr_no": "external_id",
    "source ref": "external_id",
    "source_ref": "external_id",
    "reference": "external_id",
    "ref no": "external_id",
    "case number": "external_id",
    "notification number": "external_id",
    "recall number": "external_id",
    "url of case": "source_url",
    "company recall page": "source_url",
    "source link": "source_url",
    "source_link": "source_url",
    # corrective action
    "corrective action": "corrective_action",
    "compulsory measures": "corrective_action",
    "voluntary measures": "corrective_action",
    "action type": "corrective_action",
    "action_type": "corrective_action",
    "intervention": "corrective_action",
    "measure": "corrective_action",
    "measures": "corrective_action",
    "status": "status",
    # extras kept for traceability (units, frequency)
    "units_recalled": "units_recalled",
    "incident_frequency": "incident_frequency",
    "year": "year",
    "report_date": "report_date",
}


def _norm_key(k: Any) -> str:
    """Normalize a header or column name: strip BOM, lower, unify separators."""
    s = str(k or "").strip().lower().lstrip("\ufeff")
    # Collapse any sequences of whitespace, underscores, hyphens, slashes into a single space
    return re.sub(r"[\s\-_/]+", " ", s).strip()


def map_record(raw: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    """Map a raw source record to the unified mapped_recalls shape."""
    mapped: Dict[str, Any] = {
        "product_name": None,
        "brand": None,
        "ingredients_raw": None,
        "severity_raw": None,
        "region_raw": None,
        "recall_reason": None,
        "description": None,
        "category_raw": None,
        "barcode": None,
        "batch_number": None,
        "external_id": None,
        "source_url": None,
        "corrective_action": None,
        "source_file": source_file,
    }
    # First pass: direct alias mapping
    for k, v in raw.items():
        if v is None:
            continue
        sv = str(v).strip()
        if not sv or sv.lower() == "nan":
            continue
        key = _norm_key(k)
        if key in COLUMN_ALIASES:
            target = COLUMN_ALIASES[key]
            # Don't overwrite with empty; prefer first non-empty, but allow more-specific upgrades
            if mapped.get(target) in (None, ""):
                mapped[target] = sv

    # Second pass: detect plausible product field if product_name and brand are still absent
    if not mapped.get("product_name") and not mapped.get("brand"):
        for k, v in raw.items():
            if v is None:
                continue
            sv = str(v).strip()
            if not sv or sv.lower() == "nan":
                continue
            key = _norm_key(k)
            # Avoid re-using fields that were already mapped to non-product roles
            if any(term in key for term in ["product", "item", "drug", "medicine", "substance", "title", "trade"]):
                if not any(term in key for term in ["type", "category", "class", "status", "url", "link", "date"]):
                    mapped["product_name"] = sv
                    break

    # Fold brand into product_name display if both present
    if mapped.get("brand") and mapped.get("product_name"):
        mapped["product_name_full"] = f"{mapped['brand']} – {mapped['product_name']}"
    else:
        mapped["product_name_full"] = mapped.get("product_name") or mapped.get("brand")

    # Preserve raw input record for diagnostics & lineage
    mapped["raw"] = raw

    return mapped


def derive_source_name(source_file: str) -> str:
    """Turn a source_file path into a short display source."""
    f = source_file.lower()
    if "eu_notification" in f or "eu notification" in f:
        return "EU Safety Gate"
    if "safety_alert" in f or "safety alert" in f:
        return "Safety Alerts"
    if "combined" in f:
        return "Combined Product Recalls"
    # Order matters: specific checks before broad ones
    if "recall_master" in f or "recall_mastere" in f:
        return "Recall Master"
    if "master" in f and "recall" in f:
        return "Master Recall List"
    if "regional" in f:
        return "Regional Recalls"
    if "nsq" in f:
        return "NSQ Product Quality Failures"
    if "market_action" in f or "market action" in f:
        return "Market Actions"
    if "product_recalls" in f:
        return "Product Recalls"
    return source_file
