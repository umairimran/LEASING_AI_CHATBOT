import pypdf
import fitz
import base64
import tiktoken
import os
import docx
import textract
from groq import Groq
import logging

# Utility functions
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = pypdf.PdfReader(file)
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

# Update the extract_text function to handle scanned PDFs
def extract_text(file_path):
    # Get the original file extension by removing .copy if present
    if file_path.endswith('.copy'):
        file_path_for_ext = file_path[:-5]  # Remove .copy suffix
    else:
        file_path_for_ext = file_path
        
    file_extension = os.path.splitext(file_path_for_ext)[1].lower()
    
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
    elif file_extension == '.doc':
        return textract.process(file_path).decode('utf-8')
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text))

def determine_chunk_size(num_tokens):
    if num_tokens < 30000:
        return 1000
    elif 30000 <= num_tokens <= 70000:
        return 3000
    else:
        return 7000






def get_index_name_from_document(user_id: str, document_name: str) -> str:
    """
    Generate a valid Weaviate class name from user_id and document name.
    Example: document.pdf -> user_123_document
    """
    # Remove file extension if present
    base_name = os.path.splitext(document_name)[0]
    # Create collection name as the base name
    combined = f"{base_name}"
    cleaned = ''.join(c if c.isalnum() else '_' for c in combined).lower()
 
    with open("collection_names.txt", 'a') as file:  # 'a' mode allows appending to the file
        file.write(f"{document_name}: {cleaned}\n")     # Clean the name (only letters, numbers, and underscores allowed)
    return cleaned




def get_or_create_weaviate_class(class_name,client_pool):
    client = client_pool.get_client()
    try:
        if not client.collections.exists(class_name):
            collection = client.collections.create(
                name=class_name,
                vectorizer_config=None,  # We're using our own vectors
                properties=[
                    Property(
                        name="text",
                        data_type=DataType.TEXT
                    ),
                    Property(
                        name="full_text",
                        data_type=DataType.TEXT
                    )
                ]
            )
            logger.info(f"Created new schema class: {class_name}")
        else:
            collection = client.collections.get(class_name)
            logger.info(f"Schema class {class_name} already exists")
        return collection
    except Exception as e:
        logger.error(f"Error creating/checking collection: {str(e)}")
        raise