import streamlit as st

# ✅ Must be first!
st.set_page_config(page_title="ChatBot", page_icon="💬")
from sidebar import create_sidebar
from chatbot_module import chatbot
# Load CSS
from api_client import APIClient
api_client = APIClient()

# Initialize session state variables


# Initialize all session state variables
if 'api_connected' not in st.session_state:
    st.session_state.api_connected = False
if "recent_uploads" not in st.session_state:
    st.session_state.recent_uploads = set()
if "selected_document" not in st.session_state:  # Add this initialization
    st.session_state.selected_document = None
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if st.session_state.api_connected is False:
    api_client.wait_for_api_connection()
# Only run connection check if not already connected

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
# Add a side menu (left sidebar)
create_sidebar()

load_css("Frontend/styles.css")
category = st.session_state.get("selected_category")
if category:
    st.caption(f"Category: {category}")
st.title("💬 Leasing AI Chatbot")
chatbot()

