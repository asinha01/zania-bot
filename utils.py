import os
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from fastapi import UploadFile, HTTPException

# --- 1. OBSERVABILITY (JSON LOGGING) ---
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("zania-bot")

# --- 2. CONFIG ---
MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".pdf", ".json"}
MAX_QUESTIONS = 50  # Fix #5: limit number of questions

# --- 3. CONCURRENCY HELPER ---
executor = ThreadPoolExecutor(max_workers=4)

def save_upload_to_path(upload: UploadFile, path: str) -> None:
    """Save UploadFile to disk safely (ensures the file handle is closed)."""
    with open(path, "wb") as out:
        shutil.copyfileobj(upload.file, out)

def validate_file(file: UploadFile, max_mb: int = MAX_FILE_SIZE_MB) -> str:
    """Enforce file size and type limits for general uploads (PDF/JSON docs)."""
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Use PDF or JSON.")

    # Check size by seeking to the end
    file.file.seek(0, os.SEEK_END)
    size_in_bytes = file.file.tell()
    file.file.seek(0)  # Reset cursor to start

    if size_in_bytes > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Limit is {max_mb}MB")

    return ext

def validate_questions_file(file: UploadFile, max_mb: int = 5) -> str:
    """Fix #3: questions_file must be JSON (not PDF). Keep a smaller size cap."""
    filename = file.filename or "questions.json"
    ext = os.path.splitext(filename)[1].lower()
    if ext != ".json":
        raise HTTPException(status_code=400, detail="questions_file must be a JSON file.")
    return validate_file(file, max_mb=max_mb)
