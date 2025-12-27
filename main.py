# main.py

from dotenv import load_dotenv
load_dotenv()  # loads OPENAI_API_KEY from .env if present

import os
import re
import json
import tempfile
import asyncio
import time

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from utils import (
    logger,
    validate_file,
    validate_questions_file,
    save_upload_to_path,
    executor,
    MAX_QUESTIONS,
)
from rag_engine import process_file_sync, build_rag_pipeline, resilient_llm_call

app = FastAPI(title="Zania Q&A Bot", description="Async RAG Architecture v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _pages_mentioned(answer_text: str) -> set:
    """
    Extract page numbers mentioned by the model in Evidence lines.
    Matches patterns like:
      - (page 48)
      - page=48
      - page 48
      - page= 48
    """
    pages = set()
    for m in re.finditer(r"\bpage\s*=?\s*(\d+)\b", answer_text, flags=re.IGNORECASE):
        try:
            pages.add(int(m.group(1)))
        except Exception:
            pass
    return pages

def _coerce_int(v):
    try:
        return int(v)
    except Exception:
        return None

@app.get("/health")
def health_check():
    return {"status": "active", "version": "2.0"}

@app.post("/answer")
async def generate_answers(
    questions_file: UploadFile = File(...),
    document_file: UploadFile = File(...)
):
    start_time = time.time()

    # 1) VALIDATION
    doc_ext = validate_file(document_file)
    validate_questions_file(questions_file)

    with tempfile.TemporaryDirectory() as temp_work_dir:
        local_doc_path = os.path.join(temp_work_dir, f"source_doc{doc_ext}")
        local_q_path = os.path.join(temp_work_dir, "questions.json")

        # 2) SAVE UPLOADS (async offload)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(executor, save_upload_to_path, document_file, local_doc_path)
            await loop.run_in_executor(executor, save_upload_to_path, questions_file, local_q_path)
        except Exception as e:
            logger.error(f"File write error: {e}")
            raise HTTPException(status_code=500, detail="Server failed to save upload.")

        # 3) LOAD + VALIDATE QUESTIONS EARLY (fail-fast before expensive embedding)
        try:
            with open(local_q_path, "r", encoding="utf-8") as f:
                q_data = json.load(f)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail='Invalid questions JSON. Provide a JSON array or {"questions": [...]} object.',
            )

        questions = q_data if isinstance(q_data, list) else q_data.get("questions", [])
        if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
            raise HTTPException(status_code=400, detail="Questions must be a list of strings.")

        questions = [q.strip() for q in questions if q.strip()]
        if not questions:
            raise HTTPException(status_code=400, detail="No questions provided.")
        if len(questions) > MAX_QUESTIONS:
            raise HTTPException(status_code=400, detail=f"Too many questions. Limit is {MAX_QUESTIONS}.")

        # 4) PROCESS DOCUMENT (thread offload)
        raw_documents = await loop.run_in_executor(executor, process_file_sync, local_doc_path, doc_ext)

        # Normalize citation source to original uploaded filename (avoid temp paths)
        original_name = document_file.filename or "document"
        for d in raw_documents:
            try:
                d.metadata["source"] = original_name
            except Exception:
                pass

        # 5) BUILD RAG PIPELINE (thread offload)
        rag_pipeline = await loop.run_in_executor(executor, build_rag_pipeline, raw_documents)

        # 6) ANSWER QUESTIONS + RETURN CITATIONS (clean + capped)
        results = {}
        for q in questions:
            try:
                response = await loop.run_in_executor(executor, resilient_llm_call, rag_pipeline, q)
                answer = (response.get("result", "") or "").strip()

                # Optional second pass: if explicitly not found, increase recall and retry once
                if answer == "Not found in the provided document.":
                    try:
                        # Works if your rag_pipeline exposes retriever.search_kwargs (LangChain RetrievalQA does)
                        rag_pipeline.retriever.search_kwargs["k"] = max(
                            rag_pipeline.retriever.search_kwargs.get("k", 8), 16
                        )
                        # Only meaningful if your retriever uses fetch_k; safe to set regardless
                        rag_pipeline.retriever.search_kwargs["fetch_k"] = max(
                            rag_pipeline.retriever.search_kwargs.get("fetch_k", 40), 80
                        )

                        response2 = await loop.run_in_executor(executor, resilient_llm_call, rag_pipeline, q)
                        answer2 = (response2.get("result", "") or "").strip()
                        if answer2 and answer2 != "Not found in the provided document.":
                            response = response2
                            answer = answer2
                    except Exception:
                        pass

                # Clean citations:
                #  - If the model mentioned pages in Evidence, keep only those pages
                #  - Dedupe (source, page)
                #  - Cap to 4 citations
                pages_used = _pages_mentioned(answer)

                seen = set()
                citations = []
                for d in response.get("source_documents", []) or []:
                    md = d.metadata or {}
                    src = md.get("source")
                    page = _coerce_int(md.get("page"))

                    if pages_used and page is not None and page not in pages_used:
                        continue

                    key = (src, page)
                    if key in seen:
                        continue
                    seen.add(key)

                    citations.append({"source": src, "page": page})
                    if len(citations) == 4:
                        break

                # Fallback: if Evidence didn't include page numbers or filtering removed everything,
                # take top 4 unique retrieved chunks.
                if not citations:
                    seen = set()
                    for d in response.get("source_documents", []) or []:
                        md = d.metadata or {}
                        src = md.get("source")
                        page = _coerce_int(md.get("page"))
                        key = (src, page)
                        if key in seen:
                            continue
                        seen.add(key)
                        citations.append({"source": src, "page": page})
                        if len(citations) == 4:
                            break

                results[q] = {
                    "answer": answer if answer else "Not found in the provided document.",
                    "citations": citations,
                }

            except Exception as e:
                logger.error(f"LLM Error on question '{q}': {e}")
                results[q] = {"answer": "Error: Service unavailable for this query.", "citations": []}

        duration = time.time() - start_time
        logger.info(json.dumps({
            "event": "processed_request",
            "duration_sec": duration,
            "question_count": len(questions),
        }))

        return results
