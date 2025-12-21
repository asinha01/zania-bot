import os
import json
import shutil
import tempfile
from typing import List, Dict

from fastapi import FastAPI, UploadFile, File, HTTPException
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate  # <--- NEW: Added this to customize the AI
from langchain.docstore.document import Document

# Initialize the API
app = FastAPI(title="Zania Q&A Bot", description="An intelligent assistant for document analysis.")

# --- HELPER FUNCTIONS ---

def ingest_file(file_path: str, file_ext: str) -> List[Document]:
    """
    Reads a file and converts it into LangChain Document objects.
    """
    if file_ext == ".pdf":
        loader = PyPDFLoader(file_path)
        return loader.load()
    
    elif file_ext == ".json":
        # Parse JSON and convert to string for the LLM to read
        with open(file_path, 'r') as f:
            raw_data = json.load(f)
        text_dump = json.dumps(raw_data, indent=2)
        return [Document(page_content=text_dump, metadata={"source": file_path})]
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please use PDF or JSON.")

# --- API ROUTES ---

@app.get("/")
def health_check():
    """Simple route to check if the server is running."""
    return {"status": "active", "message": "Zania Bot is ready to answer questions."}

@app.post("/answer")
async def generate_answers(
    questions_file: UploadFile = File(...),
    document_file: UploadFile = File(...)
):
    # Use a temporary directory to handle file cleanup automatically
    with tempfile.TemporaryDirectory() as temp_work_dir:
        
        # 1. SAVE UPLOADS
        # We need to save the uploaded bytes to a real file on disk for the loaders to work
        doc_ext = os.path.splitext(document_file.filename)[1].lower()
        local_doc_path = os.path.join(temp_work_dir, f"source_doc{doc_ext}")
        
        with open(local_doc_path, "wb") as buffer:
            shutil.copyfileobj(document_file.file, buffer)
            
        questions_path = os.path.join(temp_work_dir, "questions_input.json")
        with open(questions_path, "wb") as buffer:
            shutil.copyfileobj(questions_file.file, buffer)

        # 2. PROCESS DOCUMENT
        raw_documents = ingest_file(local_doc_path, doc_ext)
        
        # Split text into chunks (1000 chars) so it fits in the AI's context window
        text_processor = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunked_docs = text_processor.split_documents(raw_documents)

        # 3. BUILD KNOWLEDGE BASE (Vector Store)
        # Create embeddings and store them in FAISS (Facebook AI Similarity Search)
        embeddings_model = OpenAIEmbeddings()
        knowledge_base = FAISS.from_documents(chunked_docs, embeddings_model)
        
        # 4. CONFIGURE THE AI
        # We define a custom prompt to make the answers more professional
        custom_prompt_template = """
        You are a helpful and precise assistant for Zania. 
        Use the following pieces of context to answer the question at the end. 
        If you don't know the answer, just say that you don't know, don't try to make up an answer.

        Context: {context}

        Question: {question}
        Helpful Answer:"""
        
        PROMPT = PromptTemplate(
            template=custom_prompt_template, input_variables=["context", "question"]
        )

        llm_engine = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
        
        rag_pipeline = RetrievalQA.from_chain_type(
            llm=llm_engine,
            chain_type="stuff",
            retriever=knowledge_base.as_retriever(),
            chain_type_kwargs={"prompt": PROMPT}  # <--- Injecting our custom personality here
        )

        # 5. EXECUTE QUESTIONS
        # Load the questions JSON
        with open(questions_path, 'r') as f:
            q_data = json.load(f)
            
        # Robustly handle different JSON formats (list vs dict)
        question_list = q_data if isinstance(q_data, list) else q_data.get("questions", [])
        
        final_results = {}
        
        for q in question_list:
            # The 'invoke' method runs the retrieval and generation steps
            ai_response = rag_pipeline.invoke(q)
            final_results[q] = ai_response['result']

        return final_results