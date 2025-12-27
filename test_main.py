import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

def test_health():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "active"

def test_invalid_extension():
    """Test that invalid files are rejected."""
    files = {
        'questions_file': ('q.json', '[]', 'application/json'),
        'document_file': ('doc.txt', 'invalid content', 'text/plain')
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]