# Zania Q&A Bot (v2.0)

A robust, containerized, and asynchronous RAG (Retrieval-Augmented Generation) API designed to answer questions from PDF and JSON documents.

## Features
### Production-Grade RAG
* **MMR Retrieval:** Maximal Marginal Relevance for diverse, non-redundant results (k=10, fetch_k=25)
* **Smart Citations:** Automatic page-level extraction from LLM evidence sections
* **No Hallucinations:** Returns "Not found" when information isn't in the document
* **Partial Answers:** Explicitly lists "Missing:" information instead of making up details

### Performance & Reliability
* **Async I/O:** Non-blocking architecture with `ThreadPoolExecutor` for CPU-bound tasks
* **Auto Retry:** Exponential backoff for transient OpenAI API failures (via `tenacity`)
* **Token Tracking:** Full observability with cost/usage monitoring via `get_openai_callback()`
* **Efficient Chunking:** Token-aware splitting (1000 tokens, 200 overlap) for optimal retrieval

### Security & Validation
* **Input Validation:** Strict file type checks (PDF/JSON only)
* **Size Limits:** 50MB max file size, 50 questions per request
* **Early Validation:** Fast-fail before expensive embedding generation (400 Bad Request)
* **Structured Logging:** JSON logs for production monitoring and debugging

### Developer Experience
* **Docker Ready:** Single-command deployment with `docker-compose`
* **Comprehensive Tests:** 11 unit + integration tests with mocked dependencies
* **API Documentation:** Auto-generated OpenAPI/Swagger at `/docs`

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