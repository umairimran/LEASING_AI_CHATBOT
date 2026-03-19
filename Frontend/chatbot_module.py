import streamlit as st
import datetime
from api_client import APIClient

# Initialize API client
api_client = APIClient()

def initialize_chat_state():
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}
    if 'selected_document' not in st.session_state:
        st.session_state.selected_document = None

def add_to_chat_history(document_name, message, is_user=False, timestamp=None):
    """Add a message to the chat history"""
    if document_name not in st.session_state.chat_history:
        st.session_state.chat_history[document_name] = []
    
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    
    message_data = {
        "message": message,
        "is_user": is_user,
        "timestamp": timestamp
    }
    
    st.session_state.chat_history[document_name].append(message_data)

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    if not timestamp_str:
        return ""
    return timestamp_str

def chatbot():
    """Main chatbot function"""
    # Initialize chat state
    initialize_chat_state()

    # Require category first
    selected_category = st.session_state.get("selected_category")
    if not selected_category:
        st.info("Please choose a category from the sidebar to start.")
        return

    # Category-wide chat (no per-document selection)
    selected_document = None
    chat_scope_key = f"category::{selected_category}"

    # Display chat history
    if chat_scope_key in st.session_state.chat_history:
        for message in st.session_state.chat_history[chat_scope_key]:
            time = format_timestamp(message.get("timestamp", ""))
            text = message["message"]
            
            if message.get("is_user", False):
                # User message
                with st.chat_message("user"):
                    st.markdown(f"<div style='font-size: 22px;'>{text}</div>", unsafe_allow_html=True)
                    st.caption(f"{time}")
            else:
                # Assistant message 
                with st.chat_message("assistant"):
                    st.markdown(f"<div style='font-size: 22px;'>{text}</div>", unsafe_allow_html=True)
                    st.caption(f"{time}")

    # Chat input
    prompt_hint = "Ask something..."
    if selected_document:
        prompt_hint = "Ask something about the selected document..."
    else:
        prompt_hint = "Ask something (will use latest document in this category)..."
    user_query = st.chat_input(prompt_hint)
    
    if user_query:
        try:
            # Add user message to chat history
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            add_to_chat_history(chat_scope_key, user_query, is_user=True, timestamp=current_time)
            
            # Get bot response
            with st.spinner("Thinking..."):
                response = api_client.chat_by_category(
                    category=selected_category,
                    query=user_query
                )
                
                # Format response
                if isinstance(response, dict):
                    resp_text = response.get('answer') or response.get('response') or str(response)
                else:
                    resp_text = str(response)
                
                # Add bot response to chat history
                add_to_chat_history(chat_scope_key, resp_text, timestamp=current_time)
                
                # Rerun to update the UI
                st.rerun()
                
        except Exception as e:
            st.error(f"Error: {str(e)}")