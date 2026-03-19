import os
import tempfile
import logging
from typing import Any, Dict, List
import PyPDF2
import json
import requests

import docx
import fitz

import tiktoken
from weaviate.classes.query import HybridFusion, MetadataQuery
from langchain.text_splitter import RecursiveCharacterTextSplitter

 # PyMuPDF for PDF image extraction
import base64
from Backend.database import get_conversation_history, store_conversation
from groq import Groq
from Backend.models import ChatResponse, SearchResponse, SearchResult
from Backend.weaviate_client import WeaviateClientPool ,   get_or_create_weaviate_class
import os
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
from dotenv import load_dotenv
load_dotenv()
# Configure logging
logger = logging.getLogger(__name__)
class_names_file_path = 'class_names.json'
def extract_text_from_pdf(file_path):
    """Extract text from a PDF using PyPDF2."""
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def extract_images_from_pdf(pdf_path):
    """Extract images from PDF pages (bytes + mime_type)."""
    images: List[Dict[str, Any]] = []
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            ext = (base_image.get("ext") or "jpeg").lower()
            mime_type = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else ext}"
            images.append({"bytes": image_bytes, "mime_type": mime_type})
    
    pdf_document.close()
    return images

def process_scanned_pdf(pdf_path):
    """Process scanned PDF using Gemini vision model."""
    images = extract_images_from_pdf(pdf_path)
    extracted_text = []

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required to process scanned PDFs.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model_id = os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"))

    for img in images:
        try:
            resp = client.models.generate_content(
                model=model_id,
                contents=[
                    "Extract all readable text from this image. Output only the extracted text.",
                    types.Part.from_bytes(data=img["bytes"], mime_type=img["mime_type"]),
                ],
            )
            extracted_text.append((getattr(resp, "text", None) or "").strip())
        except Exception as e:
            logger.error(f"Error processing image with Gemini Vision: {str(e)}")
            continue

    try:
        client.close()
    except Exception:
        pass

    return " ".join([t for t in extracted_text if t])

def extract_text(file_path):
    """Extract text from various file formats."""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.pdf':
        try:
            # Try normal text extraction first
            text = extract_text_from_pdf(file_path)
            
            # If minimal text is extracted, assume it's a scanned PDF
            if len(text.strip()) < 500:  # Adjust threshold as needed
                logger.info(f"Detected possible scanned PDF, using vision model for {file_path}")
                text = process_scanned_pdf(file_path)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            # Fallback to vision model
            return process_scanned_pdf(file_path)
    elif file_extension == '.txt':
        with open(file_path, 'r', encoding='utf-8') as file_obj:
            return file_obj.read()
    elif file_extension == '.docx':
        doc = docx.Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])

    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

def count_tokens(text):
    """Count tokens in a text string using tiktoken."""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text))

def determine_chunk_size(num_tokens):
    """Determine optimal chunk size based on document length."""
    if num_tokens < 30000:
        return 1000
    elif 30000 <= num_tokens <= 70000:
        return 3000
    else:
        return 7000

def process_document(file_path):
    """Process a document file and return chunks and embeddings."""
    # Extract text
    text = extract_text(file_path)
    
    # Count tokens
    num_tokens = count_tokens(text)
    
    # Determine chunk size
    chunk_size = determine_chunk_size(num_tokens)
    print("Made Chunk size")
    # Split text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=100
    )
    chunks = text_splitter.split_text(text)
    print("Have Chunks done")
    # Generate embeddings (Gemini)
    embeddings = get_gemini_embeddings(chunks, task_type="RETRIEVAL_DOCUMENT")
   
    
    return chunks, embeddings

def _slugify(value: str) -> str:
    cleaned = ''.join(c if c.isalnum() else '_' for c in value).lower()
    cleaned = cleaned.strip("_")
    return cleaned or "default"

def _weaviate_collection_name(name: str) -> str:
    # Weaviate class/collection names often appear with leading capital letter.
    return name[:1].upper() + name[1:] if name else name


def get_index_name_from_document(user_id, document_name, category: str | None = None):

    """Generate a valid Weaviate class name from user_id and document name."""
    # Remove file extension if present
    base_name = os.path.splitext(document_name)[0]
    # Create combined name
    doc_slug = _slugify(base_name)
    if category:
        cat_slug = _slugify(category)
        return _weaviate_collection_name(f"{cat_slug}__{doc_slug}")
    return _weaviate_collection_name(doc_slug)



def batch_import_objects(collection, objects: List[Dict[str, Any]], batch_size: int = 20):
    """
    Import objects using bulk operation with manual batching
    """
    failed_objects = []
    successful_count = 0
    
    try:
        # Process in chunks
        for i in range(0, len(objects), batch_size):
            chunk = objects[i:i + batch_size]
            
            # Prepare objects for insertion
            bulk_objects = []
            for obj in chunk:
                try:
                    # Create object without vector in properties
                    bulk_object = {
                        "properties": obj["properties"],
                        "vector": obj["vector"]
                    }
                    bulk_objects.append(bulk_object)
                    
                except Exception as e:
                    failed_objects.append({
                        "object": obj,
                        "error": str(e)
                    })
            
            try:
                # Insert objects one by one to better handle errors
                for obj in bulk_objects:
                    try:
                        collection.data.insert(
                            properties=obj["properties"],
                            vector=obj["vector"]
                        )
                        successful_count += 1
                    except Exception as e:
                        failed_objects.append({
                            "object": obj,
                            "error": str(e)
                        })
                        logger.error(f"Failed to insert object: {str(e)}")
                
                logger.info(f"Processed batch {i//batch_size + 1}, Size: {len(bulk_objects)}")
                
            except Exception as e:
                logger.error(f"Failed to import batch {i//batch_size + 1}: {str(e)}")
                failed_objects.extend(chunk)
                
    except Exception as e:
        logger.error(f"Bulk import operation failed: {str(e)}")
        failed_objects.extend(objects)
        
    finally:
        logger.info(f"Import completed. Success: {successful_count}, Failed: {len(failed_objects)}")
        
    return successful_count, failed_objects





def store_document_embeddings(user_id, document_name, chunks, embeddings, category: str | None = None):
    """Store document chunks and embeddings in Weaviate."""
    try:
        # Generate index name
        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        class_name = get_index_name_from_document(user_id, document_name, category=category)
        existing_class_names = load_class_names(class_names_file_path)
        existing_class_names.append({"class_name": class_name})
       
        # Save the updated list of class names back to the JSON file
        save_class_names(class_names_file_path, existing_class_names)

        print(f"Class name '{class_name}' stored in 'class_names.json' successfully.")
        # Get or create collection
        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        collection = get_or_create_weaviate_class(class_name)
        
        # Prepare objects for import
        objects_to_import = []
        for chunk, vector in zip(chunks, embeddings):
            objects_to_import.append({
                "properties": {
                    "text": chunk,
                    "full_text": chunk
                },
                "vector": vector
            })

        # Perform batch import
        successful_count, failed_objects = batch_import_objects(
            collection=collection,
            objects=objects_to_import,
            batch_size=20
        )
        
        return {
            'index_name': class_name,
            'total_chunks': len(chunks),
            'successful_chunks': successful_count,
            'failed_chunks': len(failed_objects),
            'failed_objects': failed_objects if failed_objects else None
        }
        
    except Exception as e:
        logger.error(f"Error storing document embeddings: {str(e)}")
        raise





# Function to load class names from the JSON file
def load_class_names(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as json_file:
                return json.load(json_file)
        except json.JSONDecodeError:
            # If the file is empty or corrupted, return an empty list
            return []
    return []

# Function to save class names to the JSON file
def save_class_names(file_path, class_names):
    with open(file_path, 'w') as json_file:
        json.dump(class_names, json_file, indent=4)


def get_all_documents():
    try:
        client_pool = WeaviateClientPool()
        class_names = client_pool.get_class_names_via_rest()
        return class_names if isinstance(class_names, list) else []
    except Exception as e:
        logger.error(f"Error getting all documents: {str(e)}")
        # Return an empty list so UI doesn't fail when Weaviate is down.
        return []



def delete_document_embeddings(user_id, document_name):
    """Delete all embeddings for a document."""
    try:
        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
       ## class_name = get_index_name_from_document(user_id, document_name)
        class_name = document_name

        # Check if collection exists
        if client.collections.exists(class_name):
            # Delete the collection
            client.collections.delete(class_name)
           
            logger.info(f"Deleted embeddings for document: {document_name}")
            return True
        else:
            logger.warning(f"No embeddings found for document: {document_name}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to delete embeddings: {str(e)}")
        raise 



def search_documents(user_id, document_name, query, limit=5, alpha=0.5):
    """Search documents using hybrid search with Weaviate."""
    try:
        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        
        # Frontend passes the Weaviate collection name (category__doc). Use it directly.
        class_name = document_name
        collection = client.collections.get(class_name)

        # Generate embedding for the query (Gemini)
        query_vector = get_gemini_embeddings(query, task_type="RETRIEVAL_QUERY")[0]

        # Execute hybrid search with both query text and vector
        response = collection.query.hybrid(
            query=query,                # For keyword search
            vector=query_vector,        # For vector search
            alpha=alpha,                # Balance between keyword and vector search
            limit=limit,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True)
        )

        # Transform results into response model
        results = [
            SearchResult(
                text=obj.properties.get("text", ""),
                full_text=obj.properties.get("full_text", ""),
                score=obj.metadata.score,
                document_name=document_name

            )
            for obj in response.objects
        ]
            
        return SearchResponse(
            results=results,
            total=len(results)
        )

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        # Return a properly formatted error response
        return SearchResponse(results=[], total=0)
    


def delete_class_names(file_path, class_name):
    class_names = load_class_names(file_path)
    filtered_names = [item for item in class_names if item.get('class_name') != class_name]
    
    with open(file_path, 'w') as file:
        json.dump(filtered_names, file, indent=4)


def generate_chat_response(conversation_context, document_context, query):
    """
    Generate a chat response.

    Retrieval stays the same (Weaviate + OpenAI embeddings). This function supports
    response generation via OpenAI (default) or Gemini (when configured).
    """
    provider = (os.getenv("CHAT_PROVIDER") or "openai").strip().lower()
    if provider == "gemini":
        return generate_chat_response_gemini(conversation_context, document_context, query)
    return generate_chat_response_openai(conversation_context, document_context, query)


def _build_chat_prompt(conversation_context, document_context, query) -> str:
    return f"""You are a helpful assistant for analyzing lease documents.
Follow these rules:
- Use ONLY the provided Document Context for factual claims.
- If the context does not contain the answer, say you cannot find it in the uploaded document.
- Be concise and legally accurate.

Previous Conversation History:
{conversation_context}

Document Context:
{document_context}

Current User Query: {query}
"""


def generate_chat_response_openai(conversation_context, document_context, query):
    """OpenAI provider disabled (project now uses Gemini)."""
    raise RuntimeError("OpenAI is disabled. Set CHAT_PROVIDER=gemini and provide GEMINI_API_KEY.")


def generate_chat_response_gemini(conversation_context, document_context, query):
    """Generate a chat response using Gemini (Google GenAI SDK)."""
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return "Gemini is selected but GEMINI_API_KEY is not set."

    prompt = _build_chat_prompt(conversation_context, document_context, query)
    model_id = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        try:
            client.close()
        except Exception:
            pass
        return (getattr(resp, "text", None) or "").strip() or "No response text returned from Gemini."
    except Exception as e:
        logger.error(f"Gemini chat generation failed: {e}")
        return "An error occurred while generating a response."

def chat_with_documents(user_id, document_name, query, limit=5, alpha=0.5):
    """Generate a chat response based on lease document context."""
    try:
        # Frontend passes the Weaviate collection name (category__doc). Use it directly.
        class_name = document_name
        history = get_conversation_history(class_name)

        conversation_context = "\n".join(
            [f"Q: {h[0]}\nA: {h[1]}" for h in history]
        )

        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        collection = client.collections.get(class_name)

        query_vector = get_gemini_embeddings(query, task_type="RETRIEVAL_QUERY")[0]
        search_results = collection.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True)
        )

        document_context = "\n\n".join(
            [f"Excerpt: {obj.properties.get('text', '')}" for obj in search_results.objects]
        )

        answer = generate_chat_response(conversation_context, document_context, query)

        store_conversation(class_name, query, answer)

        return ChatResponse(answer=answer)

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise


def chat_with_category(user_id, category: str, query: str, limit: int = 5, alpha: float = 0.5):
    """
    Category-wide RAG:
    - searches across ALL documents (Weaviate collections) that belong to the category
    - merges the top results and generates a single answer
    """
    try:
        cat_prefix = f"{category}".strip().lower().replace(" ", "_") + "__"
        scope_key = f"category::{cat_prefix.rstrip('_')}"

        history = get_conversation_history(scope_key)
        conversation_context = "\n".join([f"Q: {h[0]}\nA: {h[1]}" for h in history])

        all_docs = get_all_documents() or []
        if not isinstance(all_docs, list):
            all_docs = []
        collections = [d for d in all_docs if isinstance(d, str) and d.lower().startswith(cat_prefix)]
        if not collections:
            return ChatResponse(answer=f"No documents found for category '{category}'. Upload a document first.")

        client_pool = WeaviateClientPool()
        client = client_pool.get_client()

        query_vector = get_gemini_embeddings(query, task_type="RETRIEVAL_QUERY")[0]

        merged = []
        per_doc_limit = max(1, min(3, limit))
        for class_name in collections:
            try:
                collection = client.collections.get(class_name)
                res = collection.query.hybrid(
                    query=query,
                    vector=query_vector,
                    alpha=alpha,
                    limit=per_doc_limit,
                    fusion_type=HybridFusion.RELATIVE_SCORE,
                    return_metadata=MetadataQuery(score=True),
                )
                for obj in res.objects:
                    merged.append(
                        {
                            "document": class_name,
                            "text": obj.properties.get("text", "") if hasattr(obj, "properties") else "",
                            "score": getattr(getattr(obj, "metadata", None), "score", 0.0),
                        }
                    )
            except Exception as e:
                logger.warning(f"Category search failed for {class_name}: {e}")
                continue

        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        top = merged[: max(1, limit)]

        document_context = "\n\n".join(
            [f"Document: {item['document']}\nExcerpt: {item['text']}" for item in top if item.get("text")]
        )

        answer = generate_chat_response(conversation_context, document_context, query)
        store_conversation(scope_key, query, answer)
        return ChatResponse(answer=answer)
    except Exception as e:
        logger.error(f"Category chat failed: {e}")
        raise


def get_fixed_user_id():
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        return data.get("FIXED_USER_ID", "Default")  # Fallback to "Default" if key is missing
    except (FileNotFoundError, json.JSONDecodeError):
        return "Default"  # Fallback value if file is missing or corrupted




def get_gemini_embeddings(chunks, task_type: str = "RETRIEVAL_DOCUMENT"):
    """
    Create embeddings using Gemini.

    Returns: List[List[float]] aligned to input order.
    """
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for embeddings.")

    from google import genai
    from google.genai import types

    model_id = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    inputs = chunks if isinstance(chunks, list) else [chunks]

    client = genai.Client(api_key=api_key)
    try:
        resp = client.models.embed_content(
            model=model_id,
            contents=inputs,
            config=types.EmbedContentConfig(task_type=task_type),
        )

        vectors: List[List[float]] = []
        for emb in (getattr(resp, "embeddings", None) or []):
            values = getattr(emb, "values", None)
            if values is None and isinstance(emb, dict):
                values = emb.get("values")
            vectors.append(list(values or []))

        if len(vectors) != len(inputs):
            raise RuntimeError(f"Gemini returned {len(vectors)} embeddings for {len(inputs)} inputs.")
        return vectors
    finally:
        try:
            client.close()
        except Exception:
            pass
    



