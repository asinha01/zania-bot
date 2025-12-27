# frontend.py (updated to display answers + citations, and support Docker via ZANIA_API_URL)

import os
import streamlit as st
import requests

st.set_page_config(page_title="Zania Bot", layout="wide")

st.title("Zania QA bot")
st.markdown("Upload a document and a list of questions to get grounded answers.")

# Use env override for Docker; default for local dev.
API_URL = os.getenv("ZANIA_API_URL", "http://localhost:8000/answer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Uploads")
    doc_file = st.file_uploader("1. Upload Document (PDF or JSON)", type=["pdf", "json"])
    q_file = st.file_uploader("2. Upload Questions (JSON)", type=["json"])
    st.info("Note: Max document file size is 50MB. Questions file is smaller.")

def _render_citations(citations):
    """Render citations list in a compact, readable way."""
    if not citations:
        st.caption("No citations returned.")
        return

    for i, c in enumerate(citations, start=1):
        src = c.get("source") or "unknown"
        page = c.get("page")
        if page is None:
            st.caption(f"[{i}] {src}")
        else:
            st.caption(f"[{i}] {src} (page {page})")

if st.button("Generate Answers", type="primary"):
    if not (doc_file and q_file):
        st.warning("Please upload both a document and a questions file.")
        st.stop()

    with st.spinner("Processing document and generating answers..."):
        try:
            files = {
                "document_file": (doc_file.name, doc_file.getvalue(), doc_file.type),
                "questions_file": (q_file.name, q_file.getvalue(), q_file.type),
            }

            response = requests.post(API_URL, files=files, timeout=120)

            if response.status_code != 200:
                st.error(f"Error {response.status_code}: {response.text}")
                st.stop()

            st.success("Analysis Complete!")
            results = response.json()

            # Results: {question: {"answer": str, "citations": [...]}}
            for question, payload in results.items():
                if isinstance(payload, dict):
                    answer_text = payload.get("answer", "")
                    citations = payload.get("citations", []) or []
                else:
                    # Backward compatibility if backend returns a string
                    answer_text = str(payload)
                    citations = []

                with st.expander(f"❓ {question}", expanded=True):
                    st.markdown(answer_text if answer_text else "_No answer returned._")
                    st.divider()
                    st.subheader("Citations")
                    _render_citations(citations)

        except requests.exceptions.Timeout:
            st.error("Request timed out. Is the backend under load or not running?")
        except requests.exceptions.ConnectionError:
            st.error(f"Connection error. Is the backend running and reachable at {API_URL}?")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
