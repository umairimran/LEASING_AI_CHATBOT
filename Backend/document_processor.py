import os
import tempfile
import logging
from typing import Any, Dict, List
import PyPDF2
import json
import openai
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

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")
open_ai_client = openai.OpenAI()
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
    """Extract images from PDF pages and convert them to base64."""
    images = []
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            
            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            images.append(image_base64)
    
    pdf_document.close()
    return images

def process_scanned_pdf(pdf_path):
    """Process scanned PDF using Groq's vision model."""
    images = extract_images_from_pdf(pdf_path)
    extracted_text = []
    
    for image_base64 in images:
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please extract and transcribe all the text visible in this image."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=1,
                max_completion_tokens=1024,
                top_p=1,
                stream=False,
                stop=None
            )
            
            extracted_text.append(completion.choices[0].message.content)
            logger.info(f"Successfully processed image with Groq")
            
        except Exception as e:
            logger.error(f"Error processing image with Groq: {str(e)}")
            continue
    
    return " ".join(extracted_text)

def extract_text(file_path):
    """Extract text from various file formats."""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.pdf':
        try:
            # Try normal text extraction first
            text = extract_text_from_pdf(file_path)
            
            # If minimal text is extracted, assume it's a scanned PDF
            if len(text.strip()) < 100:  # Adjust threshold as needed
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
    # Generate embeddings
    client_pool = WeaviateClientPool()
    client = client_pool.get_client()

    embeddings = get_openai_embeddings(chunks)
   
    
    return chunks, embeddings

def get_index_name_from_document(user_id, document_name):
    
    """Generate a valid Weaviate class name from user_id and document name."""
    # Remove file extension if present
    base_name = os.path.splitext(document_name)[0]
    # Create combined name
    combined = f"{base_name}"
    # Clean the name (only letters, numbers, and underscores allowed)
    cleaned = ''.join(c if c.isalnum() else '_' for c in combined).lower()
    return cleaned 



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





def store_document_embeddings(user_id, document_name, chunks, embeddings):
    """Store document chunks and embeddings in Weaviate."""
    try:
        # Generate index name
        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        class_name = get_index_name_from_document(user_id, document_name)
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
    
        class_names = load_class_names(class_names_file_path)
        class_names_list = [item['class_name'] for item in class_names][::-1]  # Reverse the list
        return class_names_list
    except Exception as e:
        logger.error(f"Error getting all documents: {str(e)}")
        return {"error": f"Error getting all documents: {str(e)}"}





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
            delete_class_names(class_names_file_path, class_name)
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
        
        # Generate index name from document name
        class_name = get_index_name_from_document(user_id, document_name)
        collection = client.collections.get(class_name)

        # Generate embedding for the query using SentenceTransformer
        query_vector =get_openai_embeddings(query)
        query_vector = query_vector[0]

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
    """Generate a chat response using OpenAI's GPT-4o-mini model."""
    messages = [
        {"role": "system", "content": (
            "You are an AI assistant specialized in legal documents. "
            "Answer questions based strictly on the provided context. "
            "If the document lacks the necessary information, explicitly state that."
            "You are a legal assistant, so you should answer questions based the document."
            "You should maintain a professional and respectful tone in your responses."
            "You should use very good simple and profession language"
            "Analyze carefull content and provide a good answer"
        )},
        {"role": "user", "content": f"""Previous Conversation History:
{conversation_context}

Document Context:
{document_context}

Current User Query: {query}

Provide a concise, legally accurate answer based on the context above."""}
    ]

    try:
        response = open_ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4,
            max_tokens=1024,
            top_p=0.95
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        return "An error occurred while generating a response."

def chat_with_documents(user_id, document_name, query, limit=5, alpha=0.5):
    """Generate a chat response based on lease document context."""
    try:
        class_name = get_index_name_from_document(user_id, document_name)
        history = get_conversation_history(class_name)

        conversation_context = "\n".join(
            [f"Q: {h[0]}\nA: {h[1]}" for h in history]
        )

        client_pool = WeaviateClientPool()
        client = client_pool.get_client()
        collection = client.collections.get(class_name)

        query_vector = get_openai_embeddings(query)[0]
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


def get_fixed_user_id():
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        return data.get("FIXED_USER_ID", "Default")  # Fallback to "Default" if key is missing
    except (FileNotFoundError, json.JSONDecodeError):
        return "Default"  # Fallback value if file is missing or corrupted




def get_openai_embeddings(chunks):
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "text-embedding-3-small",
        "input": chunks if isinstance(chunks, list) else [chunks],  # Ensures list format
        "encoding_format": "float"
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return [item["embedding"] for item in response.json()["data"]]
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None  # Handle failure properly
    
