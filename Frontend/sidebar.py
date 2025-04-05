# sidebar.py

import streamlit as st
import requests
import os
from api_client import APIClient  # Import your api_client for document interactions
APIClient = APIClient()
# Initialize session state for uploaded files and clear flag
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = None
if "clear_files" not in st.session_state:
    st.session_state.clear_files = False

# Function to reset the uploaded files
def reset_uploaded_files():
    st.session_state.clear_files = True
    st.rerun()

def handle_error(e):
    """Handles any error and displays a message."""
    st.error(f"An error occurred: {e}")

def get_index_name_from_document( document_name):

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
    st.sidebar.subheader("Select Document For Chat")
        # Document selection
    try:
        documents = APIClient.get_all_documents()
        if documents:
            # Handle both string and dictionary document formats
            document_names = [doc if isinstance(doc, str) else doc.get('document_name', 'Unknown') for doc in documents]
            
            # Document selection section with better styling
            st.sidebar.markdown('<div class="document-select-container" style="margin-top:-5px; padding-top:0; padding-bottom:0;">', unsafe_allow_html=True)
            selected_doc = st.sidebar.selectbox(
                "Select a document to chat with",
                document_names,
                key="chat_document",
                format_func=lambda x: x.replace('_', ' ').title() if isinstance(x, str) else x,
                label_visibility="collapsed"
            )
            st.session_state.selected_document = selected_doc
            st.sidebar.markdown('</div>', unsafe_allow_html=True)

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
        if cleaned_name not in documents:
            final_uploaded_files.append(file)
        
    uploaded_files=final_uploaded_files
    
    if uploaded_files:
        
        if st.sidebar.button("Upload Documents", key="process_docs"):
            
            try:
                with st.spinner("Uploading documents..."):
                    ## send both uploaded files and documents to the api
                    result = APIClient.upload_documents(uploaded_files)
                    st.rerun()
                    # Mark the uploaded files as recent
                    for file in uploaded_files:
                     
                        st.session_state.recent_uploads.add(file.name)
                    
                    st.sidebar.markdown('<div class="upload-success">Documents processed successfully!</div>', unsafe_allow_html=True)
          

                    
            except Exception as e:
                handle_error(e)
    
    # Display uploaded documents
    try:
        documents = APIClient.get_all_documents()
        
        if documents:
            st.sidebar.subheader("Uploaded Documents")
            
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
                        if st.session_state.get(f"confirm_{unique_key}", False):
                           
                            try:
                                api_base_url = "http://localhost:8000"  # Change this to your API URL
                                url = f"{api_base_url}/delete-embeddings"
                                form_data = {"document_name": doc_name}
                                response = requests.delete(url, data=form_data)
                                
                                if response.status_code == 200:
                                    if doc_name in st.session_state.recent_uploads:
                                        st.session_state.recent_uploads.remove(doc_name)
                                    st.sidebar.markdown('<div class="upload-success">Document deleted successfully!</div>', unsafe_allow_html=True)
                                    st.session_state.selected_document = None
                                    st.rerun()
                                else:
                                    st.sidebar.error(f"Failed to delete document. Status code: {response.status_code}")
                            except Exception as e:
                                handle_error(e)
                        else:
                            st.session_state[f"confirm_{unique_key}"] = True
                            st.sidebar.markdown(f'<div style="background-color: rgba(255, 59, 48, 0.2); padding: 10px; border-radius: 6px; color: #ff6b6b; border-left: 3px solid #ff3b30;">Click again to confirm deletion of \'{display_name}\'</div>', unsafe_allow_html=True)
    except Exception as e:
        handle_error(e)


