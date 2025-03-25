# Document Chat API Backend

A FastAPI-based backend service that provides API endpoints for document upload and chat functionality. THis will do the chatbot integration with api that is running at backend on local host it will be deployed allowing use to chat with tier uploaded doucments related to the leases

## Features

- **Document Upload API**: Upload and process documents
- **Document Management API**: Retrieve document information
- **Chat API**: Process chat messages and generate responses
- **Health Check API**: Monitor the API status

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the backend server    :
```bash    
python app.py     
```

2. The API will be available at http://localhost:8000

## API Endpoints

### Health Check
```
GET /api/status
```

### Document Upload
```
POST /api/documents/upload
```

### Document Retrieval
```
GET /api/documents
GET /api/documents/{doc_id}

```
        
### Chat
```
POST /api/chat
```                                     

## Integration with Frontend

The frontend application is    configured to connect to this backend API automatically. By default, it will look for the API at `http://localhost:8000`.

You can modify the backend URL used by the frontend by setting the `BACKEND_URL` environment variable before starting the frontend application.     