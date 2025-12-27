import io
import pytest
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import HTTPException

from utils import validate_file, validate_questions_file


def make_upload(filename: str, content: bytes) -> StarletteUploadFile:
    return StarletteUploadFile(filename=filename, file=io.BytesIO(content))


def test_validate_file_rejects_bad_extension():
    f = make_upload("x.txt", b"hi")
    with pytest.raises(HTTPException) as e:
        validate_file(f)
    assert e.value.status_code == 400


def test_validate_questions_file_requires_json():
    f = make_upload("q.pdf", b"%PDF-1.4")
    with pytest.raises(HTTPException) as e:
        validate_questions_file(f)
    assert e.value.status_code == 400


def test_validate_file_size_limit():
    big = b"a" * (51 * 1024 * 1024)  # 51MB
    f = make_upload("x.json", big)
    with pytest.raises(HTTPException) as e:
        validate_file(f, max_mb=50)
    assert e.value.status_code == 400
    assert "File too large" in e.value.detail
