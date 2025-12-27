# Zania Q&A Bot (v2.0)

A robust, containerized, and asynchronous RAG (Retrieval-Augmented Generation) API designed to answer questions from PDF and JSON documents.

## Features

* **Asynchronous Architecture:** Uses `asyncio` with `ThreadPoolExecutor` to handle file I/O and Embedding generation without blocking the main event loop.
* **Defense in Depth:**
    * **Strict Validation:** Enforces file type checks and a **50MB** size limit to prevent resource exhaustion.
    * **Resilience:** Implements exponential backoff retries (via `tenacity`) for OpenAI API calls to handle transient network failures.
    * **Graceful Degradation:** Validates inputs early to provide fast feedback (400 Bad Request) before expensive processing begins.
* **Observability:** Structured JSON logging for production-grade monitoring and debugging.
* **Containerization:** Full Docker and Docker Compose support for reproducible deployments.

## Setup & Running

**Prerequisite:** You need an OpenAI API Key (`sk-...`).

### Option 1: Docker (Recommended)
```bash
# 1. Clone repository
git clone 
cd zania-rag

# 2. Set your OpenAI API key (REQUIRED)
export OPENAI_API_KEY="sk-..."

# 3. Start services
docker-compose up --build

# 4. Access the application
# Frontend: http://localhost:8501
# API Docs: http://localhost:8000/docs
```

**Note:** Use `docker compose` (space) if you have Docker 20.10+, or `docker-compose` (hyphen) for older versions.

### Option 2: Local Development
```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set API key
export OPENAI_API_KEY="sk-..."

# 4. Start backend
uvicorn main:app --reload

# 5. Start frontend (in another terminal)
streamlit run frontend.py
```

## Usage

### API Documentation (Swagger UI)
Once running, visit **http://localhost:8000/docs** to test the API interactively.

### Example Request (cURL)
```bash
curl -X POST "http://localhost:8000/answer" \
  -F "document_file=@/path/to/your/document.pdf" \
  -F "questions_file=@/path/to/questions.json"