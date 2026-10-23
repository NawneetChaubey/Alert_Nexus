"""Matching engine: product + ingredient matching to user watchlists.

Provides deterministic and fuzzy matching of normalized recalls against user watchlists,
returning scored matches and creating user-scoped alerts.

Semantics & Confidence Distinction:
- `match_score`: Reflects similarity / string match confidence (0.0 to 1.0) between the
  watchlist query and target entity.
- `confidence_score` / `data_completeness_score`: Reflects the source data completeness of
  the ingested recall document (ratio of explicit fields to core fields), NOT a probability
  that a watchlist match is true or false.
- `is_verified` / `evidence_type`: Distinguishes whether the matched evidence was explicit
  in the regulatory source ('verified') or derived via inference heuristics ('inferred').
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from seed_data import INGREDIENT_MASTER

log = logging.getLogger("matching")


# Pre-build canonical alias lookup from master seed data
_GLOBAL_INGREDIENT_ALIAS_MAP: Dict[str, str] = {}
for item in INGREDIENT_MASTER:
    c = item["name"].lower().strip()
    _GLOBAL_INGREDIENT_ALIAS_MAP[c] = c
    for s in item.get("synonyms") or []:
        _GLOBAL_INGREDIENT_ALIAS_MAP[s.lower().strip()] = c


def get_ingredient_alias_map(custom_index: Optional[List[Dict[str, Any]]] = None) -> Dict[str, str]:
    """Return dictionary mapping any ingredient name or synonym to its canonical name."""
    if not custom_index:
        return _GLOBAL_INGREDIENT_ALIAS_MAP
    alias_map = dict(_GLOBAL_INGREDIENT_ALIAS_MAP)
    for item in custom_index:
        c = item.get("name", "").lower().strip()
        if not c:
            continue
        alias_map[c] = c
        for s in item.get("synonyms") or []:
            alias_map[s.lower().strip()] = c
    return alias_map


class MatchResult(tuple):
    """3-tuple (match_type, matched_term, score) with attached verification metadata.

    Subclasses tuple for 100% backwards compatibility with callers unpacking:
    `match_type, matched_on, score = matches[0]`
    """

    def __new__(
        cls,
        match_type: str,
        matched_term: str,
        score: float,
        is_verified: bool = True,
        evidence_type: str = "verified",
    ):
        return super().__new__(cls, (match_type, matched_term, score))

    def __init__(
        self,
        match_type: str,
        matched_term: str,
        score: float,
        is_verified: bool = True,
        evidence_type: str = "verified",
    ):
        self.match_type = match_type
        self.matched_term = matched_term
        self.score = score
        self.is_verified = is_verified
        self.evidence_type = evidence_type


def is_placeholder_or_empty(ingredient: str | None) -> bool:
    """Return True if ingredient is missing, empty, or a synthetic placeholder token."""
    if not ingredient or not isinstance(ingredient, str):
        return True
    s = ingredient.strip().lower()
    return s.startswith("unknown_compound_") or s in ("unknown", "none", "n/a", "null", "")


def match_product_query(query: str, product_name: str, threshold: int = 80) -> Tuple[bool, float]:
    """Match a watched product query against a recall product name.

    Uses word/token boundary semantics and windowed ratio comparisons:
    - Eliminates substring false positives on non-word boundaries (e.g. 'Bio' in 'Antibiotic',
      'Oil' in 'Boil Ease', 'Care' in 'Scarecrow', 'Art' in 'Smart', 'Cure' in 'Secure').
    - Evaluates complete token windows to prevent cutting unrelated words in half
      (e.g., 'Claritin' vs 'Clarithromycin', 'Celebrex' vs 'Celexa').
    - Requires exact token sequence for short queries (<= 3 chars).
    """
    q_tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
    p_tokens = re.findall(r"[a-zA-Z0-9]+", product_name.lower())
    if not q_tokens or not p_tokens:
        return False, 0.0

    q_len = len(q_tokens)
    q_str = " ".join(q_tokens)

    # 1. Exact token sequence match (case-insensitive phrase match with word boundaries)
    for i in range(len(p_tokens) - q_len + 1):
        if p_tokens[i : i + q_len] == q_tokens:
            return True, 1.0

    # Short query guard: queries with <= 3 characters (e.g. 'oil', 'tea', 'gel')
    # must match whole tokens exactly; 1-character fuzzy edits on 3-letter words
    # alter the identity to unrelated common words ('oil' vs 'boil').
    if len(q_str) <= 3:
        return False, 0.0

    # 2. Window-based token fuzzy match using ratio
    best_score = 0.0
    min_w = max(1, q_len - 1)
    max_w = min(len(p_tokens), q_len + 1)
    for w in range(min_w, max_w + 1):
        for i in range(len(p_tokens) - w + 1):
            window_str = " ".join(p_tokens[i : i + w])
            # For short 4-letter words (like 'cure', 'care'), an affix like 'secure' or 'scare'
            # contains the full word as a substring but represents a completely different root word.
            if len(q_str) <= 4 and q_str in window_str and len(window_str) > len(q_str):
                continue
            score = fuzz.ratio(q_str, window_str)
            if score > best_score:
                best_score = score

    if best_score >= threshold:
        return True, round(best_score / 100.0, 3)
    return False, round(best_score / 100.0, 3)


def match_ingredient_query(
    watched_ing: str,
    candidate_ing: str,
    alias_map: Dict[str, str],
) -> Tuple[bool, float]:
    """Match an ingredient query against a candidate ingredient.

    - Filters out synthetic placeholders and empty tokens.
    - Resolves known pharmacological & cosmetic synonyms to canonical forms.
    - Uses word-boundary matching on multi-token derivatives (e.g. 'ibuprofen' in 'ibuprofen sodium').
    - Disallows non-word-boundary substring false positives (e.g. 'tin' in 'gelatin', 'iron' in 'interferon').
    """
    w_clean = watched_ing.lower().strip()
    c_clean = candidate_ing.lower().strip()

    if is_placeholder_or_empty(w_clean) or is_placeholder_or_empty(c_clean):
        return False, 0.0

    w_canon = alias_map.get(w_clean, w_clean)
    c_canon = alias_map.get(c_clean, c_clean)

    # 1. Exact canonical or raw string match
    if w_canon == c_canon or w_clean == c_clean:
        return True, 1.0

    # 2. Word boundary matching: watched term is a whole token/phrase inside candidate
    w_pat_canon = r"\b" + re.escape(w_canon) + r"\b"
    w_pat_clean = r"\b" + re.escape(w_clean) + r"\b"
    if re.search(w_pat_canon, c_canon) or re.search(w_pat_clean, c_clean):
        return True, 0.95

    # 3. Candidate term is a whole token/phrase inside watched query (e.g. user watches 'ibuprofen sodium', recall lists 'ibuprofen')
    GENERIC_WORDS = {"acid", "oil", "salt", "extract", "powder", "water", "alcohol", "solution", "agent"}
    if c_canon not in GENERIC_WORDS and len(c_canon) >= 4:
        c_pat_canon = r"\b" + re.escape(c_canon) + r"\b"
        c_pat_clean = r"\b" + re.escape(c_clean) + r"\b"
        if re.search(c_pat_canon, w_canon) or re.search(c_pat_clean, w_clean):
            return True, 0.90

    return False, 0.0


def match_watchlist(
    normalized: Dict[str, Any],
    watchlist: Dict[str, List[str]],
    product_fuzzy_threshold: int = 80,
    ingredient_index: Optional[List[Dict[str, Any]]] = None,
) -> List[MatchResult]:
    """Return list of MatchResult objects for matching products and ingredients.

    Each MatchResult unpacks as (match_type, matched_term, score) for compatibility,
    and has `.is_verified` and `.evidence_type` attributes.
    """
    matches: List[MatchResult] = []
    pname = normalized.get("product_name") or ""
    inferred_fields = set(normalized.get("inferred_fields") or [])

    # Product matching
    is_product_verified = "product_name" not in inferred_fields
    for prod in watchlist.get("products", []) or []:
        p = prod.strip()
        if not p:
            continue
        matched, score = match_product_query(p, pname, threshold=product_fuzzy_threshold)
        if matched:
            evidence = "verified" if is_product_verified else "inferred"
            matches.append(
                MatchResult(
                    match_type="product",
                    matched_term=prod,
                    score=score,
                    is_verified=is_product_verified,
                    evidence_type=evidence,
                )
            )

    # Ingredient matching
    # Inferred or placeholder ingredients are NOT treated as verified evidence (Task 4)
    is_ing_verified = "ingredients" not in inferred_fields
    alias_map = get_ingredient_alias_map(ingredient_index)
    raw_candidates = normalized.get("ingredients") or []

    # Exclude placeholder ingredients completely
    valid_candidates = [c for c in raw_candidates if not is_placeholder_or_empty(c)]

    for ing in watchlist.get("ingredients", []) or []:
        i_clean = ing.strip()
        if not i_clean or is_placeholder_or_empty(i_clean):
            continue

        best_score = 0.0
        for cand in valid_candidates:
            matched, score = match_ingredient_query(i_clean, cand, alias_map)
            if matched and score > best_score:
                best_score = score

        if best_score > 0.0:
            evidence = "verified" if is_ing_verified else "inferred"
            matches.append(
                MatchResult(
                    match_type="ingredient",
                    matched_term=ing,
                    score=best_score,
                    is_verified=is_ing_verified,
                    evidence_type=evidence,
                )
            )

    # Deduplicate matches
    seen: set = set()
    out: List[MatchResult] = []
    for m in matches:
        key = (m.match_type, m.matched_term.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


async def run_matching_for_recall(db, normalized: Dict[str, Any], confidence_threshold: float = 0.25) -> int:
    """Find all users whose watchlist matches this recall, create alert docs. Preserves dismissed state."""
    # Skip matching when record data completeness is below the threshold
    if normalized.get("confidence_score", 0) < confidence_threshold:
        return 0

    cursor = db.watchlists.find({}, {"_id": 0})
    created = 0
    async for wl in cursor:
        matches = match_watchlist(normalized, wl)
        if not matches:
            continue
        match = matches[0]
        match_type, matched_on, score = match[0], match[1], match[2]
        is_verified = getattr(match, "is_verified", True)
        evidence_type = getattr(match, "evidence_type", "verified")

        alert_id = f"alert_{normalized['recall_id']}_{wl['user_id']}"

        # Preserve dismissal and prevent duplicates for the same underlying recall
        existing = await db.alerts.find_one({"user_id": wl["user_id"], "recall_id": normalized["recall_id"]})
        if existing:
            continue

        alert_doc = {
            "alert_id": alert_id,
            "user_id": wl["user_id"],
            "recall_id": normalized["recall_id"],
            "product": normalized.get("product_name"),
            "matched_on": match_type,
            "matched_term": matched_on,
            "match_score": score,
            "severity": normalized.get("severity"),
            "confidence_score": normalized.get("confidence_score"),
            "data_completeness_score": normalized.get("data_completeness_score", normalized.get("confidence_score")),
            "region": normalized.get("region"),
            "source": normalized.get("source"),
            "ingredients": normalized.get("ingredients"),
            "recall_reason": normalized.get("recall_reason"),
            "is_verified": is_verified,
            "evidence_type": evidence_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        try:
            await db.alerts.insert_one(alert_doc)
            created += 1
        except Exception as e:
            err_msg = str(e).lower()
            if "duplicate key" in err_msg or "e11000" in err_msg or type(e).__name__ == "DuplicateKeyError":
                continue
            log.error("Database error inserting alert %s: %s", alert_id, e)
            raise
    return created


async def run_matching_for_user(db, user_id: str, watchlist: Dict[str, List[str]]) -> int:
    """Backfill: when a watchlist is updated, scan existing recalls for new matches. Preserves dismissed state."""
    created = 0
    cursor = db.normalized_recalls.find({}, {"_id": 0})
    async for rec in cursor:
        if rec.get("confidence_score", 0) < 0.25:
            continue
        matches = match_watchlist(rec, watchlist)
        if not matches:
            continue
        match = matches[0]
        match_type, matched_on, score = match[0], match[1], match[2]
        is_verified = getattr(match, "is_verified", True)
        evidence_type = getattr(match, "evidence_type", "verified")

        alert_id = f"alert_{rec['recall_id']}_{user_id}"

        # Preserve dismissal and prevent duplicates for the same underlying recall
        existing = await db.alerts.find_one({"user_id": user_id, "recall_id": rec["recall_id"]})
        if existing:
            continue

        alert_doc = {
            "alert_id": alert_id,
            "user_id": user_id,
            "recall_id": rec["recall_id"],
            "product": rec.get("product_name"),
            "matched_on": match_type,
            "matched_term": matched_on,
            "match_score": score,
            "severity": rec.get("severity"),
            "confidence_score": rec.get("confidence_score"),
            "data_completeness_score": rec.get("data_completeness_score", rec.get("confidence_score")),
            "region": rec.get("region"),
            "source": rec.get("source"),
            "ingredients": rec.get("ingredients"),
            "recall_reason": rec.get("recall_reason"),
            "is_verified": is_verified,
            "evidence_type": evidence_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        try:
            await db.alerts.insert_one(alert_doc)
            created += 1
        except Exception as e:
            err_msg = str(e).lower()
            if "duplicate key" in err_msg or "e11000" in err_msg or type(e).__name__ == "DuplicateKeyError":
                continue
            log.error("Database error inserting alert %s: %s", alert_id, e)
            raise
    return created
