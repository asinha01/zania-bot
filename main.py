import os
import json
import shutil
import tempfile
import asyncio
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import logger, validate_file, executor
from rag_engine import process_file_sync, build_rag_pipeline, resilient_llm_call

app = FastAPI(title="Zania Q&A Bot", description="Async RAG Architecture v2")

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "active", "version": "2.0"}

@app.post("/answer")
async def generate_answers(
    questions_file: UploadFile = File(...),
    document_file: UploadFile = File(...)
):
    start_time = time.time()
    
    # 1. VALIDATION (Error Handling)
    doc_ext = validate_file(document_file)
    validate_file(questions_file)

    # Use TempDir for auto-cleanup (Memory Safety)
    with tempfile.TemporaryDirectory() as temp_work_dir:
        local_doc_path = os.path.join(temp_work_dir, f"source_doc{doc_ext}")
        local_q_path = os.path.join(temp_work_dir, "questions.json")

        # 2. ASYNC FILE SAVE (Performance)
        # We run the blocking I/O in a thread executor
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(executor, lambda: shutil.copyfileobj(document_file.file, open(local_doc_path, "wb")))
            await loop.run_in_executor(executor, lambda: shutil.copyfileobj(questions_file.file, open(local_q_path, "wb")))
        except Exception as e:
            logger.error(f"File write error: {e}")
            raise HTTPException(status_code=500, detail="Server failed to save upload.")

        # 3. ASYNC PROCESSING
        # Run heavy processing in thread
        raw_documents = await loop.run_in_executor(executor, process_file_sync, local_doc_path, doc_ext)
        
        # 4. BUILD PIPELINE
        rag_pipeline = await loop.run_in_executor(executor, build_rag_pipeline, raw_documents)

        # 5. PROCESS QUESTIONS
        with open(local_q_path, 'r') as f:
            q_data = json.load(f)
        
        # Robust JSON handling
        questions = q_data if isinstance(q_data, list) else q_data.get("questions", [])
        
        results = {}
        for q in questions:
            try:
                # Concurrent safe call
                response = await loop.run_in_executor(executor, resilient_llm_call, rag_pipeline, q)
                results[q] = response['result']
            except Exception as e:
                logger.error(f"LLM Error on question '{q}': {e}")
                results[q] = "Error: Service unavailable for this query."

        # Metrics Log
        duration = time.time() - start_time
        logger.info(json.dumps({
            "event": "processed_request", 
            "duration_sec": duration, 
            "question_count": len(questions)
        }))

        return results