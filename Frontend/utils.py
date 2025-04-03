import streamlit as st
from typing import List, Dict, Any
import time
from datetime import datetime

def initialize_session_state():
    """Initialize session state variables."""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}
    if 'selected_document' not in st.session_state:
        st.session_state.selected_document = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = {}

def format_chat_message(message: str, is_user: bool = False) -> str:
    """Format chat messages with HTML and CSS."""
    timestamp = format_timestamp()
    
    # Clean the message - handle potential JSON strings
    if message.startswith('{') and message.endswith('}'):
        try:
            import json
            message_obj = json.loads(message)
            if 'answer' in message_obj:
                message = message_obj['answer']
        except:
            pass
            
    if is_user:
        return f"""
        <div style="
            background-color: #007bff;
            color: white;
            padding: 12px 16px;
            border-radius: 18px 18px 4px 18px;
            margin: 8px 0;
            max-width: 80%;
            margin-left: auto;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            word-wrap: break-word;
        ">
            <div style="font-weight: bold; margin-bottom: 4px;">You</div>
            <div>{message}</div>
            <div style="text-align: right; font-size: 0.7rem; margin-top: 4px; opacity: 0.7;">{timestamp}</div>
        </div>
        """
    else:
        return f"""
        <div style="
            background-color: #f0f0f0;
            color: #333;
            padding: 12px 16px;
            border-radius: 18px 18px 18px 4px;
            margin: 8px 0;
            max-width: 80%;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            word-wrap: break-word;
        ">
            <div style="font-weight: bold; margin-bottom: 4px;">Assistant</div>
            <div>{message}</div>
            <div style="text-align: right; font-size: 0.7rem; margin-top: 4px; opacity: 0.7;">{timestamp}</div>
        </div>
        """

def display_chat_history(document_name: str):
    """Display chat history for a specific document."""
    if document_name in st.session_state.chat_history:
        for message in st.session_state.chat_history[document_name]:
            if isinstance(message, str):
                # For backward compatibility with old format
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

def add_to_chat_history(document_name: str, message: str, is_user: bool = False, timestamp: str = None):
    """Add a message to the chat history."""
    if document_name not in st.session_state.chat_history:
        st.session_state.chat_history[document_name] = []
    
    if timestamp is None:
        timestamp = format_timestamp()
        
    # Store as a dictionary instead of HTML string
    st.session_state.chat_history[document_name].append({
        "message": message,
        "is_user": is_user,
        "timestamp": timestamp
    })

def display_search_results(results: Dict[str, Any]):
    """Display search results in a formatted way."""
    if not results or 'results' not in results:
        st.warning("No search results found.")
        return

    for idx, result in enumerate(results['results'], 1):
        with st.expander(f"Result {idx} (Score: {result.get('score', 'N/A'):.2f})"):
            st.markdown("""
            <div style="
                background-color: #1e1e1e;
                border-left: 4px solid #2196F3;
                padding: 10px;
                border-radius: 4px;
                color: #e0e0e0;
            ">
            """ + result.get('text', 'No text available') + """
            </div>
            """, unsafe_allow_html=True)

def show_loading_spinner(message: str = "Processing..."):
    """Show a loading spinner with a custom message."""
    with st.spinner(message):
        time.sleep(0.5)  # Minimum display time for better UX

def format_timestamp() -> str:
    """Format current timestamp for chat messages."""
    return datetime.now().strftime("%H:%M:%S")

def handle_error(error: Exception):
    """Handle and display errors in a user-friendly way."""
    st.error(f"An error occurred: {str(error)}")
    st.info("Please try again or contact support if the problem persists.") 