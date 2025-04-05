import os
import tempfile
import logging
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from Backend.models import SearchRequest, SearchResponse, ChatRequest, ChatResponse

from Backend.document_processor import chat_with_documents, delete_document_embeddings, get_all_documents, get_fixed_user_id, process_document, get_index_name_from_document, search_documents,store_document_embeddings

from Backend.database import get_conversation_history, delete_conversation_history

# Configure lo  gging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/test")
async def test_endpoint():
    return {"message": "API is working"}

@router.post("/upload-documents/")
async def upload_documents(
    files: List[UploadFile] = File(...),
    
):
    try:
        processed_files = []

        for file_obj in files:
            try:
                
                # Create a temporary file to store the uploaded content
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_obj.filename)[1]) as temp_file:
                    # Write uploaded file content to temporary file
                    content = await file_obj.read()
                    temp_file.write(content)
                    temp_file.flush()
                    temp_file.close() 
                    
                    try:
                        # Process document to get chunks and embeddings
                        print("Before embedding making")
                        chunks, embeddings = process_document(temp_file.name)
                     
                        # Store embeddings in Weaviate
                        result = store_document_embeddings(
                            
                            user_id=get_fixed_user_id(),
                            document_name=file_obj.filename,
                            chunks=chunks,
                            embeddings=embeddings
                        )
                        
                        processed_files.append({
                            'file_name': file_obj.filename,
                            **result
                        })

                    finally:
                        # Clean up the temporary file
                        os.unlink(temp_file.name)

            except Exception as e:
                logger.error(f"Error processing file {file_obj.filename}: {str(e)}")
                return {"error": str(e), "file": file_obj.filename}

        return {
            'message': 'Documents processed and stored successfully',
            'processed_files': processed_files
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}
    return {"message": "Documents uploaded successfully"}
  

@router.get("/get_all_documents")
async def get_all_documents_endpoint():  # Rename to avoid recursion
    try:
        documents = get_all_documents()  # Call the correct function
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error getting all documents: {str(e)}")
        return {"error": f"Error getting all documents: {str(e)}"}


@router.delete("/delete-embeddings")
async def delete_embeddings_endpoint(
    document_name: str = Form(...)
):
    try:
        user_id = get_fixed_user_id()
        class_name = get_index_name_from_document(user_id, document_name)
        
        # Delete the embeddings
        result = delete_document_embeddings(user_id, document_name)
        
        if result:
            # Also delete associated chat history
            delete_conversation_history(class_name)
            
            return {
                "message": f"Successfully deleted embeddings and chat history for document: {document_name}",
                "user_id": user_id,
                "document_name": document_name,
                "index_name": class_name
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No embeddings found for document: {document_name}"
            )
            
    except Exception as e:
        logger.error(f"Failed to delete embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    return search_documents(
        user_id=get_fixed_user_id(),
        document_name=request.document_name,
        query=request.query,
        limit=request.limit,
        alpha=request.alpha
    )



@router.post("/chat/")
async def chat_endpoint(
    document_name: str = Form(...),
    query: str = Form(...),
    limit: Optional[int] = Form(5),
    alpha: Optional[float] = Form(0.5)
):
    try:
        # Create a ChatRequest object
        print("here")
        request = ChatRequest(
            user_id=get_fixed_user_id(),
            document_name=document_name,
            query=query,
            limit=limit,
            alpha=alpha
        )
        print("here")
        # Process chat request
        response = chat_with_documents(
            user_id=get_fixed_user_id(),
            document_name=request.document_name,
            query=request.query,
            limit=request.limit,
            alpha=request.alpha
        )
        print("here 3")
        return response

    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))