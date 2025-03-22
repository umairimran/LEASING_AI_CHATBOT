from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import UploadFile, File, Form
from typing import List
import os
import tempfile
from functions import *
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter

from Vector_Database import *
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app=FastAPI()

# Initialize client pool
client_pool = WeaviateClientPool()


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    try:
        client_pool.get_client()
    except Exception as e:
        logger.error(f"Failed ot initilaiz startup up: {e}")
        


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")
    try:
        client_pool.close_client()
        logger.info("Resources cleaned up successfully")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {str(e)}")


@app.get("/test")
async def test():
    return {"message": "API is working fine"}

@app.post("/upload-documents/")
async def upload_documents(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...)
):

    try:
        client = client_pool.get_client()
        processed_files = []

        for file_obj in files:
            temp_file_path = None
            try:
                # Generate a unique temporary file name but don't create it yet
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_obj.filename)[1]) as temp_file:
                    temp_file_path = temp_file.name
           
                # Write uploaded file content to temporary file
                content = await file_obj.read()
                # Write in a separate context to ensure file handle is released
                with open(temp_file_path, 'wb') as f:
                    f.write(content)
                                               
                # Generate index name from document name
                class_name = get_index_name_from_document(user_id, file_obj.filename)
                  
                # Ensure schema exists
                collection = get_or_create_weaviate_class(class_name,client)

                # Make a copy to process to avoid file locking issues
                process_file_path = temp_file_path + ".copy"
                with open(temp_file_path, 'rb') as src, open(process_file_path, 'wb') as dst:
                    dst.write(src.read())
                
                try:
                    # Process text using the copy file path
                    text = extract_text(process_file_path)
                    num_tokens = count_tokens(text)
                    chunk_size = determine_chunk_size(num_tokens)

                    # Split text
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size,
                        chunk_overlap=100
                    )
                    texts = text_splitter.split_text(text)

                    # Generate embeddings
                    vectors = embeddings_model.encode(texts).tolist()

                    # Prepare objects for import
                    objects_to_import = []
                    for chunk, vec in zip(texts, vectors):
                        objects_to_import.append({
                            "properties": {
                                "text": chunk,
                                "full_text": chunk
                            },
                            "vector": vec
                        })

                    # Perform batch import
                    successful_count, failed_objects = batch_import_objects(
                        collection=collection,
                        objects=objects_to_import,
                        batch_size=20
                    )

                    processed_files.append({
                        'file_name': file_obj.filename,
                        'index_name': class_name,
                        'total_chunks': len(texts),
                        'successful_chunks': successful_count,
                        'failed_chunks': len(failed_objects),
                        'failed_objects': failed_objects if failed_objects else None
                    })

                finally:
                    # Clean up the copy file
                    try:
                        if os.path.exists(process_file_path):
                            os.unlink(process_file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete copy file {process_file_path}: {str(e)}")

            except Exception as e:
                logger.error(f"Error processing file {file_obj.filename}: {str(e)}")
                processed_files.append({
                    'file_name': file_obj.filename,
                    'error': str(e),
                    'status': 'failed'
                })
            finally:
                # Clean up the temporary file
                try:
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {str(e)}")

        return {
            'message': 'Documents processed and stored successfully',
            'processed_files': processed_files
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}
    


