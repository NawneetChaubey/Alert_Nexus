"""Ingestion router for manual spreadsheet file uploads."""
from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import get_current_user
from pipeline import ingest_file

log = logging.getLogger("ingest")
router = APIRouter(prefix="/ingest", tags=["ingest"])

# Maximum allowed upload size: 50 MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload and process a recall dataset (CSV or Excel).

    Enforces:
    - Non-empty filename and supported extension validation (.csv, .xlsx, .xls)
    - Collision-free, unique temporary file per upload
    - Upload size ceiling (50MB) and empty file rejection (0 bytes)
    - Guaranteed temporary file cleanup in a finally block
    - Structured error responses on corrupt/malformed files
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="no filename provided")

    raw_filename = Path(file.filename).name
    suffix = Path(raw_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file extension '{suffix}'. Only .csv, .xlsx, and .xls are supported.",
        )

    # Collision-free temporary file path
    unique_id = uuid.uuid4().hex[:12]
    safe_stem = "".join(c for c in Path(raw_filename).stem if c.isalnum() or c in ("-", "_"))[:32] or "upload"
    temp_filename = f"upload_{unique_id}_{safe_stem}{suffix}"
    tmp_path = Path(tempfile.gettempdir()) / temp_filename

    total_bytes = 0
    try:
        # Stream file to disk while enforcing max upload size
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB buffer
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"file exceeds maximum allowed size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
                    )
                f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="file is empty (0 bytes)")

        try:
            result = await ingest_file(tmp_path, run_matching=True, source_name=raw_filename)
            return result
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            log.exception("failed to process uploaded file %s", raw_filename)
            raise HTTPException(status_code=400, detail=f"failed to process file: {e}")

    finally:
        # Guaranteed cleanup in finally block
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception as e:
                log.warning("failed to delete temporary file %s: %s", tmp_path, e)
