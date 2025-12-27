import json
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from fastapi import HTTPException

# Import logger from our utils file
from utils import logger

def process_file_sync(file_path: str, file_ext: str) -> List[Document]:
    """Reads the file. This is Blocking I/O, so it runs in a thread."""
    try:
        if file_ext == ".pdf":
            loader = PyPDFLoader(file_path)
            return loader.load()
        elif file_ext == ".json":
            with open(file_path, 'r') as f:
                raw_data = json.load(f)
            # Convert JSON to string so the LLM can read it
            text_dump = json.dumps(raw_data, indent=2)
            return [Document(page_content=text_dump, metadata={"source": file_path})]
        else:
            return []
    except Exception as e:
        logger.error(f"Failed to ingest file: {str(e)}")
        raise HTTPException(status_code=400, detail="Corrupt or unreadable file.")

# --- ROBUSTNESS: RETRY LOGIC ---
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def resilient_llm_call(chain, question):
    """Retries the LLM call if OpenAI errors out."""
    return chain.invoke(question)

def build_rag_pipeline(raw_documents):
    """Builds the Vector Store and QA Chain."""
    # 1. Split Text
    text_processor = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunked_docs = text_processor.split_documents(raw_documents)

    # 2. Embed & Index (Heavy CPU)
    embeddings_model = OpenAIEmbeddings()
    knowledge_base = FAISS.from_documents(chunked_docs, embeddings_model)

    # 3. Define the Prompt (Grounding)
    custom_prompt = """
        You are a helpful and precise assistant for Zania. 
        Use the following pieces of context to answer the question at the end. 
        If you don't know the answer, just say that you don't know, don't try to make up an answer.

        Context: {context}

        Question: {question}
        Helpful Answer:"""
        
    PROMPT = PromptTemplate(
            template=custom_prompt_template, input_variables=["context", "question"]
        )
    # 4. Create Chain
    rag_pipeline = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(temperature=0, model_name="gpt-4o-mini", request_timeout=30),
        chain_type="stuff",
        retriever=knowledge_base.as_retriever(),
        chain_type_kwargs={"prompt": PROMPT}
    )
    return rag_pipeline