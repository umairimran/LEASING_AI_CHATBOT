



if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # Enable auto-reload
            reload_dirs=["./"],  # Watch current directory for changes
            log_level="info"
        )
    finally:
        client_pool.close_client()


