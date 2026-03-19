# sidebar.py

import streamlit as st
import requests
import os
from api_client import APIClient
api_client = APIClient()

CATEGORIES = [
    "LLMs",
    "Prompt Engineering",
    "RAG",
    "AI API Integration",
    "AI Agents",
]
# Initialize session state for uploaded files and clear flag
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = None
if "clear_files" not in st.session_state:
    st.session_state.clear_files = False
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None

@st.cache_data(ttl=5, show_spinner=False)
def _cached_get_all_documents():
    return api_client.get_all_documents()

def _safe_documents_list(documents_raw):
    """
    Backend normally returns a list of class names.
    If it returns an error object (dict), convert to empty list and show message.
    """
    if isinstance(documents_raw, list):
        return documents_raw
    if isinstance(documents_raw, dict):
        # Treat as empty without breaking UI.
        err = documents_raw.get("error") or documents_raw.get("detail")
        if err:
            st.sidebar.warning("Documents unavailable (backend not ready yet).")
        return []
    return []

# Function to reset the uploaded files
def reset_uploaded_files():
    st.session_state.clear_files = True
    st.rerun()

def handle_error(e):
    """Handles any error and displays a message."""
    st.error(f"An error occurred: {e}")

def get_index_name_from_document(document_name):

    """Generate a valid Weaviate class name from user_id and document name."""
    # Remove file extension if present
    base_name = os.path.splitext(document_name)[0]
    # Create combined name
    combined = f"{base_name}"
    # Clean the name (only letters, numbers, and underscores allowed)
    cleaned = ''.join(c if c.isalnum() else '_' for c in combined).lower()
    return cleaned 


def create_sidebar():
    # Add logo and branding
    st.sidebar.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <div style="background-color: #1976d2; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
            <span style="color: white; font-size: 22px; font-weight: bold;">🏢</span>
        </div>
        <h1 style="margin: 0; padding: 0; font-size: 24px;">Leasing AI</h1>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")

    st.sidebar.subheader("1) Choose a Category")
    current_category = st.session_state.get("selected_category")
    category = st.sidebar.selectbox(
        "Category",
        options=["Select..."] + CATEGORIES,
        index=0 if not current_category else (CATEGORIES.index(current_category) + 1),
        label_visibility="collapsed",
        key="category_selectbox",
    )
    if category == "Select...":
        st.session_state.selected_category = None
        st.sidebar.info("Pick a category to continue.")
        st.sidebar.markdown("---")
        return

    st.session_state.selected_category = category
    st.sidebar.caption(f"Selected: {category}")

    # Chat scope is category-wide now (no per-document selection)
    st.session_state.selected_document = None

    # Always define documents so upload logic is safe
    documents = []
    try:
        documents = _safe_documents_list(_cached_get_all_documents())
        cat_prefix = f"{st.session_state.selected_category.lower().replace(' ', '_')}__"
        category_docs = [d for d in documents if isinstance(d, str) and d.lower().startswith(cat_prefix)]
        st.sidebar.caption(f"Docs in this category: {len(category_docs)}")
        if not category_docs:
            st.sidebar.info("No documents in this category yet. Upload a document below.")
    except Exception as e:
        handle_error(e)
    # Document Management Section
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Document Management")
    
    # File uploader
# File uploader widget with conditional reset
    uploaded_files = st.sidebar.file_uploader(
        "Upload Documents",
        type=["pdf", "txt", "doc", "docx"],
        accept_multiple_files=True,
    )
    final_uploaded_files=[]
    for file in uploaded_files:
        cleaned_name=get_index_name_from_document(file.name)
        # If the document already exists in this category, skip it.
        cat_prefix = f"{st.session_state.selected_category.lower().replace(' ', '_')}__"
        existing_in_category = set(
            d.split("__", 1)[1]
            for d in (documents or [])
            if isinstance(d, str) and d.lower().startswith(cat_prefix) and "__" in d
        )
        if cleaned_name not in existing_in_category:
            final_uploaded_files.append(file)
        
    uploaded_files=final_uploaded_files
  
    if uploaded_files:
        
        if st.sidebar.button("Upload Documents", key="process_docs", disabled=not bool(st.session_state.selected_category)):
            
            try:
                with st.spinner("Uploading documents..."):
                    ## send both uploaded files and documents to the api
                   
                    result = api_client.upload_documents(uploaded_files, category=st.session_state.selected_category)
                    _cached_get_all_documents.clear()
                    st.rerun()
                    # Mark the uploaded files as recent
                    for file in uploaded_files:
                     
                        st.session_state.recent_uploads.add(file.name)
                    
                    st.sidebar.markdown('<div class="upload-success">Documents processed successfully!</div>', unsafe_allow_html=True)
          
                    
            except Exception as e:
                handle_error(e)
    
    # Display uploaded documents
    try:
        documents = _safe_documents_list(_cached_get_all_documents())
        documents.sort()
        
        if documents:
            st.sidebar.subheader("Uploaded Documents")
            
            # Only show docs for current category
            cat_prefix = f"{st.session_state.selected_category.lower().replace(' ', '_')}__"
            documents = [d for d in documents if isinstance(d, str) and d.lower().startswith(cat_prefix)]

            for i, doc in enumerate(documents):
                doc_name = doc if isinstance(doc, str) else doc.get('document_name', 'Unknown')
                display_name = doc_name.replace('_', ' ').title()
                
                col1, col2 = st.sidebar.columns([4, 1])
                with col1:
                    # Show document name with recent indicator if applicable
                    is_recent = doc_name in st.session_state.recent_uploads
                    recent_tag = f'<span class="recent-upload">NEW</span>' if is_recent else ''
                    st.sidebar.markdown(f'<div class="document-name" title="{doc_name}">{display_name} {recent_tag}</div>', unsafe_allow_html=True)
                
                with col2:
                    unique_key = f"delete_{i}_{hash(doc_name)}"
                    if st.sidebar.button("🗑️", key=unique_key, help=f"Delete {doc_name}"):
                        try:
                            api_base_url = "http://localhost:8000"  # Change this to your API URL
                            url = f"{api_base_url}/delete-embeddings"
                            form_data = {"document_name": doc_name}
                            response = requests.delete(url, data=form_data)
                            
                            if response.status_code == 200:
                                _cached_get_all_documents.clear()
                                if doc_name in st.session_state.recent_uploads:
                                    st.session_state.recent_uploads.remove(doc_name)
                                st.sidebar.markdown('<div class="upload-success">Document deleted successfully!</div>', unsafe_allow_html=True)
                                st.session_state.selected_document = None
                                st.rerun()
                            else:
                                st.sidebar.error(f"Failed to delete document. Status code: {response.status_code}")
                        except Exception as e:
                            handle_error(e)
    except Exception as e:
        handle_error(e)


