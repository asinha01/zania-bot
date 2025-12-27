import streamlit as st
import requests
import json

st.set_page_config(page_title="Zania Bot", layout="wide")

st.title("🤖 Zania Compliance Assistant")
st.markdown("Upload a document and a list of questions to get grounded answers.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Uploads")
    # File Uploader
    doc_file = st.file_uploader("1. Upload Document (PDF or JSON)", type=["pdf", "json"])
    # Questions Uploader
    q_file = st.file_uploader("2. Upload Questions (JSON)", type=["json"])
    
    st.info("Note: Max file size is 50MB.")

# --- MAIN AREA ---
if st.button("Generate Answers", type="primary"):
    if doc_file and q_file:
        with st.spinner("Processing document and generating answers..."):
            try:
                # Prepare files for the API
                files = {
                    "document_file": (doc_file.name, doc_file.getvalue(), doc_file.type),
                    "questions_file": (q_file.name, q_file.getvalue(), q_file.type)
                }
                
                # Call the Backend API (Assumes it's running on port 8000)
                response = requests.post("http://localhost:8000/answer", files=files)
                
                if response.status_code == 200:
                    st.success("Analysis Complete!")
                    results = response.json()
                    
                    # Display results nicely
                    for question, answer in results.items():
                        with st.expander(f"❓ {question}", expanded=True):
                            st.write(answer)
                else:
                    st.error(f"Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                st.error(f"Connection Error: Is the backend running? \nDetail: {e}")
    else:
        st.warning("Please upload both a document and a questions file.")