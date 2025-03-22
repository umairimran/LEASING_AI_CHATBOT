import weaviate
from weaviate.classes import Property, DataType
from typing import List, Dict, Any
from threading import Lock
import logging
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants directly
WEAVIATE_HOST = "127.0.0.1"
WEAVIATE_PORT = 8081

# Update the WeaviateClientPool class
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
            try:
                self.client.close()
                logger.info("Weaviate client closed successfully")
            except Exception as e:
                logger.error(f"Error closing client: {str(e)}")
            finally:
                self.client = None




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