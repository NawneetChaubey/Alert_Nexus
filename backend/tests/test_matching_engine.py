"""Regression test suite for matching engine reliability.

Tests:
1. Exact product-name matches.
2. Legitimate fuzzy matches.
3. Similar but unrelated product names (false-positive prevention).
4. Ingredient aliases and canonicalization.
5. Missing, inferred, and placeholder ingredients.
6. Existing alert behavior and backwards compatibility.
7. Data completeness vs match confidence semantics.
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

# Ensure backend directory is in path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from matching import (
    MatchResult,
    is_placeholder_or_empty,
    match_product_query,
    match_ingredient_query,
    match_watchlist,
    get_ingredient_alias_map,
)
from normalization import normalize_record


# ===========================================================================
# 1. Exact Product-Name Matches
# ===========================================================================
class TestExactProductMatches:
    """Verifies exact and phrase-level product matches."""

    def test_exact_single_word_product(self):
        matched, score = match_product_query("Advil", "Advil")
        assert matched is True
        assert score == 1.0

    def test_exact_case_insensitive(self):
        matched, score = match_product_query("tylenol", "TYLENOL")
        assert matched is True
        assert score == 1.0

    def test_exact_multi_word_product(self):
        matched, score = match_product_query("Tylenol Extra Strength", "Tylenol Extra Strength")
        assert matched is True
        assert score == 1.0

    def test_product_with_dosage_and_formulation_suffix(self):
        matched, score = match_product_query("Advil", "Advil PM Liquid-Gels 200mg")
        assert matched is True
        assert score == 1.0

    def test_product_with_brand_prefix(self):
        matched, score = match_product_query("Tylenol", "Childrens Tylenol Oral Suspension")
        assert matched is True
        assert score == 1.0

    def test_punctuation_and_hyphen_variants(self):
        matched, score = match_product_query("Pepto Bismol", "Pepto-Bismol Chewable Tablets")
        assert matched is True
        assert score == 1.0


# ===========================================================================
# 2. Legitimate Fuzzy Matches
# ===========================================================================
class TestLegitimateFuzzyMatches:
    """Verifies legitimate typos and orthographic variations match above threshold."""

    def test_multi_word_product_typo(self):
        # 'Strenght' typo in product name
        matched, score = match_product_query("Tylenol Extra Strength", "Tylenol Extra Strenght 500mg")
        assert matched is True
        assert score >= 0.80

    def test_slight_orthographic_variation(self):
        # 'Liqui-Gels' vs 'Liquid Gels'
        matched, score = match_product_query("Advil Liqui-Gels", "Advil Liquid Gels 200mg")
        assert matched is True
        assert score >= 0.80

    def test_single_word_typo(self):
        # 'Tylennol' (extra n) vs 'Tylenol Extra Strength'
        matched, score = match_product_query("Tylennol", "Tylenol Extra Strength")
        assert matched is True
        assert score >= 0.80

    def test_spacing_and_hyphenation_fuzzy(self):
        # 'Crest 3D White' vs 'Crest 3-D White Toothpaste'
        matched, score = match_product_query("Crest 3D White", "Crest 3-D White Toothpaste")
        assert matched is True
        assert score >= 0.80

    def test_active_ingredient_salt_form(self):
        matched, score = match_product_query("Metformin", "Metformin HCl ER Tablets")
        assert matched is True
        assert score == 1.0


# ===========================================================================
# 3. Similar But Unrelated Product Names (False Positive Prevention)
# ===========================================================================
class TestUnrelatedProductRejection:
    """Verifies similar lookalikes, shared prefixes, and non-word substrings do NOT match."""

    def test_shared_prefix_different_drug_claritin_vs_clarithromycin(self):
        # Claritin (antihistamine) must never match Clarithromycin (antibiotic)
        matched, score = match_product_query("Claritin", "Clarithromycin 500mg Tablets")
        assert matched is False, f"Claritin falsely matched Clarithromycin with score {score}"

    def test_phonetic_lookalike_celebrex_vs_celexa(self):
        # Celebrex (celecoxib) must never match Celexa (citalopram)
        matched, score = match_product_query("Celebrex", "Celexa 20mg Tablets")
        assert matched is False, f"Celebrex falsely matched Celexa with score {score}"

    def test_brand_confusion_advil_vs_aleve(self):
        matched, score = match_product_query("Advil", "Aleve Sinus & Headache")
        assert matched is False

    def test_unrelated_tylenol_vs_terenol(self):
        matched, score = match_product_query("Tylenol", "Terenol 10mg")
        assert matched is False

    def test_unrelated_zyrtec_vs_zantac(self):
        matched, score = match_product_query("Zyrtec", "Zantac 150mg")
        assert matched is False

    def test_unrelated_xanax_vs_zantac(self):
        matched, score = match_product_query("Xanax", "Zantac 75mg")
        assert matched is False

    def test_unrelated_prilosec_vs_prozac(self):
        matched, score = match_product_query("Prilosec", "Prozac 20mg")
        assert matched is False

    def test_substring_trap_bio_in_antibiotic(self):
        # 'Bio' must not match 'Antibiotic'
        matched, score = match_product_query("Bio", "Antibiotic Ointment")
        assert matched is False, f"Bio falsely matched Antibiotic with score {score}"

    def test_substring_trap_oil_in_boil_ease(self):
        # 'Oil' must not match 'Boil'
        matched, score = match_product_query("Oil", "Boil Ease Pain Relieving Ointment")
        assert matched is False, f"Oil falsely matched Boil Ease with score {score}"

    def test_substring_trap_tea_in_proteasome(self):
        # 'Tea' must not match 'Proteasome'
        matched, score = match_product_query("Tea", "Proteasome Inhibitor Injection")
        assert matched is False, f"Tea falsely matched Proteasome with score {score}"

    def test_substring_trap_care_in_scarecrow(self):
        # 'Care' must not match 'Scarecrow'
        matched, score = match_product_query("Care", "Scarecrow Mask Novelty")
        assert matched is False, f"Care falsely matched Scarecrow with score {score}"

    def test_substring_trap_art_in_smart_cream(self):
        matched, score = match_product_query("Art", "Smart Cream Skin Care")
        assert matched is False

    def test_substring_trap_cure_in_secure(self):
        matched, score = match_product_query("Cure", "Secure Denture Adhesive")
        assert matched is False


# ===========================================================================
# 4. Ingredient Aliases and Canonicalization
# ===========================================================================
class TestIngredientAliasesAndCanonicalization:
    """Verifies that synonym lists and chemical aliases correctly match canonical names."""

    @pytest.fixture
    def alias_map(self):
        return get_ingredient_alias_map()

    def test_exact_canonical_match(self, alias_map):
        matched, score = match_ingredient_query("acetaminophen", "acetaminophen", alias_map)
        assert matched is True
        assert score == 1.0

    def test_synonym_paracetamol_to_acetaminophen(self, alias_map):
        matched, score = match_ingredient_query("paracetamol", "acetaminophen", alias_map)
        assert matched is True
        assert score == 1.0

    def test_slang_alias_apap_to_acetaminophen(self, alias_map):
        matched, score = match_ingredient_query("apap", "acetaminophen", alias_map)
        assert matched is True
        assert score == 1.0

    def test_chemical_synonym_acetylsalicylic_acid_to_aspirin(self, alias_map):
        matched, score = match_ingredient_query("acetylsalicylic acid", "aspirin", alias_map)
        assert matched is True
        assert score == 1.0

    def test_abbreviation_asa_to_aspirin(self, alias_map):
        matched, score = match_ingredient_query("asa", "aspirin", alias_map)
        assert matched is True
        assert score == 1.0

    def test_contaminant_synonym_ndma_to_nitrosamine(self, alias_map):
        matched, score = match_ingredient_query("ndma", "nitrosamine", alias_map)
        assert matched is True
        assert score == 1.0

    def test_cosmetic_abbreviation_sls_to_sodium_lauryl_sulfate(self, alias_map):
        matched, score = match_ingredient_query("sls", "sodium lauryl sulfate", alias_map)
        assert matched is True
        assert score == 1.0

    def test_heavy_metal_synonym_calomel_to_mercury(self, alias_map):
        matched, score = match_ingredient_query("calomel", "mercury", alias_map)
        assert matched is True
        assert score == 1.0

    def test_salt_form_derivative_ibuprofen_in_ibuprofen_sodium(self, alias_map):
        matched, score = match_ingredient_query("ibuprofen", "ibuprofen sodium", alias_map)
        assert matched is True
        assert score >= 0.90

    def test_derivative_hydrocortisone_in_hydrocortisone_acetate(self, alias_map):
        matched, score = match_ingredient_query("hydrocortisone", "hydrocortisone acetate", alias_map)
        assert matched is True
        assert score >= 0.90

    def test_derivative_retinol_in_retinol_palmitate(self, alias_map):
        matched, score = match_ingredient_query("retinol", "retinol palmitate", alias_map)
        assert matched is True
        assert score >= 0.90

    # Non-word substring false positive tests
    def test_substring_trap_tin_in_gelatin(self, alias_map):
        matched, score = match_ingredient_query("tin", "gelatin", alias_map)
        assert matched is False, f"tin falsely matched gelatin with score {score}"

    def test_substring_trap_iron_in_interferon(self, alias_map):
        matched, score = match_ingredient_query("iron", "interferon", alias_map)
        assert matched is False, f"iron falsely matched interferon with score {score}"

    def test_substring_trap_lead_in_bleach(self, alias_map):
        matched, score = match_ingredient_query("lead", "bleach", alias_map)
        assert matched is False

    def test_generic_word_acid_does_not_match_salicylic_acid(self, alias_map):
        # Candidate 'acid' is a generic word and should not match specific 'salicylic acid'
        matched, score = match_ingredient_query("salicylic acid", "acid", alias_map)
        assert matched is False


# ===========================================================================
# 5. Missing, Inferred, and Placeholder Ingredients (Task 4)
# ===========================================================================
class TestIngredientEvidenceAndPlaceholders:
    """Verifies that missing and placeholder ingredients never match, and inferred

    ingredients are distinguished from verified evidence.
    """

    def test_placeholder_helper_identifies_synthetic_tokens(self):
        assert is_placeholder_or_empty("unknown_compound_82a39b4f") is True
        assert is_placeholder_or_empty("unknown") is True
        assert is_placeholder_or_empty("none") is True
        assert is_placeholder_or_empty("n/a") is True
        assert is_placeholder_or_empty("") is True
        assert is_placeholder_or_empty(None) is True
        assert is_placeholder_or_empty("acetaminophen") is False

    def test_placeholder_ingredient_never_matches(self):
        normalized = {
            "recall_id": "rec_001",
            "product_name": "Generic Product",
            "ingredients": ["unknown_compound_82a39b4f"],
            "inferred_fields": ["ingredients"],
            "confidence_score": 0.8,
        }
        # Neither a real ingredient nor placeholder-named queries match
        watchlist = {"ingredients": ["compound", "unknown", "unknown_compound", "acetaminophen"]}
        matches = match_watchlist(normalized, watchlist)
        assert len(matches) == 0, f"Expected 0 matches on placeholder ingredient, got {matches}"

    def test_missing_ingredients_never_match(self):
        normalized = {
            "recall_id": "rec_002",
            "product_name": "Eye Care Product",
            "ingredients": [],
            "inferred_fields": ["ingredients"],
            "confidence_score": 0.8,
        }
        watchlist = {"ingredients": ["acetaminophen", "pseudomonas"]}
        matches = match_watchlist(normalized, watchlist)
        assert len(matches) == 0

    def test_verified_ingredient_produces_verified_evidence(self):
        # Recall with explicit (non-inferred) ingredient
        normalized = {
            "recall_id": "rec_003",
            "product_name": "Extra Strength Pain Reliever",
            "ingredients": ["acetaminophen"],
            "inferred_fields": [],  # No inferred fields: ingredients is verified
            "confidence_score": 1.0,
        }
        watchlist = {"ingredients": ["paracetamol"]}  # Tests synonym + verified evidence
        matches = match_watchlist(normalized, watchlist)
        assert len(matches) == 1
        m = matches[0]
        assert m.match_type == "ingredient"
        assert m.matched_term == "paracetamol"
        assert m.score == 1.0
        assert m.is_verified is True
        assert m.evidence_type == "verified"

    def test_inferred_ingredient_is_not_treated_as_verified_evidence(self):
        # Recall where ingredient was inferred from recall_reason or product_map
        normalized = {
            "recall_id": "rec_004",
            "product_name": "Whitening Skin Lotion",
            "ingredients": ["hydroquinone"],
            "inferred_fields": ["ingredients"],  # Explicitly marked as inferred
            "confidence_score": 0.8,
        }
        watchlist = {"ingredients": ["hydroquinone"]}
        matches = match_watchlist(normalized, watchlist)
        assert len(matches) == 1
        m = matches[0]
        assert m.match_type == "ingredient"
        assert m.matched_term == "hydroquinone"
        # Must NOT be treated as verified evidence (Task 4)
        assert m.is_verified is False
        assert m.evidence_type == "inferred"


# ===========================================================================
# 6. Existing Alert Behavior & Backwards Compatibility
# ===========================================================================
class TestBackwardsCompatibilityAndSemantics:
    """Verifies that MatchResult tuple unpacking, alert fields, and normalization

    semantics maintain complete backwards compatibility.
    """

    def test_match_result_unpacks_as_3_tuple(self):
        res = MatchResult("product", "Advil", 1.0, is_verified=True, evidence_type="verified")
        # Existing callers do: match_type, matched_on, score = matches[0]
        match_type, matched_on, score = res
        assert match_type == "product"
        assert matched_on == "Advil"
        assert score == 1.0
        assert len(res) == 3

    def test_match_result_attributes_accessible(self):
        res = MatchResult("ingredient", "aspirin", 0.95, is_verified=False, evidence_type="inferred")
        assert res.match_type == "ingredient"
        assert res.matched_term == "aspirin"
        assert res.score == 0.95
        assert res.is_verified is False
        assert res.evidence_type == "inferred"

    def test_normalization_confidence_is_data_completeness(self):
        """Task 6: Verifies confidence_score represents data completeness, not match probability."""
        mapped = {
            "product_name": "Test Cream",
            "brand": "Test Brand",
            "ingredients_raw": "hydroquinone, mercury",
            "severity_raw": "Class I",
            "region_raw": "EU",
            "recall_reason": "High chemical hazard",
            "category_raw": "cosmetic",
            "source_file": "eu_notification_list.xlsx",
        }
        norm, lineage = normalize_record(mapped, [], {}, "EU Safety Gate")
        # When all 5 core fields are explicit, data completeness = 1.0
        assert norm["confidence_score"] == 1.0
        assert norm["data_completeness_score"] == 1.0
        assert norm["inferred_fields"] == []

        # When 2 core fields are inferred (e.g. missing severity and region)
        mapped_incomplete = dict(mapped)
        mapped_incomplete["severity_raw"] = None
        mapped_incomplete["region_raw"] = None
        norm_inc, _ = normalize_record(mapped_incomplete, [], {}, "EU Safety Gate")
        # 2 out of 5 core fields inferred -> 1 - 2/5 = 0.6 data completeness
        assert norm_inc["confidence_score"] == 0.6
        assert norm_inc["data_completeness_score"] == 0.6
        assert "severity" in norm_inc["inferred_fields"]
        assert "region" in norm_inc["inferred_fields"]


# ===========================================================================
# 7. Alert Model Document Structure & Matching Invariants
# ===========================================================================
class TestAlertDocumentInvariants:
    """Verifies that match results and alert documents accurately represent

    verified vs inferred evidence, match scores, and data completeness.
    """

    def test_verified_product_match_contract(self):
        normalized = {
            "recall_id": "rec_100",
            "product_name": "Tylenol Extra Strength 500mg",
            "severity": "high",
            "region": "US",
            "source": "FDA",
            "ingredients": ["acetaminophen"],
            "recall_reason": "Labeling issue",
            "confidence_score": 1.0,
            "data_completeness_score": 1.0,
            "inferred_fields": [],
        }
        matches = match_watchlist(normalized, {"products": ["Tylenol"], "ingredients": []})
        assert len(matches) == 1
        m = matches[0]
        assert m.match_type == "product"
        assert m.matched_term == "Tylenol"
        assert m.score == 1.0
        assert m.is_verified is True
        assert m.evidence_type == "verified"

        # Construct alert document exactly as run_matching_for_recall does
        match_type, matched_on, score = m
        alert_doc = {
            "alert_id": f"alert_{normalized['recall_id']}_user1",
            "user_id": "user1",
            "recall_id": normalized["recall_id"],
            "product": normalized.get("product_name"),
            "matched_on": match_type,
            "matched_term": matched_on,
            "match_score": score,
            "severity": normalized.get("severity"),
            "confidence_score": normalized.get("confidence_score"),
            "data_completeness_score": normalized.get("data_completeness_score"),
            "is_verified": getattr(m, "is_verified", True),
            "evidence_type": getattr(m, "evidence_type", "verified"),
            "read": False,
        }
        assert alert_doc["is_verified"] is True
        assert alert_doc["evidence_type"] == "verified"
        assert alert_doc["match_score"] == 1.0
        assert alert_doc["confidence_score"] == 1.0

    def test_inferred_ingredient_alert_contract(self):
        normalized = {
            "recall_id": "rec_101",
            "product_name": "Skin Brightening Lotion",
            "severity": "medium",
            "region": "EU",
            "source": "EU Safety Gate",
            "ingredients": ["hydroquinone"],
            "recall_reason": "Chemical risk",
            "confidence_score": 0.8,
            "data_completeness_score": 0.8,
            "inferred_fields": ["ingredients"],
        }
        matches = match_watchlist(normalized, {"products": [], "ingredients": ["hydroquinone"]})
        assert len(matches) == 1
        m = matches[0]
        assert m.match_type == "ingredient"
        assert m.matched_term == "hydroquinone"
        # Task 4 invariant: Inferred ingredients are NOT treated as verified evidence
        assert m.is_verified is False
        assert m.evidence_type == "inferred"

        # Construct alert document as run_matching_for_recall does
        match_type, matched_on, score = m
        alert_doc = {
            "alert_id": f"alert_{normalized['recall_id']}_user2",
            "user_id": "user2",
            "recall_id": normalized["recall_id"],
            "product": normalized.get("product_name"),
            "matched_on": match_type,
            "matched_term": matched_on,
            "match_score": score,
            "severity": normalized.get("severity"),
            "confidence_score": normalized.get("confidence_score"),
            "data_completeness_score": normalized.get("data_completeness_score"),
            "is_verified": getattr(m, "is_verified", True),
            "evidence_type": getattr(m, "evidence_type", "verified"),
            "read": False,
        }
        assert alert_doc["is_verified"] is False
        assert alert_doc["evidence_type"] == "inferred"


# ===========================================================================
# 8. Stable Recall Identity, Dismissal Preservation & Error Surfacing
# ===========================================================================
class TestStableRecallIdentityAndDismissalPreservation:
    """Verifies that recall IDs are stable across re-runs, dismissals persist,
    and genuinely new recalls create alerts without swallowing unexpected DB errors."""

    def test_reprocessing_same_recall_generates_identical_id(self):
        from normalization import generate_stable_recall_id

        mapped1 = {
            "external_id": "EU-ALERT-999",
            "source_file": "eu_notification.xlsx",
            "product_name": "Skin Cream",
        }
        id1 = generate_stable_recall_id(mapped1, "EU Safety Gate")
        id2 = generate_stable_recall_id(mapped1, "EU Safety Gate")
        assert id1 == id2
        assert id1.startswith("rec_")

        # Fingerprint fallback when external_id is absent
        mapped_fp = {
            "external_id": None,
            "product_name": "Hydro Serum",
            "batch_number": "BATCH-88",
            "recall_reason": "Contains toxic mercury",
            "region_raw": "France",
            "source_file": "safety_alert.csv",
        }
        fp1 = generate_stable_recall_id(mapped_fp, "Safety Alerts")
        fp2 = generate_stable_recall_id(mapped_fp, "Safety Alerts")
        assert fp1 == fp2

    def test_different_batch_for_same_product_generates_distinct_id(self):
        from normalization import generate_stable_recall_id

        mapped_a = {
            "product_name": "Eye Drops",
            "batch_number": "LOT-A",
            "recall_reason": "Bacterial contamination",
            "region_raw": "US",
        }
        mapped_b = {
            "product_name": "Eye Drops",
            "batch_number": "LOT-B",
            "recall_reason": "Bacterial contamination",
            "region_raw": "US",
        }
        id_a = generate_stable_recall_id(mapped_a, "US FDA")
        id_b = generate_stable_recall_id(mapped_b, "US FDA")
        assert id_a != id_b

    @staticmethod
    def _run_sync(coro):
        result = None
        stack = [coro]
        while stack:
            current = stack[-1]
            try:
                val = current.send(result)
                result = None
                if hasattr(val, "send"):
                    stack.append(val)
            except StopIteration as e:
                stack.pop()
                result = e.value
        return result

    def test_dismissed_alert_remains_dismissed_on_recall_rematch(self):
        from matching import run_matching_for_recall
        from unittest.mock import AsyncMock, MagicMock

        normalized = {
            "recall_id": "rec_stable_123",
            "product_name": "Tylenol Extra",
            "confidence_score": 1.0,
            "data_completeness_score": 1.0,
            "severity": "high",
            "region": "US",
            "source": "US FDA",
            "ingredients": ["acetaminophen"],
            "recall_reason": "Contamination",
        }

        # Mock watchlist for user_1
        async def mock_cursor_gen():
            yield {"user_id": "user_1", "products": ["Tylenol Extra"], "ingredients": []}

        mock_db = MagicMock()
        mock_db.watchlists.find.return_value = mock_cursor_gen()
        # Simulate that alert was previously dismissed in database
        mock_db.alerts.find_one = AsyncMock(return_value={
            "alert_id": "alert_rec_stable_123_user_1",
            "user_id": "user_1",
            "recall_id": "rec_stable_123",
            "dismissed": True,
        })
        mock_db.alerts.insert_one = AsyncMock()

        # Run coroutine synchronously without socketpair
        created = self._run_sync(run_matching_for_recall(mock_db, normalized))

        # Alert should NOT be created again, and insert_one should NOT be called
        assert created == 0
        mock_db.alerts.insert_one.assert_not_called()

    def test_dismissed_alert_remains_dismissed_on_watchlist_update(self):
        from matching import run_matching_for_user
        from unittest.mock import AsyncMock, MagicMock

        # Mock recall in database
        async def mock_recalls_gen():
            yield {
                "recall_id": "rec_stable_123",
                "product_name": "Tylenol Extra",
                "confidence_score": 1.0,
                "data_completeness_score": 1.0,
                "severity": "high",
                "ingredients": ["acetaminophen"],
            }

        mock_db = MagicMock()
        mock_db.normalized_recalls.find.return_value = mock_recalls_gen()
        # Alert already exists and is dismissed
        mock_db.alerts.find_one = AsyncMock(return_value={
            "alert_id": "alert_rec_stable_123_user_1",
            "user_id": "user_1",
            "recall_id": "rec_stable_123",
            "dismissed": True,
        })
        mock_db.alerts.insert_one = AsyncMock()

        created = self._run_sync(run_matching_for_user(mock_db, "user_1", {"products": ["Tylenol Extra"], "ingredients": []}))

        assert created == 0
        mock_db.alerts.insert_one.assert_not_called()

    def test_new_recall_for_same_watched_product_creates_new_alert(self):
        from matching import run_matching_for_recall
        from unittest.mock import AsyncMock, MagicMock

        # Genuinely new recall for same product name with new stable ID
        new_recall = {
            "recall_id": "rec_new_batch_456",
            "product_name": "Tylenol Extra",
            "confidence_score": 1.0,
            "data_completeness_score": 1.0,
            "severity": "high",
            "region": "US",
            "source": "US FDA",
            "ingredients": ["acetaminophen"],
            "recall_reason": "Foreign particle",
        }

        async def mock_cursor_gen():
            yield {"user_id": "user_1", "products": ["Tylenol Extra"], "ingredients": []}

        mock_db = MagicMock()
        mock_db.watchlists.find.return_value = mock_cursor_gen()
        # For this new recall_id, no alert exists yet
        mock_db.alerts.find_one = AsyncMock(return_value=None)
        mock_db.alerts.insert_one = AsyncMock()

        created = self._run_sync(run_matching_for_recall(mock_db, new_recall))

        assert created == 1
        mock_db.alerts.insert_one.assert_called_once()
        inserted_alert = mock_db.alerts.insert_one.call_args[0][0]
        assert inserted_alert["alert_id"] == "alert_rec_new_batch_456_user_1"
        assert inserted_alert["recall_id"] == "rec_new_batch_456"

    def test_unexpected_database_error_is_raised(self):
        from matching import run_matching_for_recall
        from unittest.mock import AsyncMock, MagicMock

        normalized = {
            "recall_id": "rec_db_err_999",
            "product_name": "Advil PM",
            "confidence_score": 1.0,
            "severity": "high",
        }

        async def mock_cursor_gen():
            yield {"user_id": "user_1", "products": ["Advil PM"], "ingredients": []}

        mock_db = MagicMock()
        mock_db.watchlists.find.return_value = mock_cursor_gen()
        mock_db.alerts.find_one = AsyncMock(return_value=None)
        # Simulate unexpected non-duplicate DB failure
        mock_db.alerts.insert_one = AsyncMock(side_effect=RuntimeError("Database connection lost"))

        with pytest.raises(RuntimeError) as exc_info:
            self._run_sync(run_matching_for_recall(mock_db, normalized))
        assert "Database connection lost" in str(exc_info.value)


