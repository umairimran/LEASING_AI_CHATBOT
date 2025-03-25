import asyncio
import logging
from fastapi import FastAPI
from routes import router
from database import init_db
from weaviate_client import WeaviateClientPool
from logger import setup_logging

# Setup logging
logger = setup_logging()
# Initialize client pool
client_pool = WeaviateClientPool()
# Create FastAPI app
app = FastAPI(
    title="Document Search and Chat API",
    description="API for document search and chat based on Weaviate",
    version="1.0.0"
)


# Include API routes
app.include_router(router)


# Initialize database on startup
@app.on_event("startup")

async def startup_event():
    try:
        init_db()
        logger.info("SQLite database initialized")
        
        client = client_pool.get_client()
        
        # Run sync check in separate thread to avoid blocking
        is_ready = await asyncio.to_thread(client.is_ready)
        
        if is_ready:
            logger.info("Successfully connected to Weaviate")
        else:
            logger.error("Cannot connect to Weaviate")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")

# Add cleanup on application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    try:
        client_pool.close_client()
        logger.info("Closed Weaviate client connection")
    except Exception as e:
        logger.error(f"Error closing Weaviate client: {str(e)}")

# Create a root endpoint for basic health check
@app.get("/")
async def root():
    return {"status": "ok", "message": "Document Search and Chat API is running"}

# Run the application if this file is executed directly
if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # Enable auto-reload
            reload_dirs=["."],  # Watch app directory for changes
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
    finally:
        client_pool.close_client() 