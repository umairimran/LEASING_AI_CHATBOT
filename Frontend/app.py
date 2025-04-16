import streamlit as st
import os
import datetime
import json
import requests
import re  # Add re import
from api_client import APIClient
from utils import (
    display_chat_history,
    display_search_results,
    show_loading_spinner,
    handle_error
)

def process_message_text(text):
    """Process message text to ensure proper formatting of lists and other elements"""
    # Replace markdown-style numbered lists with HTML
    
    # Handle code blocks with ```
    code_block_pattern = r'```(?:\w+)?\s*([\s\S]*?)```'
    code_blocks = re.findall(code_block_pattern, text)
    for i, block in enumerate(code_blocks):
        placeholder = f"CODE_BLOCK_{i}"
        text = text.replace(f"```{block}```", placeholder)
    
    # Fix duplicated numbering pattern (the specific issue in our case)
    # Pattern like "1. 1. Item", "1. 2. Item", etc.
    text = re.sub(r'(?m)^1\.\s+(\d+)\.\s+(.*?)$', r'\1. \2', text)
    
    # A more general fix for any number followed by another number
    text = re.sub(r'(?m)^(\d+)\.\s+(\d+)\.\s+(.*?)$', r'\2. \3', text)
    
    # Process numbered lists (e.g., "1. Item")
    # This regex looks for lines starting with a number followed by a period and space
    text = re.sub(r'(?m)^(\d+)\.\s+(.*?)$', r'<li value="\1"><span class="list-number">\1.</span> \2</li>', text)
    
    # Process bullet lists (e.g., "• Item" or "- Item")
    text = re.sub(r'(?m)^[•\-]\s+(.*?)$', r'<li>\1</li>', text)
    
    # Wrap consecutive list items in ol/ul tags
    # First, detect if there are any list items
    if '<li' in text:
        # Split by double newlines to preserve paragraphs
        paragraphs = text.split('\n\n')
        for i, paragraph in enumerate(paragraphs):
            # If paragraph contains list items
            if '<li' in paragraph:
                lines = paragraph.split('\n')
                list_content = []
                in_list = False
                
                for j, line in enumerate(lines):
                    if '<li value=' in line:  # Numbered list
                        if not in_list:
                            list_content.append('<ol class="custom-counter">')
                            in_list = 'ol'
                        list_content.append(line)
                    elif '<li>' in line:  # Bullet list
                        if not in_list:
                            list_content.append('<ul>')
                            in_list = 'ul'
                        elif in_list == 'ol':  # Switch from numbered to bullet
                            list_content.append('</ol><ul>')
                            in_list = 'ul'
                        list_content.append(line)
                    else:
                        if in_list:
                            list_content.append(f'</{in_list}>')
                            in_list = False
                        list_content.append(line)
                
                if in_list:
                    list_content.append(f'</{in_list}>')
                
                paragraphs[i] = '\n'.join(list_content)
        
        text = '\n\n'.join(paragraphs)
    
    # Bold for titles/subtitles that end with a colon
    text = re.sub(r'(?m)^([A-Za-z][A-Za-z\s]+:)(\s*)', r'<strong>\1</strong>\2', text)
    
    # Replace inline code with <code> tags (text between backticks)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Put back code blocks with proper HTML
    for i, block in enumerate(code_blocks):
        formatted_block = f"<pre><code>{block}</code></pre>"
        text = text.replace(f"CODE_BLOCK_{i}", formatted_block)
    
    return text

# Initialize session state variables
def initialize_session_state():
    """Initialize session state variables"""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}
    if 'document_names' not in st.session_state:
        st.session_state.document_names = []
    if 'selected_document' not in st.session_state:
        st.session_state.selected_document = None
    if 'show_search_page' not in st.session_state:
        st.session_state.show_search_page = False
    if 'auto_scroll' not in st.session_state:
        st.session_state.auto_scroll = True
    if 'recent_uploads' not in st.session_state:
        st.session_state.recent_uploads = set()

# Helper function to add message to chat history
def add_to_chat_history(document_name, message, is_user=False, timestamp=None):
    """Add a message to the chat history for a document"""
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

# Format timestamps to be more user-friendly
def format_timestamp(timestamp_str):
    """Convert timestamp to a more user-friendly format"""
    if not timestamp_str:
        return ""
    
    try:
        # Parse the timestamp
        timestamp = datetime.datetime.strptime(timestamp_str, '%H:%M:%S')
        now = datetime.datetime.now()
        
        # If it's today
        if timestamp.date() == now.date():
            # If it's within the last minute
            if (now - timestamp).seconds < 60:
                return "Just now"
            # If it's within the last hour
            elif (now - timestamp).seconds < 3600:
                minutes = (now - timestamp).seconds // 60
                return f"{minutes}m ago"
            else:
                return f"Today, {timestamp.strftime('%I:%M %p')}"
        else:
            return timestamp.strftime('%I:%M %p')
    except:
        return timestamp_str

# Page configuration
st.set_page_config(
    page_title="Leasing AI Chatbot",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client and session state
api_client = APIClient()

# Make sure to initialize session state
initialize_session_state()

# Custom CSS
st.markdown("""
    <style>
    /* Global styling */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
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
        width: 100%;
        max-width: 100%;
    }
    
    /* Make the content area take full width */
    .block-container, [data-testid="stVerticalBlock"] {
        max-width: 100% !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
    }
    
    /* Ensure the main container expands */
    .css-18e3th9 {
        padding-top: 0;
        padding-bottom: 0;
        max-width: 100% !important;
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
        background: transparent;
        padding: 0;
        margin-bottom: 0;
        box-shadow: none;
        border: none;
        position: relative;
        z-index: 100;
        width: 100%;
    }
    
    /* Form input styling */
    div[data-testid="stForm"] [data-testid="stTextInput"] input {
        background-color: #2c2c2c;
        border: 1px solid #444;
        border-radius: 8px;
        color: #ffffff;
        font-size: 16px;
        padding: 12px 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        width: 100%;
        height: 48px;
    }
    
    div[data-testid="stForm"] [data-testid="stTextInput"] input:focus {
        border: 1px solid #1976d2;
        box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.3);
        outline: none;
    }
    
    /* Send button styling */
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(145deg, #1976d2, #0d47a1);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        height: 42px;
        margin: 0;
        padding: 0 22px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
    }
    
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(145deg, #0d47a1, #0a3880);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
    }
    
    /* Hide form label */
    div[data-testid="stForm"] label {
        display: none;
    }
    
    /* Message containers */
    .message-container {
        margin: 12px 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
        width: 100%;
    }
    
    .message-user {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        color: white;
        padding: 12px 16px;
        border-radius: 12px;
        align-self: flex-end;
        max-width: 80%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        word-wrap: break-word;
        margin-bottom: 8px;
    }
    
    .message-assistant {
        background-color: #2c2c2c;
        color: #ffffff;
        padding: 12px 16px;
        border-radius: 12px;
        align-self: flex-start;
        max-width: 80%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        word-wrap: break-word;
        line-height: 1.5;
        margin-bottom: 8px;
    }
    
    /* Other containers */
    .chat-messages {
        display: flex;
        flex-direction: column;
        gap: 0;
        margin: 0;
        padding: 0;
        flex-grow: 1;
        overflow-y: auto;
        background-color: #121212;
        width: 100%;
        padding-bottom: 90px;
    }
    
    /* Empty state styling */
    .empty-chat-message {
        text-align: center;
        color: #888;
        padding: 10px 0;
        font-size: 14px;
        margin-top: 0;
    }
    
    /* Document select container */
    .document-select-container {
        position: sticky;
        top: 30px;
        z-index: 99;
        padding: 10px 20px;
        background-color: #1a1a1a;
        border-bottom: 1px solid #333;
        margin-bottom: 10px;
    }
    
    /* Hide document selection */
    .sidebar-document-selection {
        display: none;
    }
    
    /* Main content header styling */
    .content-header {
        padding: 10px 20px;
        background-color: #1a1a1a;
        border-bottom: 1px solid #333;
    }
    
    /* ChatGPT-like message styling with better contrast */
    .chatgpt-message-container {
        display: flex;
        padding: 2px 8% 2px;
        width: 100%;
        min-height: 0;
        animation: fadeIn 0.2s ease-in-out;
        margin-bottom: 0;
        border-bottom: 0;
    }
    
    /* First message should have no top padding */
    .chat-messages > .chatgpt-message-container:first-child {
        padding-top: 0;
        margin-top: -5px;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(3px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-message-container {
        background-color: #191919;
        justify-content: flex-end;
        padding-right: 4%;
        margin-bottom: 0;
        border: none;
    }
    
    .assistant-message-container {
        background-color: #1e1e1e;
        justify-content: flex-start;
        padding-left: 4%;
        border-top: 1px solid #2a2a2a;
        border-bottom: 1px solid #2a2a2a;
        margin-bottom: 0;
    }
    
    /* Message content styling with improved readability */
    .message-content {
        flex: 0 1 auto;
        max-width: 80%;
        margin-top: 0;
        background-color: #2a2a2a;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }
    
    .user-message .message-content {
        background: linear-gradient(145deg, #1976d2, #0d47a1);
        margin-left: auto;
        border-radius: 12px 12px 2px 12px;
    }
    
    .assistant-message .message-content {
        background-color: #333333;
        margin-right: auto;
        border-radius: 10px 10px 10px 2px;
        padding: 12px 16px;
    }
    
    .message-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        margin-right: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-weight: bold;
        font-size: 12px;
    }
    
    .user-avatar {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        color: white;
        margin-right: 0;
        margin-left: 10px;
        order: 2;
    }
    
    .assistant-avatar {
        background-color: #40826D;
        color: white;
    }
    
    .message-header {
        font-weight: 600;
        margin-bottom: 4px;
        color: #ffffff;
        font-size: 0.85rem;
    }
    
    .message-text {
        line-height: 1.5;
        color: #ffffff;
        white-space: pre-wrap;
        word-break: break-word;
        font-size: 15px;
    }
    
    /* Improve formatting for lists in messages */
    .message-text ol, .message-text ul {
        margin-top: 0.5em;
        margin-bottom: 0.5em;
        padding-left: 1.5em;
    }
    
    .message-text .custom-counter {
        list-style-type: none;
        margin-left: 0;
        padding-left: 1.5em;
    }
    
    .message-text .custom-counter li {
        counter-increment: none !important;
        position: relative;
    }
    
    .message-text .list-number {
        font-weight: bold;
        color: #ffffff;
    }
    
    .message-text ul {
        list-style-type: disc;
    }
    
    .message-text li {
        margin-bottom: 0.5em;
    }
    
    .message-text p {
        margin-top: 0.5em;
        margin-bottom: 0.5em;
    }
    
    /* Style for headings in messages */
    .message-text h1, .message-text h2, .message-text h3, .message-text h4 {
        margin-top: 0.75em;
        margin-bottom: 0.5em;
        font-weight: 600;
    }
    
    /* Bold and emphasis styles */
    .message-text strong, .message-text b {
        font-weight: 700;
        color: #ffffff;
    }
    
    .message-text em, .message-text i {
        font-style: italic;
    }
    
    /* Code and pre formatting */
    .message-text code {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        background-color: #1e1e1e;
        padding: 0.2em 0.4em;
        border-radius: 3px;
        font-size: 0.9em;
        color: #e0e0e0;
    }
    
    .message-text pre {
        background-color: #1e1e1e;
        border-radius: 6px;
        padding: 0.8em;
        overflow-x: auto;
        margin: 0.7em 0;
        border: 1px solid #333;
    }
    
    .message-text pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
        color: #e0e0e0;
    }
    
    /* Table styling */
    .message-text table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
        border: 1px solid #333;
    }
    
    .message-text th {
        background-color: #1e1e1e;
        border: 1px solid #333;
        padding: 8px;
        text-align: left;
        font-weight: 600;
    }
    
    .message-text td {
        border: 1px solid #333;
        padding: 8px;
    }
    
    /* Quote styling */
    .message-text blockquote {
        border-left: 4px solid #444;
        margin: 0.7em 0;
        padding: 0.5em 10px;
        color: #aaa;
        font-style: italic;
    }
    
    .message-timestamp {
        font-size: 0.65rem;
        color: #aaa;
        margin-top: 4px;
        text-align: right;
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
        border: 1px solid #444;
        padding: 2px;
    }
    
    div[data-testid="stSelectbox"] > div[data-baseweb="select"] > div {
        background-color: #2c2c2c;
        border-radius: 8px;
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
        padding: 20px;
        border: 2px dashed #1976d2;
        margin-bottom: 16px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"]:hover {
        background-color: #252525;
        border-color: #2196F3;
    }
    
    [data-testid="stFileUploader"] p {
        color: #e0e0e0;
    }
    
    /* File uploader button */
    [data-testid="stFileUploader"] button {
        background-color: #1976d2 !important;
        color: white !important;
        border: none !important;
        padding: 10px 16px !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        margin-top: 8px !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stFileUploader"] button:hover {
        background-color: #0d47a1 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* Upload success message */
    .upload-success {
        background-color: rgba(46, 125, 50, 0.2);
        color: #81c784;
        padding: 12px 16px;
        border-radius: 8px;
        border-left: 4px solid #4caf50;
        margin: 12px 0;
        font-weight: 500;
        display: flex;
        align-items: center;
    }
    
    .upload-success:before {
        content: "✓";
        font-size: 18px;
        margin-right: 10px;
        font-weight: bold;
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
    
    /* Sticky chat input at bottom - fixed position */
    .chat-input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: rgba(18, 18, 18, 0.95);
        padding: 10px 20px;
        z-index: 1000;
        border-top: 1px solid #333;
        width: 100%;
        max-width: 100%;
        backdrop-filter: blur(10px);
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.2);
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
    
    /* Additional container styling for responsiveness */
    .css-1r6slb0, .css-1d391kg, .css-1dm3euu {
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Ensure st.columns adjusts properly to full width */
    [data-testid="column"] {
        width: 100%;
    }
    
    /* Fix any width limitations for search and chat input containers */
    [data-testid="stFormSubmit"] {
        width: 100%;
    }
    
    /* ChatGPT-like input styling */
    .chatgpt-input-container {
        border: 1px solid #444;
        border-radius: 10px;
        background-color: #1e1e1e;
        padding: 6px 10px;
        display: flex;
        align-items: center;
        position: relative;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    }
    
    /* ChatGPT-like container structure */
    .chatgpt-container {
        display: flex;
        flex-direction: column;
        height: calc(100vh - 100px);
        position: relative;
        overflow: hidden;
        margin-top: -10px;
        padding-top: 0;
        background-color: #121212;
    }
    
    /* Chat messages container with auto-scroll */
    .chat-messages {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow-y: auto;
        margin: 0;
        padding: 0 0 70px 0; /* Reduced padding */
        background-color: #121212;
        width: 100%;
        position: absolute;
        top: 0;
        bottom: 70px;
        left: 0;
        right: 0;
        scroll-behavior: smooth;
    }
    
    /* ChatGPT-like message styling with better contrast */
    .chatgpt-message-container {
        display: flex;
        padding: 8px 8% 4px;
        width: 100%;
        min-height: 40px;
        animation: fadeIn 0.3s ease-in-out;
        margin-bottom: 0;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(5px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-message-container {
        background-color: #191919;
        justify-content: flex-end;
        padding-right: 4%;
        margin-bottom: 0;
    }
    
    .assistant-message-container {
        background-color: #1e1e1e;
        justify-content: flex-start;
        padding-left: 4%;
        border-top: 1px solid #333;
        border-bottom: 1px solid #333;
        margin-bottom: 0;
    }
    
    /* Message content styling with improved readability */
    .message-content {
        flex: 0 1 auto;
        max-width: 80%;
        margin-top: 0;
        background-color: #2a2a2a;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }
    
    .user-message .message-content {
        background: linear-gradient(145deg, #1976d2, #0d47a1);
        margin-left: auto;
        border-radius: 12px 12px 2px 12px;
    }
    
    .assistant-message .message-content {
        background-color: #333333;
        margin-right: auto;
        border-radius: 10px 10px 10px 2px;
        padding: 12px 16px;
    }
    
    .message-avatar {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        margin-right: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-weight: bold;
        font-size: 12px;
    }
    
    .user-avatar {
        background: linear-gradient(145deg, #2196F3, #1976d2);
        color: white;
        margin-right: 0;
        margin-left: 8px;
        order: 2;
    }
    
    .assistant-avatar {
        background-color: #40826D;
        color: white;
    }
    
    .message-header {
        font-weight: 600;
        margin-bottom: 2px;
        color: #ffffff;
        font-size: 0.8rem;
    }
    
    .message-text {
        line-height: 1.4;
        color: #ffffff;
        white-space: pre-wrap;
        word-break: break-word;
    }
    
    .message-timestamp {
        font-size: 0.65rem;
        color: #aaa;
        margin-top: 3px;
        text-align: right;
    }
    
    /* Auto-scroll toggle */
    .auto-scroll-toggle {
        position: fixed;
        bottom: 70px;
        right: 15px;
        z-index: 999;
        background-color: #1e1e1e;
        border: 1px solid #444;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        opacity: 0.7;
        transition: opacity 0.2s ease;
    }
    
    .auto-scroll-toggle:hover {
        opacity: 1;
    }
    
    .auto-scroll-toggle.active {
        background-color: #2196F3;
        border-color: #1976d2;
    }
    
    .auto-scroll-toggle svg {
        color: #fff;
        width: 16px;
        height: 16px;
    }
    
    /* Document name formatting */
    .document-name {
        max-width: 200px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 14px;
        color: #ffffff;
        padding: 6px 0;
    }
    
    /* Recently uploaded indicator */
    .recent-upload {
        display: inline-block;
        background-color: #1976d2;
        color: white;
        border-radius: 4px;
        padding: 2px 6px;
        margin-left: 8px;
        font-size: 10px;
        vertical-align: middle;
    }
    
    /* Set overall layout to match ChatGPT */
    .block-container {
        padding-top: 0 !important;
    }
    
    /* Fixed header position */
    .content-header {
        position: sticky;
        top: 0;
        z-index: 100;
        padding: 2px 20px;
        background-color: #1a1a1a;
        border-bottom: 1px solid #333;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }
    
    /* Document select in fixed header */
    .document-select-container {
        position: sticky;
        top: 30px;
        z-index: 99;
        padding: 10px 20px;
        background-color: #1a1a1a;
        border-bottom: 1px solid #333;
        margin-bottom: 10px;
    }
    
    /* Navigation container */
    .nav-container {
        position: sticky;
        top: 0;
        z-index: 101;
        background-color: #1a1a1a;
        border-bottom: 1px solid #333;
        padding: 8px 20px;
        display: flex;
        align-items: center;
    }
    
    /* Auto-focus input when page loads */
    input:focus {
        outline: none !important;
    }
    
    /* Compact form styling */
    div[data-testid="stForm"] [data-testid="stTextInput"] input {
        height: 36px;
    }
    
    div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        height: 36px;
    }
    
    /* Add custom spacing fixes for the chat interface */
    .main > .block-container {
        padding-top: 0 !important;
        margin-top: -20px !important;
    }
    
    .content-header, .document-select-container {
        margin: 0 !important;
        padding: 1px 10px !important;
    }
    
    .content-header h3 {
        font-size: 14px !important;
    }
    
    /* Make the chat interface more compact */
    .chat-messages {
        margin-top: -10px !important;
        padding-top: 0 !important;
        position: absolute !important;
        top: 0 !important;
        bottom: 65px !important;
        left: 0 !important;
        right: 0 !important;
        overflow-y: auto !important;
        background-color: #121212 !important;
    }
    
    /* Ensure selectbox is as compact as possible */
    div[data-testid="stSelectbox"] > div {
        min-height: 0 !important;
    }
    
    /* Remove extra space in messages */
    .chatgpt-message-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        min-height: 0 !important;
    }
    
    /* Fill empty space with proper styling */
    .chatgpt-container {
        display: flex !important;
        flex-direction: column !important;
        height: calc(100vh - 80px) !important;
        position: absolute !important;
        top: 40px !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        background-color: #121212 !important;
    }
    
    /* Hide any unwanted space */
    .block-container {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Ensure the chat container fills the entire area */
    .css-1544g2n {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Empty message styling */
    .empty-chat-message {
        padding: 0 !important;
        margin: 0 !important;
        text-align: center;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 80%;
    }
    
    /* Prevent scrollbar from taking up space */
    ::-webkit-scrollbar {
        width: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #333;
        border-radius: 3px;
    }

    @media (max-width: 768px) {
        .message-content {
            max-width: 90%;
        }
        
        .chatgpt-message-container {
            padding-left: 4% !important;
            padding-right: 4% !important;
        }
        
        .empty-chat-message {
            width: 95%;
        }
    }
    </style>
""", unsafe_allow_html=True)

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
    # Add logo and branding
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <div style="background-color: #1976d2; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
            <span style="color: white; font-size: 22px; font-weight: bold;">🏢</span>
        </div>
        <h1 style="margin: 0; padding: 0; font-size: 24px;">Leasing AI</h1>
    </div>
    """, unsafe_allow_html=True)
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
                    # Mark the uploaded files as recent
                    for file in uploaded_files:
                        st.session_state.recent_uploads.add(file.name)
                    st.markdown('<div class="upload-success">Documents processed successfully!</div>', unsafe_allow_html=True)
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
                
                # Format document name for display
                display_name = doc_name.replace('_', ' ').title()
                
                # Create columns with better ratio
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Show document name with recent indicator if applicable
                    is_recent = doc_name in st.session_state.recent_uploads
                    recent_tag = f'<span class="recent-upload">NEW</span>' if is_recent else ''
                    st.markdown(f'<div class="document-name" title="{doc_name}">{display_name} {recent_tag}</div>', unsafe_allow_html=True)
                
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
                                    # Remove from recent uploads if present
                                    if doc_name in st.session_state.recent_uploads:
                                        st.session_state.recent_uploads.remove(doc_name)
                                    st.markdown('<div class="upload-success">Document deleted successfully!</div>', unsafe_allow_html=True)
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete document. Status code: {response.status_code}")
                            except Exception as e:
                                handle_error(e)
                        else:
                            # Set confirmation state and show confirmation message
                            st.session_state[f"confirm_{unique_key}"] = True
                            st.markdown(f'<div style="background-color: rgba(255, 59, 48, 0.2); padding: 10px; border-radius: 6px; color: #ff6b6b; border-left: 3px solid #ff3b30;">Click again to confirm deletion of \'{display_name}\'</div>', unsafe_allow_html=True)
    except Exception as e:
        handle_error(e)

# Main content
st.title("", anchor=False)

# Create container for page navigation
nav_container = st.container()
with nav_container:
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 4])
    
    # Add page indicators with consistent sizing
    with cols[0]:
        # Chat button - highlight if on chat page
        button_style = "solid" if not st.session_state.get("show_search_page", False) else "outline"
        st.markdown(f"""
        <style>
        div[data-testid="element-container"]:has(button:contains("Chat")) button {{
            width: 100px !important;
            height: 36px !important;
            background: {("linear-gradient(145deg, #2c2c2c, #1e1e1e)" if button_style == "outline" else "linear-gradient(145deg, #2196F3, #1976d2)")} !important;
            color: #e0e0e0 !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            border: 1px solid {("#333" if button_style == "outline" else "#1976d2")} !important;
            border-radius: 8px !important;
            padding: 0 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button("Chat", key="goto_chat"):
            st.session_state.show_search_page = False
            st.rerun()
    
    with cols[1]:
        # Search button - highlight if on search page
        button_style = "solid" if st.session_state.get("show_search_page", False) else "outline"
        st.markdown(f"""
        <style>
        div[data-testid="element-container"]:has(button:contains("Search")) button {{
            width: 100px !important;
            height: 36px !important;
            background: {("linear-gradient(145deg, #2c2c2c, #1e1e1e)" if button_style == "outline" else "linear-gradient(145deg, #2196F3, #1976d2)")} !important;
            color: #e0e0e0 !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            border: 1px solid {("#333" if button_style == "outline" else "#1976d2")} !important;
            border-radius: 8px !important;
            padding: 0 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button("Search", key="goto_search"):
            st.session_state.show_search_page = True
            st.rerun()
    
    # Empty column in the middle, removing the title
    with cols[2]:
        st.markdown('', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# No separator needed since nav container has a border bottom
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
    st.markdown('<div class="content-header">', unsafe_allow_html=True)
    st.markdown("<h3 style='margin:0; padding:0; font-size:16px;'>Chat with Documents</h3>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Document selection
    try:
        documents = api_client.get_all_documents()
        if documents:
            # Handle both string and dictionary document formats
            document_names = [doc if isinstance(doc, str) else doc.get('document_name', 'Unknown') for doc in documents]
            
            # Document selection section with better styling
            st.markdown('<div class="document-select-container" style="margin-top:-5px; padding-top:0; padding-bottom:0;">', unsafe_allow_html=True)
            selected_doc = st.selectbox(
                "Select a document to chat with",
                document_names,
                key="selected_document",  # Changed from chat_document to selected_document
                format_func=lambda x: x.replace('_', ' ').title() if isinstance(x, str) else x,
                label_visibility="collapsed"
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Add custom CSS to make selectbox more compact
            st.markdown("""
            <style>
            div[data-testid="stSelectbox"] {
                margin-bottom: 0 !important;
                padding: 0 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Set selected document in session state
            st.session_state.selected_document = selected_doc
            
            # Create a container for the entire chat interface that mimics ChatGPT
            st.markdown('<div class="chatgpt-container" style="height:calc(100vh - 80px);position:absolute;top:40px;left:0;right:0;bottom:0;overflow:hidden;">', unsafe_allow_html=True)
            
            # Add auto-scroll toggle button with simpler implementation
            auto_scroll_active = "active" if st.session_state.auto_scroll else ""
            st.markdown(f"""
            <div class="auto-scroll-toggle {auto_scroll_active}" id="auto-scroll-toggle" title="Toggle auto-scroll" onclick="toggleAutoScroll()">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M11 4h2v12l5.5-5.5 1.42 1.42L12 19.84l-7.92-7.92L5.5 10.5 11 16V4z"/>
                </svg>
            </div>
            """, unsafe_allow_html=True)
            
            # Add JavaScript for auto-scrolling and button functionality (simplified)
            st.markdown("""
            <script>
                // Auto-scroll function
                function scrollToBottom() {
                    const chatMessages = document.getElementById('chat-messages');
                    if (chatMessages) {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                }
                
                // Toggle auto-scroll (simplified)
                function toggleAutoScroll() {
                    const toggleBtn = document.getElementById('auto-scroll-toggle');
                    toggleBtn.classList.toggle('active');
                }
                
                // Attempt to scroll initially and after content changes
                window.addEventListener('load', function() {
                    scrollToBottom();
                    setTimeout(scrollToBottom, 500);
                });
                
                // Watch for new messages
                const observer = new MutationObserver(function() {
                    scrollToBottom();
                });
                
                // Start observing
                document.addEventListener('DOMContentLoaded', function() {
                    const chatMessages = document.getElementById('chat-messages');
                    if (chatMessages) {
                        observer.observe(chatMessages, { childList: true, subtree: true });
                    }
                });
            </script>
            """, unsafe_allow_html=True)
            
            # Create chat messages container
            st.markdown('<div class="chat-messages" id="chat-messages">', unsafe_allow_html=True)
            
            # Check if there's any chat history for this document
            if selected_doc in st.session_state.chat_history and len(st.session_state.chat_history[selected_doc]) > 0:
                # Display all previous messages
                for message in st.session_state.chat_history[selected_doc]:
                    try:
                        if isinstance(message, str):
                            # Legacy format (HTML string) - should be converted with convert_chat_history_format
                            st.markdown(message, unsafe_allow_html=True)
                        else:
                            # Format timestamp
                            formatted_time = format_timestamp(message.get("timestamp", ""))
                            
                            # Process message text for better formatting
                            message_text = process_message_text(message["message"])
                            
                            # New dictionary format with ChatGPT-like styling
                            if message.get("is_user", False):
                                # User message
                                st.markdown(f"""<div class="chatgpt-message-container user-message-container" style="padding-top:0"><div class="message-content user-message"><div class="message-header">You</div><div class="message-text">{message_text}</div><div class="message-timestamp">{formatted_time}</div></div><div class="message-avatar user-avatar">U</div></div>""", unsafe_allow_html=True)
                            else:
                                # Assistant message
                                st.markdown(f"""<div class="chatgpt-message-container assistant-message-container" style="padding-top:0"><div class="message-avatar assistant-avatar">A</div><div class="message-content assistant-message"><div class="message-header">Assistant</div><div class="message-text">{message_text}</div><div class="message-timestamp">{formatted_time}</div></div></div>""", unsafe_allow_html=True)
                    except Exception as e:
                        # If there's an error with a message, show a placeholder and continue
                        st.warning(f"Could not display a message. Error: {str(e)}")
                        continue
            else:
                # No chat history yet
                st.markdown(f"""
                <div class="empty-chat-message">
                    <div style="background-color: rgba(33, 33, 33, 0.5); padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); width: 100%; max-width: 600px; margin: 0 auto;">
                        <h3 style="margin:0;padding:0;color:#e0e0e0;font-size:20px;text-align:center;margin-bottom:15px;">Welcome to {selected_doc.replace('_', ' ').title()} Document</h3>
                        <p style="margin:0;padding:0;color:#aaa;font-size:15px;text-align:center;line-height:1.5;">I see you've selected a leasing document. You can ask me questions about lease terms, payment schedules, property details, or any other information contained in the document.</p>
                        <div style="margin-top:20px;text-align:center;">
                            <div style="display:inline-block;width:40px;height:40px;background-color:#40826D;border-radius:50%;line-height:40px;color:white;font-weight:bold;">A</div>
                        </div>
                        <div style="margin-top:15px;text-align:center;">
                            <p style="color:#999;font-size:13px;">Try asking: "What are the payment terms?" or "Summarize the lease agreement"</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            # Close chat messages container
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Chat input form
            st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)
            
            # Container for the chatgpt-like input styling
            st.markdown('<div class="chatgpt-input-container">', unsafe_allow_html=True)
            
            with st.form(key="chat_form", clear_on_submit=True):
                # Use columns to place input and button on the same line with proper ratio
                col1, col2 = st.columns([6, 1])
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
                            st.rerun()
                            
                    except Exception as e:
                        handle_error(e)
                        error_message = f"Error: {str(e)}"
                        add_to_chat_history(selected_doc, error_message, timestamp=current_time)
                        st.rerun()
            
            # Close the chatgpt-like input container
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Close chat input area
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Close chatgpt container
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