import httpx
from typing import List, Dict, Any, Optional
import json
import requests
import time
import streamlit as st

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def check_api_connection(self):
        """Check if the API is ready and database is connected"""
        try:
            # Using base URL since there's no health endpoint
            response = requests.get(f"{self.base_url}/")
            return response.status_code == 200
        except requests.RequestException:
            return False

    def upload_documents(self, files: List[Any]) -> Dict:
        """Upload documents to the backend."""
        try:
           
            files_data = [("files", file) for file in files]
            
            response = self.client.post(f"{self.base_url}/upload-documents/", files=files_data, timeout=1000)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error uploading documents: {str(e)}")

    def wait_for_api_connection(self):
        """Wait for the API to be ready and database to be connected"""
        attempt = 1
        placeholder = st.empty()
        while True:
            try:
                placeholder.info(f"Waiting for database connection... (Attempt {attempt})")
                if self.check_api_connection():
                    placeholder.success("Connected successfully!")
                    time.sleep(1)
                    placeholder.empty()
                    st.session_state.api_connected = True
                    return True
                attempt += 1
                time.sleep(2)
            except Exception:
                attempt += 1
                time.sleep(2)

    def get_all_documents(self) -> List[Dict]:
        """Get all uploaded documents."""
        try:
            response = self.client.get(f"{self.base_url}/get_all_documents")
            response.raise_for_status()
            return response.json()["documents"]
        except Exception as e:
            raise Exception(f"Error getting documents: {str(e)}")

    def search_documents(self, document_name: str, query: str, limit: int = 5, alpha: float = 0.5) -> Dict:
        """Search within a specific document."""
        try:
            data = {
                "document_name": document_name,
                "query": query,
                "limit": limit,
                "alpha": alpha
            }
            response = self.client.post(f"{self.base_url}/search/", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error searching documents: {str(e)}")

    def chat_with_document(self, document_name: str, query: str, limit: int = 5, alpha: float = 0.5) -> Dict:
        """Chat with a specific document."""
        try:
            data = {
                "document_name": document_name,
                "query": query,
                "limit": limit,
                "alpha": alpha
            }
            response = self.client.post(f"{self.base_url}/chat/", data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error chatting with document: {str(e)}")

    def delete_embeddings(self, document_name):
        """Delete document embeddings"""
        try:
            # The correct endpoint is /delete-embeddings with form data
            url = f"{self.base_url}/delete-embeddings"
            
            # Use form data to match the backend's expectations
            form_data = {"document_name": document_name}
            
            # Make the DELETE request with form data
            response = requests.delete(url, data=form_data)
            
            # Check if response is successful
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Server error (Status code: {response.status_code})"
                if response.text:
                    try:
                        error_data = response.json()
                        if "detail" in error_data:
                            error_msg = error_data["detail"]
                    except:
                        error_msg = response.text
                raise Exception(error_msg)
        except requests.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error deleting embeddings: {str(e)}")

    def __del__(self):
        """Close the HTTP client when the object is destroyed."""
        self.client.close() 

