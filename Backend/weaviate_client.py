import weaviate
import logging
from threading import Lock
from weaviate.classes.config import Property, DataType

# Configure logging
logger = logging.getLogger(__name__)

# Define constants
WEAVIATE_HOST = "weaviate"  # Use service name inside Docker
WEAVIATE_PORT = 8080


class WeaviateClientPool:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.client = None
        return cls._instance

    def get_client(self):
        if self.client is None or not self.client.is_ready():
            self.client = weaviate.connect_to_local(
                host=WEAVIATE_HOST,
                port=WEAVIATE_PORT,
                grpc_port=50051,
                skip_init_checks=True
            )
            if not self.client.is_ready():
                raise ConnectionError("Cannot connect to Weaviate")
            logger.info("Weaviate client connected successfully")
        return self.client

    def close_client(self):
        if self.client and self.client.is_ready():
            self.client.close()
            logger.info("Weaviate client closed successfully")
            self.client = None

def get_or_create_weaviate_class(class_name):
    """Create Weaviate schema class if it doesn't exist."""
    client_pool = WeaviateClientPool()
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