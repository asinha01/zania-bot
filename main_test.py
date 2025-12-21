import os
import json
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app

client = TestClient(app)

# 1. Test the Health Check (Basic connectivity)
def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "active", "message": "Zania Bot is ready to answer questions."}

# 2. Test Input Validation (What happens if I send the wrong file type?)
def test_invalid_file_type():
    # Create dummy files
    files = {
        'questions_file': ('q.json', json.dumps(["Question?"]), 'application/json'),
        'document_file': ('bad.txt', b"This is a text file", 'text/plain')  # TXT is not allowed
    }
    response = client.post("/answer", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()['detail']

# 3. Test the Full Flow (Mocking the AI so it doesn't cost money)
@patch("main.RetrievalQA")
@patch("main.FAISS")
@patch("main.OpenAIEmbeddings")
def test_answer_endpoint(mock_embeddings, mock_faiss, mock_chain):
    # Setup the mock to return a fake answer
    mock_chain_instance = MagicMock()
    mock_chain_instance.invoke.return_value = {"result": "This is a mock answer."}
    mock_chain.from_chain_type.return_value = mock_chain_instance

    # Create dummy valid files
    questions_content = json.dumps(["What is the summary?"])
    pdf_content = b"%PDF-1.4 mock pdf content" # Minimal PDF header
    
    files = {
        'questions_file': ('questions.json', questions_content, 'application/json'),
        'document_file': ('doc.pdf', pdf_content, 'application/pdf')
    }

    response = client.post("/answer", files=files)

    # Assertions
    assert response.status_code == 200
    json_response = response.json()
    assert "What is the summary?" in json_response
    assert json_response["What is the summary?"] == "This is a mock answer."