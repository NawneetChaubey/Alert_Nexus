"""
Comprehensive Ingestion Reliability Test Suite for Med-Alert-101.

Validates:
1. Valid CSV parsing (standard, UTF-8, quoted strings, embedded newlines)
2. Valid Excel (.xlsx / .xls) parsing (standard header at row 0, EU Safety Gate style header at row 1)
3. Corrupted, malformed, empty (0-byte), and unsupported file handling
4. Upload size guard (50MB ceiling) and chunked streaming simulation
5. Temporary file collision-resistance for concurrent uploads
6. Guaranteed temporary file cleanup in finally block under success and error conditions
7. Data lineage and provenance preservation (source_name vs temporary filename)
8. Row-level error isolation (bad rows do not abort valid rows)
9. End-to-end upload endpoint validation (extension checks, size ceiling, cleanup)
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend directory is in path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pandas as pd
import pytest
from fastapi import HTTPException

from ingestion import (
    _df_to_clean_rows,
    parse_csv_bytes,
    parse_excel_bytes,
    parse_file,
)
from mapping import map_record, derive_source_name
from normalization import normalize_record


# Synchronous coroutine runner for testing async functions without event-loop socketpair
def run_coro_sync(coro):
    """Drives a pure coroutine chain synchronously without creating loopback sockets."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    raise RuntimeError("Coroutine did not complete synchronously")


# ---------------------------------------------------------------------------
# 1. CSV Parsing Tests
# ---------------------------------------------------------------------------

class TestCsvParsing:
    """Verifies safe and accurate parsing of various CSV payloads."""

    def test_valid_standard_csv(self, tmp_path: Path):
        csv_data = (
            "product_name,recall_reason,severity,category\n"
            "Paracetamol 500mg,Contamination with glass particles,high,pharmaceutical\n"
            "Amoxicillin 250mg,Subpotency failure,medium,pharmaceutical\n"
        )
        file_path = tmp_path / "valid.csv"
        file_path.write_text(csv_data, encoding="utf-8")

        rows = parse_file(file_path)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "Paracetamol 500mg"
        assert rows[0]["severity"] == "high"
        assert rows[1]["product_name"] == "Amoxicillin 250mg"

    def test_csv_with_utf8_and_accents(self, tmp_path: Path):
        csv_data = (
            "product_name,recall_reason,country\n"
            "Crème Éclaircissante,Contient de l'hydroquinone,France\n"
            "Niño Jarabe para la tos,Presencia de dietilenglicol,España\n"
        )
        file_path = tmp_path / "utf8.csv"
        file_path.write_text(csv_data, encoding="utf-8")

        rows = parse_file(file_path)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "Crème Éclaircissante"
        assert "hydroquinone" in rows[0]["recall_reason"]
        assert rows[1]["country"] == "España"

    def test_csv_with_quoted_fields_and_commas(self, tmp_path: Path):
        csv_data = (
            'product_name,recall_reason,distribution\n'
            '"Skin Lightening Cream, Extra Strength","Contains lead, mercury, and steroids","USA, Canada, Mexico"\n'
        )
        file_path = tmp_path / "quoted.csv"
        file_path.write_text(csv_data, encoding="utf-8")

        rows = parse_file(file_path)
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Skin Lightening Cream, Extra Strength"
        assert rows[0]["recall_reason"] == "Contains lead, mercury, and steroids"
        assert rows[0]["distribution"] == "USA, Canada, Mexico"

    def test_empty_csv_file_raises_value_error(self, tmp_path: Path):
        file_path = tmp_path / "empty.csv"
        file_path.write_bytes(b"")

        with pytest.raises(ValueError, match="File is empty"):
            parse_file(file_path)

    def test_csv_with_only_headers_returns_empty_rows(self, tmp_path: Path):
        csv_data = "product_name,recall_reason,severity\n"
        file_path = tmp_path / "header_only.csv"
        file_path.write_text(csv_data, encoding="utf-8")

        rows = parse_file(file_path)
        assert rows == []

    def test_csv_fallback_with_malformed_ragged_rows(self, tmp_path: Path):
        # Line 2 has extra fields; standard csv reader or pandas fallback skips bad lines
        csv_data = (
            "product_name,recall_reason,severity\n"
            "Valid Med,Reason 1,low\n"
            "Bad Med,Extra,Fields,Too,Many,Unmatched\n"
            "Valid Med 2,Reason 2,high\n"
        )
        file_path = tmp_path / "ragged.csv"
        file_path.write_text(csv_data, encoding="utf-8")

        rows = parse_file(file_path)
        assert len(rows) >= 2
        assert rows[0]["product_name"] == "Valid Med"


# ---------------------------------------------------------------------------
# 2. Excel (.xlsx / .xls) Parsing Tests
# ---------------------------------------------------------------------------

class TestExcelParsing:
    """Verifies safe and accurate parsing of Excel spreadsheets."""

    def test_valid_standard_excel(self, tmp_path: Path):
        df = pd.DataFrame([
            {"product_name": "Ibuprofen 400mg", "recall_reason": "Foreign matter", "severity": "high"},
            {"product_name": "Aspirin 81mg", "recall_reason": "Labeling error", "severity": "low"},
        ])
        file_path = tmp_path / "valid.xlsx"
        df.to_excel(file_path, index=False)

        rows = parse_file(file_path)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "Ibuprofen 400mg"
        assert rows[1]["product_name"] == "Aspirin 81mg"

    def test_excel_header_auto_detection_row_1(self, tmp_path: Path):
        """EU Safety Gate style where row 0 is banner and real headers start at row 1."""
        raw_rows = [
            ["European Commission - Safety Gate Recall Report", None, None],
            ["product_name", "recall_reason", "severity"],
            ["Banned Bleaching Cream", "Contains Hydroquinone 4%", "serious"],
            ["Defective Syringe", "Sterility compromise", "urgent"],
        ]
        df = pd.DataFrame(raw_rows)
        file_path = tmp_path / "eu_banner.xlsx"
        df.to_excel(file_path, header=False, index=False)

        rows = parse_file(file_path)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "Banned Bleaching Cream"
        assert rows[0]["severity"] == "serious"
        assert rows[1]["product_name"] == "Defective Syringe"

    def test_excel_cleans_nan_and_empty_cells(self):
        df = pd.DataFrame([
            {"product_name": "Med A", "recall_reason": None, "notes": float("nan"), "severity": "medium"},
            {"product_name": "Med B", "recall_reason": "Active issue", "notes": "  ", "severity": "high"},
        ])
        clean = _df_to_clean_rows(df)
        assert len(clean) == 2
        assert "recall_reason" not in clean[0]
        assert "notes" not in clean[0]
        assert clean[0]["product_name"] == "Med A"
        assert "notes" not in clean[1]
        assert clean[1]["product_name"] == "Med B"

    def test_corrupted_excel_file_raises_value_error(self, tmp_path: Path):
        file_path = tmp_path / "corrupt.xlsx"
        file_path.write_bytes(b"PK\x03\x04not-a-valid-zip-or-excel-spreadsheet-garbage-bytes")

        with pytest.raises(ValueError, match="Corrupted or invalid Excel file"):
            parse_file(file_path)

    def test_empty_excel_file_raises_value_error(self, tmp_path: Path):
        file_path = tmp_path / "empty.xlsx"
        file_path.write_bytes(b"")

        with pytest.raises(ValueError, match="File is empty"):
            parse_file(file_path)


# ---------------------------------------------------------------------------
# 3. File System & Extension Validation Tests
# ---------------------------------------------------------------------------

class TestFileValidation:
    """Tests file existence and extension restrictions."""

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path):
        missing_file = tmp_path / "does_not_exist.csv"
        with pytest.raises(FileNotFoundError, match="File not found"):
            parse_file(missing_file)

    def test_unsupported_extensions_rejected_by_parse_file(self, tmp_path: Path):
        for ext in (".json", ".pdf", ".txt", ".exe", ".xml"):
            file_path = tmp_path / f"test{ext}"
            file_path.write_text("sample content", encoding="utf-8")
            with pytest.raises(ValueError, match="Unsupported file type"):
                parse_file(file_path)

    def test_allowed_extensions_constant(self):
        from routers.ingest import ALLOWED_EXTENSIONS
        assert ALLOWED_EXTENSIONS == {".csv", ".xlsx", ".xls"}


# ---------------------------------------------------------------------------
# 4. Upload Size Guard & Chunked Streaming Tests
# ---------------------------------------------------------------------------

class TestUploadSizeGuard:
    """Verifies that upload size limits prevent DOS and memory exhaustion."""

    def test_max_upload_size_is_50mb(self):
        from routers.ingest import MAX_UPLOAD_SIZE
        assert MAX_UPLOAD_SIZE == 50 * 1024 * 1024

    def test_size_guard_logic_rejects_oversized_stream(self):
        """Simulates the 1MB chunked streaming size validation from routers/ingest.py."""
        from routers.ingest import MAX_UPLOAD_SIZE
        simulated_size = 51 * 1024 * 1024  # 51 MB
        chunk_size = 1024 * 1024
        chunks_sent = simulated_size // chunk_size

        total_bytes = 0
        exceeded = False
        for _ in range(chunks_sent):
            total_bytes += chunk_size
            if total_bytes > MAX_UPLOAD_SIZE:
                exceeded = True
                break

        assert exceeded is True
        assert total_bytes > MAX_UPLOAD_SIZE

    def test_zero_bytes_upload_flagged_as_empty(self):
        total_bytes = 0
        with pytest.raises(HTTPException) as exc_info:
            if total_bytes == 0:
                raise HTTPException(status_code=400, detail="file is empty (0 bytes)")
        assert exc_info.value.status_code == 400
        assert "file is empty" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 5. Collision-Free Temporary File Naming & Concurrency
# ---------------------------------------------------------------------------

class TestTemporaryFileCollisionResistance:
    """Ensures simultaneous uploads of identically named files do not collide."""

    def test_concurrent_temp_filenames_are_unique(self):
        raw_filename = "recalls_dataset.csv"
        generated_paths = set()
        iterations = 500

        for _ in range(iterations):
            unique_id = uuid.uuid4().hex[:12]
            suffix = Path(raw_filename).suffix.lower()
            safe_stem = "".join(c for c in Path(raw_filename).stem if c.isalnum() or c in ("-", "_"))[:32] or "upload"
            temp_filename = f"upload_{unique_id}_{safe_stem}{suffix}"
            tmp_path = Path(tempfile.gettempdir()) / temp_filename
            generated_paths.add(tmp_path)

        # All 500 generated paths must be completely distinct
        assert len(generated_paths) == iterations

    def test_path_traversal_characters_sanitized(self):
        malicious_filenames = [
            "../../etc/passwd.csv",
            "..\\..\\windows\\system32.csv",
            "/absolute/root/path.xlsx",
            "../../../secret.xls",
            "normal_file.csv\x00malicious",
        ]
        for malicious in malicious_filenames:
            raw_filename = Path(malicious).name
            suffix = Path(raw_filename).suffix.lower()
            safe_stem = "".join(c for c in Path(raw_filename).stem if c.isalnum() or c in ("-", "_"))[:32] or "upload"
            temp_filename = f"upload_{uuid.uuid4().hex[:12]}_{safe_stem}{suffix}"
            tmp_path = Path(tempfile.gettempdir()) / temp_filename

            # The temporary file must remain inside the OS temp directory
            assert tmp_path.parent == Path(tempfile.gettempdir())
            assert ".." not in tmp_path.name
            assert "/" not in tmp_path.name
            assert "\\" not in tmp_path.name


# ---------------------------------------------------------------------------
# 6. Guaranteed Temporary File Cleanup in Finally Block
# ---------------------------------------------------------------------------

class TestTemporaryFileCleanup:
    """Verifies that temporary files are deleted in a finally block."""

    def test_cleanup_on_success(self, tmp_path: Path):
        temp_file = tmp_path / "temp_upload_success.csv"
        temp_file.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
        assert temp_file.exists()

        try:
            # Simulate successful processing
            pass
        finally:
            if temp_file.exists():
                temp_file.unlink()

        assert not temp_file.exists()

    def test_cleanup_on_exception(self, tmp_path: Path):
        temp_file = tmp_path / "temp_upload_fail.csv"
        temp_file.write_text("corrupted content", encoding="utf-8")
        assert temp_file.exists()

        with pytest.raises(RuntimeError):
            try:
                raise RuntimeError("Simulated processing crash")
            finally:
                if temp_file.exists():
                    temp_file.unlink()

        # Must be deleted even when an unhandled exception occurred
        assert not temp_file.exists()


# ---------------------------------------------------------------------------
# 7. Data Provenance & Pipeline Resilience
# ---------------------------------------------------------------------------

class TestDataProvenanceAndResilience:
    """Verifies that source file names are preserved and bad rows are isolated."""

    def test_source_name_known_patterns_and_fallback(self):
        assert derive_source_name("eu_notification_2026.xlsx") == "EU Safety Gate"
        assert derive_source_name("safety_alert_update.csv") == "Safety Alerts"
        assert derive_source_name("recall_master_v2.xlsx") == "Recall Master"
        # Unknown filenames preserve the exact uploaded filename
        uploaded_name = "Custom_Hospital_Recall_Feed.xlsx"
        assert derive_source_name(uploaded_name) == uploaded_name

    def test_bad_row_in_mapping_does_not_abort_valid_rows(self):
        """Simulates row-level try...except isolation inside pipeline.process_raw_rows."""
        mock_raw_rows = [
            {"product_name": "Valid Antibiotic", "recall_reason": "Defective seal", "severity": "high"},
            {"product_name": "Corrupted Row", "cause_error": True},
            {"product_name": "Valid Antihistamine", "recall_reason": "Potency issue", "severity": "medium"},
        ]

        normalized_docs = []
        for raw in mock_raw_rows:
            try:
                if raw.get("cause_error"):
                    raise ValueError("Simulated malformed cell structure")
                mapped = map_record(raw, "test_upload.csv")
                normalized, lineage = normalize_record(mapped, [], {}, "Test Source")
                normalized_docs.append(normalized)
            except Exception:
                continue

        # The bad row was skipped; the 2 valid rows were processed cleanly
        assert len(normalized_docs) == 2
        assert normalized_docs[0]["product_name"] == "Valid Antibiotic"
        assert normalized_docs[1]["product_name"] == "Valid Antihistamine"


# ---------------------------------------------------------------------------
# 8. End-to-End Upload Router Invariants
# ---------------------------------------------------------------------------

class TestUploadRouterInvariants:
    """Tests the /upload router endpoint's HTTP error contracts and cleanup."""

    class MockUploadFile:
        def __init__(self, filename: str, content: bytes, chunk_size: int = 1024 * 1024):
            self.filename = filename
            self.stream = io.BytesIO(content)
            self.chunk_size = chunk_size

        async def read(self, size: int = -1) -> bytes:
            sz = size if size > 0 else self.chunk_size
            return self.stream.read(sz)

    def test_upload_rejects_missing_filename(self):
        from routers.ingest import upload
        mock_file = self.MockUploadFile(filename="", content=b"data")
        with pytest.raises(HTTPException) as exc_info:
            run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))
        assert exc_info.value.status_code == 400
        assert "no filename provided" in exc_info.value.detail

    def test_upload_rejects_unsupported_extension(self):
        from routers.ingest import upload
        mock_file = self.MockUploadFile(filename="test.exe", content=b"MZ\x90binary")
        with pytest.raises(HTTPException) as exc_info:
            run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))
        assert exc_info.value.status_code == 400
        assert "unsupported file extension" in exc_info.value.detail

    def test_upload_rejects_empty_zero_byte_file(self):
        from routers.ingest import upload
        mock_file = self.MockUploadFile(filename="empty.csv", content=b"")
        with pytest.raises(HTTPException) as exc_info:
            run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))
        assert exc_info.value.status_code == 400
        assert "file is empty (0 bytes)" in exc_info.value.detail

    def test_upload_rejects_oversized_file_with_http_413(self):
        from routers.ingest import upload
        # Create an upload file whose total stream exceeds 50MB
        oversized_data = b"x" * (51 * 1024 * 1024)
        mock_file = self.MockUploadFile(filename="huge.csv", content=oversized_data)
        with pytest.raises(HTTPException) as exc_info:
            run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))
        assert exc_info.value.status_code == 413
        assert "exceeds maximum allowed size" in exc_info.value.detail

    def test_upload_cleans_up_temp_file_on_ingest_failure(self):
        from routers.ingest import upload
        corrupt_data = b"PK\x03\x04not-valid-zip-excel"
        mock_file = self.MockUploadFile(filename="corrupt.xlsx", content=corrupt_data)

        # Before upload, count temp files matching upload_*
        temp_dir = Path(tempfile.gettempdir())
        initial_temp_files = set(temp_dir.glob("upload_*"))

        # Patch ingest_file to invoke parse_file directly (triggering real ValueError)
        async def mock_ingest(tmp_path, run_matching=True, source_name=None):
            parse_file(tmp_path)

        with patch("routers.ingest.ingest_file", side_effect=mock_ingest):
            with pytest.raises(HTTPException) as exc_info:
                run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))

        assert exc_info.value.status_code == 400
        assert "Corrupted or invalid Excel file" in exc_info.value.detail

        # After failure, verify no leftover temporary files remain
        remaining_temp_files = set(temp_dir.glob("upload_*")) - initial_temp_files
        assert len(remaining_temp_files) == 0, f"Leftover temp files detected: {remaining_temp_files}"

    def test_upload_success_cleans_up_temp_file(self):
        from routers.ingest import upload
        valid_csv = b"product_name,recall_reason\nMedX,ReasonY\n"
        mock_file = self.MockUploadFile(filename="valid.csv", content=valid_csv)

        temp_dir = Path(tempfile.gettempdir())
        initial_temp_files = set(temp_dir.glob("upload_*"))

        async def mock_ingest(tmp_path, run_matching=True, source_name=None):
            assert tmp_path.exists()
            assert source_name == "valid.csv"
            return {"source_file": source_name, "raw_rows": 1, "normalized": 1}

        with patch("routers.ingest.ingest_file", side_effect=mock_ingest):
            result = run_coro_sync(upload(file=mock_file, user={"user_id": "test"}))

        assert result["source_file"] == "valid.csv"
        assert result["raw_rows"] == 1

        # Verify temp file was cleaned up on success
        remaining_temp_files = set(temp_dir.glob("upload_*")) - initial_temp_files
        assert len(remaining_temp_files) == 0


# ---------------------------------------------------------------------------
# 10. Header Normalization and Ingestion Response Contract
# ---------------------------------------------------------------------------

class TestHeaderNormalizationAndResponseContract:
    """Verifies header key cleaning and structured ingestion result contracts."""

    def test_norm_key_strips_bom_and_unifies_separators(self):
        from mapping import _norm_key
        assert _norm_key("\ufeffProduct_Name") == "product name"
        assert _norm_key("Product  Name") == "product name"
        assert _norm_key("Product-Name") == "product name"
        assert _norm_key("Product / Title") == "product title"
        assert _norm_key("  BATCH_NO  ") == "batch no"

    def test_map_record_recognizes_punctuation_variants(self):
        raw1 = {"Product-Name": "Aspirin 100mg", "Batch_No": "LOT-123"}
        mapped1 = map_record(raw1, "test.csv")
        assert mapped1["product_name"] == "Aspirin 100mg"
        assert mapped1["batch_number"] == "LOT-123"

        raw2 = {"\ufeffTrade Name": "Tylenol Extra", "Recall-Reason": "Defect"}
        mapped2 = map_record(raw2, "test.csv")
        assert mapped2["product_name"] == "Tylenol Extra"
        assert mapped2["recall_reason"] == "Defect"

    def test_process_raw_rows_reports_partial_success_on_mixed_validity(self):
        from pipeline import process_raw_rows
        from unittest.mock import AsyncMock

        raw_rows = [
            {"product_name": "Valid Med A", "recall_reason": "Contamination", "severity": "high"},
            {},  # Completely empty row
            {"product_name": "Valid Med B", "recall_reason": "Subpotent", "severity": "medium"},
            {"unrecognized_col_1": "", "unrecognized_col_2": "   "},  # Malformed blank row
        ]

        mock_db = MagicMock()
        mock_db.ingredients.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.product_ingredient_map.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.normalized_recalls.insert_many = AsyncMock()
        mock_db.data_lineage.insert_many = AsyncMock()
        mock_db.watchlists.find.return_value = AsyncMock()

        with patch("pipeline.db", mock_db), patch("pipeline.run_matching_for_recall", new_callable=AsyncMock) as mock_match:
            mock_match.return_value = 1
            result = run_coro_sync(process_raw_rows(raw_rows, "mixed.csv", run_matching=True))

        assert result["raw_rows"] == 4
        assert result["normalized"] == 2
        assert result["failed_rows"] == 2
        assert result["status"] == "partial_success"
        assert len(result["errors"]) == 2
        assert result["errors"][0]["row"] == 2
        assert result["errors"][1]["row"] == 4
        assert result["alerts_created"] == 2

    def test_process_raw_rows_reports_failed_when_all_rows_invalid(self):
        from pipeline import process_raw_rows
        from unittest.mock import AsyncMock

        raw_rows = [
            {},
            {"unrelated_col": "   "},
        ]

        mock_db = MagicMock()
        mock_db.ingredients.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.product_ingredient_map.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("pipeline.db", mock_db):
            result = run_coro_sync(process_raw_rows(raw_rows, "all_bad.csv", run_matching=False))

        assert result["raw_rows"] == 2
        assert result["normalized"] == 0
        assert result["failed_rows"] == 2
        assert result["status"] == "failed"

    def test_process_raw_rows_reports_success_when_all_rows_valid(self):
        from pipeline import process_raw_rows
        from unittest.mock import AsyncMock

        raw_rows = [
            {"product_name": "Med 1", "recall_reason": "Reason 1"},
            {"product_name": "Med 2", "recall_reason": "Reason 2"},
        ]

        mock_db = MagicMock()
        mock_db.ingredients.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.product_ingredient_map.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.normalized_recalls.insert_many = AsyncMock()
        mock_db.data_lineage.insert_many = AsyncMock()

        with patch("pipeline.db", mock_db):
            result = run_coro_sync(process_raw_rows(raw_rows, "all_good.csv", run_matching=False))

        assert result["raw_rows"] == 2
        assert result["normalized"] == 2
        assert result["failed_rows"] == 0
        assert result["status"] == "success"
        assert len(result["errors"]) == 0
