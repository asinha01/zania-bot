import json
from typing import List

from fastapi import HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_community.callbacks.manager import get_openai_callback

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document

from utils import logger


def process_file_sync(file_path: str, file_ext: str) -> List[Document]:
    """Reads the file. This is blocking I/O, so it should run in a thread."""
    try:
        if file_ext == ".pdf":
            loader = PyPDFLoader(file_path)
            return loader.load()

        if file_ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            text_dump = json.dumps(raw_data, indent=2)
            return [Document(page_content=text_dump, metadata={"source": file_path})]

        raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF or JSON.")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Corrupt JSON document.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ingest file: {str(e)}")
        raise HTTPException(status_code=400, detail="Corrupt or unreadable file.")


# ---- Retry only for transient-ish upstream errors ----
_TRANSIENT_EXC = (TimeoutError, ConnectionError)
try:
    from openai import RateLimitError, APIConnectionError, APITimeoutError, InternalServerError
    _TRANSIENT_EXC = _TRANSIENT_EXC + (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
except Exception:
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_TRANSIENT_EXC),
    reraise=True
)
def resilient_llm_call(chain, question: str):
    """
    Call LLM with automatic retry on transient errors and token usage tracking.
    Returns the chain result dict with an added 'token_usage' key.
    """
    with get_openai_callback() as cb:
        result = chain.invoke(question)
        
        # Log per-question token usage
        logger.info(json.dumps({
            "event": "llm_call",
            "question_preview": question[:100],
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_tokens": cb.total_tokens,
            "total_cost_usd": round(cb.total_cost, 6),
        }))
        
        # Attach usage info to result for caller (main.py can aggregate)
        if isinstance(result, dict):
            result["token_usage"] = {
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
                "total_tokens": cb.total_tokens,
                "cost_usd": round(cb.total_cost, 6)
            }
        
        return result


def build_rag_pipeline(raw_documents: List[Document]):
    """
    Builds the vector store + QA chain.
    Improvements:
      - token-aware splitting (more stable chunks)
      - MMR retrieval for diversity
      - include source/page labels inside context
      - prompt returns Not found / partial + Evidence
      - logs embedding costs
    """
    # 1) Split text (token-aware is generally better than raw characters)
    text_processor = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunked_docs = text_processor.split_documents(raw_documents)

    # 2) Embeddings with cost tracking
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")
    
    with get_openai_callback() as cb:
        knowledge_base = FAISS.from_documents(chunked_docs, embeddings_model)
        
        logger.info(json.dumps({
            "event": "embedding_creation",
            "num_chunks": len(chunked_docs),
            "total_tokens": cb.total_tokens,
            "total_cost_usd": round(cb.total_cost, 6),
        }))

    # 3) Retriever with MMR for diversity
    retriever = knowledge_base.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 10,
            "fetch_k": 25,
            "lambda_mult": 0.7
        }
    )

    # 4) Document formatting: inject page/source into the "context" text
    DOCUMENT_PROMPT = PromptTemplate(
        input_variables=["page_content", "source", "page"],
        template="(source={source}, page={page})\n{page_content}"
    )

    # 5) QA prompt: prefer "Not found" + partial answers + evidence snippets
    QA_PROMPT = PromptTemplate(
        input_variables=["context", "question"],
        template="""
You are a compliance assistant. Answer ONLY using the provided context.

Rules:
- If the answer is explicitly stated in the context, answer it.
- If the context contains partial information, answer what is known and list missing items under "Missing:".
- If the answer is NOT in the context, respond exactly: "Not found in the provided document."
- Always include an "Evidence:" section with up to 2 short excerpts (max 25 words each) copied from the context,
  and include the page number shown in the context labels.

Context:
{context}

Question:
{question}

Answer:
""".strip()
    )

    # 6) Chain with sources
    rag_pipeline = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(
            temperature=0,
            model_name="gpt-4o-mini",
            request_timeout=30,
        ),
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={
            "prompt": QA_PROMPT,
            "document_prompt": DOCUMENT_PROMPT,
        },
        return_source_documents=True,
    )
    return rag_pipeline