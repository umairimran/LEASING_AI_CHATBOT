import streamlit as st
import os
import datetime
import json
import requests
from api_client import APIClient
from utils import (
    initialize_session_state,
    display_chat_history,
    add_to_chat_history,
    display_search_results,
    show_loading_spinner,
    handle_error
)

# Page configuration
st.set_page_config(
    page_title="E-commerce Chatbot",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    /* Global styling */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
        background-color: #121212;
    }
    
    h1, h2, h3 {
        font-weight: 600;
        color: #ffffff;
        letter-spacing: -0.5px;
    }
    
    p {
        color: #e0e0e0;
    }
    
    /* Container styling */
    .chat-container {
        height: calc(100vh - 250px);
        overflow-y: auto;
        padding: 20px;
        border: 1px solid #333;
        border-radius: 12px 12px 0 0;
        margin-bottom: 0;
        margin-top: 10px;
        background-color: #1e1e1e;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        display: flex;
        flex-direction: column;
    }
    
    /* Document management styling */
    .delete-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: #ff4b4b;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.25rem 0.75rem;
        font-size: 0.8rem;
        line-height: 1;
        cursor: pointer;
        text-decoration: none;
        width: 100%;
    }
    
    .stButton button {
        width: 100%;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    
    /* Main content area styling */
    [data-testid="stAppViewContainer"] > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) {
        background-color: #121212;
    }
    
    /* Sidebar enhancements */
    [data-testid="stSidebar"] {
        background-color: #121212;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: white;
    }
    
    [data-testid="stSidebar"] p {
        color: #e0e0e0;
    }
    
    /* Add styling for the sidebar separator line */
    [data-testid="stSidebar"] hr {
        border-color: #333;
        margin: 15px 0;
    }
    
    /* Add black background color to the whitespace at the bottom of sidebar */
    [data-testid="stSidebar"] > div:first-of-type {
        background-color: #121212;
    }
    
    [data-testid="stSidebar"] > div {
        background-color: #121212;
    }
    
    /* Custom chat input styling */
    div[data-testid="stForm"] {
        background: #121212;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border: 1px solid #333;
        position: sticky;
        bottom: 0;
        z-index: 100;
    }
    
    /* Form label styling - white text */
    div[data-testid="stForm"] label {
        color: white !important;
        font-weight: 500;
        letter-spacing: 0.3px;
    }
    
    /* Input field styling */
    div[data-testid="stForm"] [data-testid="stTextInput"] input {
        background-color: #2c2c2c;
        border: 1px solid #444;
        border-radius: 8px;
        color: #ffffff;
        font-size: 16px;
        padding: 14px 18px;
        transition: all 0.2s ease;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);
        width: 100%;
    }
    
    div[data-testid="stForm"] [data-testid="stTextInput"] input:focus {
        border-color: #4e8cff;
        box-shadow: 0 0 0 3px rgba(78,140,255,0.2);
    }
    
    div[data-testid="stForm"] [data-testid="stTextInput"] input::placeholder {
        color: #888;
    }
    
    /* Send button styling - adjusted to align with the query input box */
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        height: 48px;
        margin-top: 10px; /* Removed top margin to align with query box */
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        letter-spacing: 0.5px;
        width: 100%;
    }
    
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(145deg, #1976d2, #0d47a1);
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }
    
    /* Message containers */
    .message-container {
        margin: 24px 0;
        display: flex;
        flex-direction: column;
        gap: 16px;
    }
    
    .message-user {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        color: white;
        padding: 14px 18px;
        border-radius: 18px 18px 4px 18px;
        align-self: flex-end;
        max-width: 80%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        word-wrap: break-word;
    }
    
    .message-assistant {
        background-color: #2c2c2c;
        color: #ffffff;
        padding: 14px 18px;
        border-radius: 18px 18px 18px 4px;
        align-self: flex-start;
        max-width: 80%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        word-wrap: break-word;
        line-height: 1.5;
    }
    
    .timestamp {
        text-align: right;
        font-size: 0.7rem;
        color: rgba(255,255,255,0.7);
        margin-top: 6px;
    }
    
    .message-assistant .timestamp {
        color: #888;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #2c2c2c;
        padding: 5px;
        border-radius: 12px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 8px;
        gap: 6px;
        padding: 10px 20px;
        margin-right: 5px;
        font-weight: 500;
        background-color: #2c2c2c;
        color: #e0e0e0;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(33, 150, 243, 0.1);
    }
    
    .stTabs [data-baseweb="tab-highlight"] {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        border-radius: 8px;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: white;
        background: linear-gradient(145deg, #2196F3, #1976d2);
    }
    
    /* Selectbox styling */
    div[data-testid="stSelectbox"] {
        margin-bottom: 16px;
        color: white;
    }
    
    div[data-testid="stSelectbox"] > div:first-child {
        border-radius: 8px;
        background-color: #2c2c2c;
    }
    
    /* Text and labels */
    [data-testid="stMarkdown"] p {
        color: #e0e0e0;
    }
    
    /* Search styling */
    [data-testid="stWidgetLabel"] {
        font-weight: 500;
        color: #ffffff;
        margin-bottom: 5px;
    }
 
    [data-testid="baseButton-secondary"] {
        background-color: #2c2c2c;
        color: #ffffff;
        border-radius: 6px;
        border: 1px solid #444;
        font-weight: 500;
        padding: 10px 16px;
        transition: all 0.2s ease;
    }
    
    [data-testid="baseButton-secondary"]:hover {
        background-color: #383838;
        border-color: #555;
    }
    
    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: #1e1e1e;
        border-radius: 12px;
        padding: 16px;
        border: 1px dashed #444;
        margin-bottom: 16px;
    }
    
    [data-testid="stFileUploader"] p {
        color: #e0e0e0;
    }
    
    /* Info box */
    [data-testid="stAlert"] {
        background-color: rgba(33, 150, 243, 0.1);
        border-color: #2196F3;
        border-radius: 8px;
        color: #e0e0e0;
    }
    
    /* Hide bottom whitespace and default Streamlit padding */
    .css-18e3th9 {
        padding-top: 0;
        padding-bottom: 0;
    }
    
    .css-1d391kg {
        padding-top: 3.5rem;
    }
    
    /* Sticky chat input at bottom */
    .chat-input-area {
        position: sticky;
        bottom: 0;
        background-color: #121212;
        padding: 10px 0;
        margin-top: auto;
        z-index: 100;
        border-top: 1px solid #333;
    }
    
    /* Other containers */
    .chat-messages {
        display: flex;
        flex-direction: column;
        gap: 16px;
        margin-bottom: 0;
        padding: 15px;
        flex-grow: 1;
        overflow-y: auto;
        min-height: calc(100vh - 300px);
        background-color: #121212;
    }
    
    /* Selection text color */
    ::selection {
        background-color: #2196F3;
        color: white;
    }
    
    /* Additional sidebar selectors to ensure all parts are black */
    .st-emotion-cache-16txtl3 {
        background-color: #121212 !important;
    }
    
    .st-emotion-cache-z5fcl4 {
        background-color: #121212 !important;
    }
    
    /* Make document upload area darker */
    [data-testid="stSidebar"] .block-container {
        background-color: #121212;
    }
    
    /* Target more sidebar elements to ensure full black coverage */
    .st-emotion-cache-r421ms {
        background-color: #121212 !important;
    }
    
    .st-emotion-cache-vk3wp9 {
        background-color: #121212 !important;
    }
    
    [data-testid="stSidebarNav"] {
        background-color: #121212 !important;
    }
    
    /* Ensure scrollbars in sidebar match the dark theme */
    [data-testid="stSidebar"]::-webkit-scrollbar {
        background-color: #121212;
        width: 8px;
    }
    
    [data-testid="stSidebar"]::-webkit-scrollbar-thumb {
        background-color: #333;
        border-radius: 4px;
    }
    
    /* Custom styling for the button in sidebar */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #1e1e1e;
        color: white;
        border: 1px solid #333;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #333;
        border-color: #444;
    }
    
    /* Navigation button styling */
    .nav-button {
        margin-bottom: 15px;
        text-align: center;
    }
    
    button[data-testid="baseButton-secondary"].nav-button {
        width: 120px;
        background: linear-gradient(145deg, #2c2c2c, #1e1e1e);
        color: #e0e0e0;
        font-weight: 600;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
        transition: all 0.2s ease;
    }
    
    button[data-testid="baseButton-secondary"].nav-button:hover {
        background: linear-gradient(145deg, #333, #222);
        transform: translateY(-1px);
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize API client and session state
api_client = APIClient()
initialize_session_state()

# Convert legacy chat history format to new format if needed
def convert_chat_history_format():
    """Convert any string-based chat history entries to the new dictionary format."""
    if 'chat_history' in st.session_state:
        for doc_name, messages in st.session_state.chat_history.items():
            for i, message in enumerate(messages):
                if isinstance(message, str):
                    # Determine if it's a user message (basic heuristic)
                    is_user = 'You</div>' in message
                    # Extract message text (simplified approach)
                    try:
                        text_start = message.find('<div style="line-height: 1.5;">') + len('<div style="line-height: 1.5;">')
                        if text_start < 0:
                            text_start = message.find('<div>') + len('<div>')
                        text_end = message.find('</div>', text_start)
                        
                        if text_start >= 0 and text_end >= 0:
                            msg_text = message[text_start:text_end].strip()
                            # Replace with new format
                            messages[i] = {
                                "message": msg_text,
                                "is_user": is_user,
                                "timestamp": datetime.datetime.now().strftime('%H:%M:%S')
                            }
                    except:
                        # Keep original if conversion fails
                        continue

# Run the conversion
convert_chat_history_format()

# Sidebar
with st.sidebar:
    st.title("🛍️ E-commerce Chatbot")
    st.markdown("---")
    
    # Document Management Section
    st.subheader("Document Management")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["pdf", "txt", "doc", "docx"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("Process Documents", key="process_docs"):
            try:
                with st.spinner("Processing documents..."):
                    result = api_client.upload_documents(uploaded_files)
                    st.success("Documents processed successfully!")
            except Exception as e:
                handle_error(e)
    
    # Display uploaded documents
    try:
        documents = api_client.get_all_documents()
        if documents:
            st.subheader("Uploaded Documents")
            
            # Remove the dedicated delete section with the expander
            # Just keep the inline deletion with unique keys
            for i, doc in enumerate(documents):
                # Handle both string and dictionary document formats
                doc_name = doc if isinstance(doc, str) else doc.get('document_name', 'Unknown')
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(doc_name)
                with col2:
                    # Create a unique key using the index
                    unique_key = f"delete_{i}_{hash(doc_name)}"
                    if st.button("🗑️", key=unique_key, help=f"Delete {doc_name}"):
                        # Add confirmation before deletion
                        if st.session_state.get(f"confirm_{unique_key}", False):
                            try:
                                # Direct API call that we know works
                                api_base_url = "http://localhost:8000"  # Change this to your API URL
                                url = f"{api_base_url}/delete-embeddings"
                                form_data = {"document_name": doc_name}
                                response = requests.delete(url, data=form_data)
                                
                                if response.status_code == 200:
                                    st.success(f"Document '{doc_name}' deleted successfully!")
                                    st.experimental_rerun()
                                else:
                                    st.error(f"Failed to delete document. Status code: {response.status_code}")
                            except Exception as e:
                                handle_error(e)
                        else:
                            # Set confirmation state and show confirmation message
                            st.session_state[f"confirm_{unique_key}"] = True
                            st.warning(f"Click again to confirm deletion of '{doc_name}'")
    except Exception as e:
        handle_error(e)

# Main content
st.title("E-commerce Chatbot", anchor=False)

# Create container for page navigation
nav_container = st.container()
with nav_container:
    cols = st.columns([1, 1, 4])
    
    # Add page indicators with consistent sizing
    with cols[0]:
        # Chat button - highlight if on chat page
        button_style = "solid" if not st.session_state.get("show_search_page", False) else "outline"
        st.markdown(f"""
        <style>
        div[data-testid="element-container"]:has(button:contains("Chat")) button {{
            width: 120px !important;
            height: 40px !important;
            background: {("linear-gradient(145deg, #2c2c2c, #1e1e1e)" if button_style == "outline" else "linear-gradient(145deg, #2196F3, #1976d2)")} !important;
            color: #e0e0e0 !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            border: 1px solid {("#333" if button_style == "outline" else "#1976d2")} !important;
            border-radius: 8px !important;
            padding: 8px 0px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button("Chat", key="goto_chat"):
            st.session_state.show_search_page = False
            st.experimental_rerun()
    
    with cols[1]:
        # Search button - highlight if on search page
        button_style = "solid" if st.session_state.get("show_search_page", False) else "outline"
        st.markdown(f"""
        <style>
        div[data-testid="element-container"]:has(button:contains("Search")) button {{
            width: 120px !important;
            height: 40px !important;
            background: {("linear-gradient(145deg, #2c2c2c, #1e1e1e)" if button_style == "outline" else "linear-gradient(145deg, #2196F3, #1976d2)")} !important;
            color: #e0e0e0 !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            border: 1px solid {("#333" if button_style == "outline" else "#1976d2")} !important;
            border-radius: 8px !important;
            padding: 8px 0px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button("Search", key="goto_search"):
            st.session_state.show_search_page = True
            st.experimental_rerun()

# Add a separator after the navigation
st.markdown("<hr style='margin: 15px 0; border-color: #333; opacity: 0.5;'>", unsafe_allow_html=True)

# Main section - Chat or Search based on selection
if 'show_search_page' not in st.session_state:
    st.session_state.show_search_page = False
    
# Display either Chat or Search based on state
if st.session_state.show_search_page:
    # Search page
    st.markdown("<h3 style='margin-top:0; margin-bottom:10px;'>Search Documents</h3>", unsafe_allow_html=True)
    
    # Document selection for search
    try:
        documents = api_client.get_all_documents()
        if documents:
            # Handle both string and dictionary document formats
            document_names = [doc if isinstance(doc, str) else doc.get('document_name', 'Unknown') for doc in documents]
            selected_doc = st.selectbox(
                "Select a document to search",
                document_names,
                key="search_document"
            )
            
            # Search interface
            col1, col2 = st.columns([5, 1])
            with col1:
                search_query = st.text_input("Enter your search query:", 
                                            key="search_input",
                                            placeholder="Search for specific information...")
            with col2:
                # Add a button with similar styling to the chat send button
                search_button = st.button("Search", key="execute_search", 
                                         help="Search documents",
                                         use_container_width=True)
            
            if search_button and search_query:
                try:
                    with st.spinner("Searching..."):
                        results = api_client.search_documents(
                            document_name=selected_doc,
                            query=search_query
                        )
                        st.markdown('<div style="margin-top: 20px;">', unsafe_allow_html=True)
                        display_search_results(results)
                        st.markdown('</div>', unsafe_allow_html=True)
                except Exception as e:
                    handle_error(e)
        else:
            st.info("Please upload documents to start searching.")
    except Exception as e:
        handle_error(e)
else:
    # Chat page
    st.markdown("<h3 style='margin-top:0; margin-bottom:10px;'>Chat with Documents</h3>", unsafe_allow_html=True)
    
    # Document selection
    try:
        documents = api_client.get_all_documents()
        if documents:
            # Handle both string and dictionary document formats
            document_names = [doc if isinstance(doc, str) else doc.get('document_name', 'Unknown') for doc in documents]
            selected_doc = st.selectbox(
                "Select a document to chat with",
                document_names,
                key="chat_document"
            )
            
            # Set selected document in session state
            st.session_state.selected_document = selected_doc
            
            # Create a single container for the entire chat interface (instead of separate containers)
            chat_area = st.container()
            
            # Display everything in one container
            with chat_area:
                # No outer container - directly display messages
                st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
                
                # Check if there's any chat history for this document
                if selected_doc in st.session_state.chat_history and len(st.session_state.chat_history[selected_doc]) > 0:
                    # Display all previous messages
                    for message in st.session_state.chat_history[selected_doc]:
                        try:
                            if isinstance(message, str):
                                # Legacy format (HTML string)
                                st.markdown(message, unsafe_allow_html=True)
                            else:
                                # New dictionary format
                                if message.get("is_user", False):
                                    st.markdown(f"""
                                    <div class="message-user">
                                        <div style="font-weight: 600; margin-bottom: 6px;">You</div>
                                        <div style="line-height: 1.5;">{message["message"]}</div>
                                        <div class="timestamp">{message.get("timestamp", "")}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.markdown(f"""
                                    <div class="message-assistant">
                                        <div style="font-weight: 600; margin-bottom: 6px;">Assistant</div>
                                        <div>{message["message"]}</div>
                                        <div class="timestamp">{message.get("timestamp", "")}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        except Exception as e:
                            # If there's an error with a message, show a placeholder and continue
                            st.warning(f"Could not display a message. Error: {str(e)}")
                            continue
                else:
                    # No chat history yet
                    st.markdown("""
                    <div style="text-align: center; color: #888; margin: 30px 0;">
                        <p>No messages yet. Start a conversation by typing below.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Chat input form
                st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)
                with st.form(key="chat_form", clear_on_submit=True):
                    # Use columns to place input and button on the same line
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        user_query = st.text_input("", 
                                                key="chat_input", 
                                                placeholder="Ask something about the document...")
                    with col2:
                        submit_button = st.form_submit_button("Send")
                
                    if submit_button and user_query:
                        try:
                            # Add to chat history first (for immediate display)
                            current_time = datetime.datetime.now().strftime('%H:%M:%S')
                            add_to_chat_history(selected_doc, user_query, is_user=True, timestamp=current_time)
                            
                            # Get bot response
                            with st.spinner("Thinking..."):
                                response = api_client.chat_with_document(
                                    document_name=selected_doc,
                                    query=user_query
                                )
                                
                                # Format the response - MODIFIED to handle dictionary responses properly
                                if isinstance(response, dict):
                                    if 'answer' in response:
                                        resp_text = response['answer']
                                    elif 'response' in response:
                                        resp_text = response['response']
                                    else:
                                        resp_text = str(response)
                                else:
                                    resp_text = str(response)
                                    # Try to parse JSON strings
                                    if resp_text.startswith('{') and resp_text.endswith('}'):
                                        try:
                                            resp_obj = json.loads(resp_text)
                                            if 'answer' in resp_obj:
                                                resp_text = resp_obj['answer']
                                        except:
                                            pass
                                
                                # Add bot response to chat history
                                add_to_chat_history(selected_doc, resp_text, timestamp=current_time)
                                
                                # Rerun to update the UI with the new messages
                                st.experimental_rerun()
                                
                        except Exception as e:
                            handle_error(e)
                            error_message = f"Error: {str(e)}"
                            add_to_chat_history(selected_doc, error_message, timestamp=current_time)
                            st.experimental_rerun()
                
                # Optional: Add a button to clear chat history
                if selected_doc in st.session_state.chat_history and len(st.session_state.chat_history[selected_doc]) > 0:
                    if st.button("Clear Chat History", key="clear_chat"):
                        st.session_state.chat_history[selected_doc] = []
                        st.experimental_rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.info("Please upload documents to start chatting.")
    except Exception as e:
        handle_error(e)

# Define test function (move this function up, below imports)
def test_delete_document(document_name):
    """Test direct API call to delete a document"""
    # Update this URL to match your actual API base URL
    api_base_url = "http://localhost:8000"  # Change this to your API URL
    url = f"{api_base_url}/delete-embeddings"
    
    form_data = {"document_name": document_name}
    
    st.write(f"Testing direct delete request to: {url}")
    st.write(f"With form data: {form_data}")
    
    try:
        response = requests.delete(url, data=form_data)
        st.write(f"Status code: {response.status_code}")
        st.write(f"Response: {response.text}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Error in test delete: {str(e)}")
        return None 