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

### Option 1: Docker Compose (Recommended)
This is the easiest way to run the application in a clean environment.

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-link>
    cd <repo-folder>
    ```

2.  **Configure the API Key:**
    Create a `.env` file in the root directory and paste your key:
    ```bash
    echo "OPENAI_API_KEY=sk-proj-..." > .env
    ```

3.  **Run the application:**
    ```bash
    docker compose up --build
    ```
    The API will be available at `http://localhost:8000`.

### Option 2: Local Python
If you prefer running without Docker:

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set the API Key:**
    * **Mac/Linux:** `export OPENAI_API_KEY="sk-proj-..."`
    * **Windows:** `$env:OPENAI_API_KEY="sk-proj-..."`

3.  **Run the server:**
    ```bash
    uvicorn main:app --reload
    ```

## 🧪 Usage

### API Documentation (Swagger UI)
Once running, visit **http://localhost:8000/docs** to test the API interactively.

### Example Request (cURL)
```bash
curl -X POST "http://localhost:8000/answer" \
  -F "document_file=@/path/to/your/document.pdf" \
  -F "questions_file=@/path/to/questions.json"