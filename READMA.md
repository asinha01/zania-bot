# Zania AI Challenge - QA Bot

A production-ready FastAPI backend that leverages OpenAI (GPT-4o-mini) and LangChain to answer questions based on the content of uploaded documents (PDF or JSON).

## Features
- **RAG Pipeline:** Uses Retrieval Augmented Generation to provide accurate answers based *only* on the provided document.
- **Vector Search:** Implements `FAISS` for efficient similarity search within document chunks.
- **Robust Error Handling:** Validates file types and handles malformed JSON inputs gracefully.
- **Automated Tests:** Includes a test suite to verify endpoints and logic.

## Project Structure
- `main.py`: The application entry point and logic.
- `test_main.py`: Unit and integration tests using `pytest`.
- `requirements.txt`: Project dependencies.

## Setup & Installation

1. **Create a Virtual Environment (Optional but recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate