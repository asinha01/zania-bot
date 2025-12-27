import os
import logging
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

# --- 3. CONCURRENCY HELPER ---
# This allows us to run heavy tasks without freezing the server
executor = ThreadPoolExecutor(max_workers=4)

def validate_file(file: UploadFile, max_mb: int = MAX_FILE_SIZE_MB):
    """Enforce file size and type limits."""
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Use PDF or JSON.")
    
    # Check size by seeking to the end
    file.file.seek(0, os.SEEK_END)
    size_in_bytes = file.file.tell()
    file.file.seek(0) # Reset cursor to start
    
    if size_in_bytes > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Limit is {max_mb}MB")
    return ext