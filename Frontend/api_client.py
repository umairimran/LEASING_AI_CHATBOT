import httpx
from typing import List, Dict, Any, Optional
import json
import requests

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def upload_documents(self, files: List[Any]) -> Dict:
        """Upload documents to the backend."""
        try:
            files_data = [("files", file) for file in files]
            response = self.client.post(f"{self.base_url}/upload-documents/", files=files_data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error uploading documents: {str(e)}")

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