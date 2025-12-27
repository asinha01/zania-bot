import json
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from utils import MAX_QUESTIONS

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_invalid_doc_extension_rejected():
    files = {
        "questions_file": ("q.json", "[]", "application/json"),
        "document_file": ("doc.txt", "invalid", "text/plain"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_questions_file_must_be_json():
    files = {
        "questions_file": ("q.pdf", b"%PDF-1.4 fake", "application/pdf"),
        "document_file": ("doc.json", "{}", "application/json"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "questions_file must be a JSON file" in response.json()["detail"]


def test_invalid_questions_json_returns_400():
    files = {
        "questions_file": ("q.json", "{not valid json", "application/json"),
        "document_file": ("doc.json", "{}", "application/json"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Invalid questions JSON" in response.json()["detail"]


def test_no_questions_returns_400():
    files = {
        "questions_file": ("q.json", "[]", "application/json"),
        "document_file": ("doc.json", "{}", "application/json"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "No questions provided" in response.json()["detail"]


def test_non_string_questions_returns_400():
    files = {
        "questions_file": ("q.json", json.dumps([1, 2, 3]), "application/json"),
        "document_file": ("doc.json", "{}", "application/json"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Questions must be a list of strings" in response.json()["detail"]


def test_too_many_questions_returns_400():
    too_many = [f"Q{i}" for i in range(MAX_QUESTIONS + 1)]
    files = {
        "questions_file": ("q.json", json.dumps(too_many), "application/json"),
        "document_file": ("doc.json", "{}", "application/json"),
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Too many questions" in response.json()["detail"]


# IMPORTANT:
# main.py imports these symbols directly:
#   from rag_engine import process_file_sync, build_rag_pipeline, resilient_llm_call
# so you MUST patch "main.<name>", not "rag_engine.<name>".


@patch("main.resilient_llm_call")
@patch("main.build_rag_pipeline")
@patch("main.process_file_sync")
def test_answer_happy_path_with_mocks(mock_process, mock_build, mock_llm):
    # Arrange: avoid real parsing/embeddings/LLM calls
    mock_process.return_value = ["dummy_doc"]
    mock_build.return_value = object()

    d1 = MagicMock()
    d1.metadata = {"source": "source_doc.pdf", "page": 2}
    d2 = MagicMock()
    d2.metadata = {"source": "source_doc.pdf", "page": 5}

    mock_llm.return_value = {
        "result": "Mocked answer",
        "source_documents": [d1, d2],
    }

    questions = ["What is this doc about?"]
    files = {
        "questions_file": ("q.json", json.dumps(questions), "application/json"),
        "document_file": ("doc.json", json.dumps({"hello": "world"}), "application/json"),
    }

    # Act
    response = client.post("/answer", files=files)

    # Assert
    assert response.status_code == 200
    body = response.json()

    assert "What is this doc about?" in body
    assert body["What is this doc about?"]["answer"] == "Mocked answer"
    assert body["What is this doc about?"]["citations"] == [
        {"source": "source_doc.pdf", "page": 2},
        {"source": "source_doc.pdf", "page": 5},
    ]

    assert mock_process.called
    assert mock_build.called
    assert mock_llm.called


@patch("main.resilient_llm_call", side_effect=Exception("boom"))
@patch("main.build_rag_pipeline")
@patch("main.process_file_sync")
def test_llm_failure_is_handled_per_question(mock_process, mock_build, mock_llm):
    mock_process.return_value = ["dummy_doc"]
    mock_build.return_value = object()

    questions = ["Q1"]
    files = {
        "questions_file": ("q.json", json.dumps(questions), "application/json"),
        "document_file": ("doc.json", "{}", "application/json"),
    }

    response = client.post("/answer", files=files)
    assert response.status_code == 200
    body = response.json()

    assert body["Q1"]["answer"].startswith("Error:")
    assert body["Q1"]["citations"] == []
