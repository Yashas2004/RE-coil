import os

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
CONTENT_COLLECTION = os.getenv("CONTENT_COLLECTION", "videos")
# Each model version gets its own index: items_<version>. More on why in index.py.
INDEX_PREFIX = os.getenv("INDEX_PREFIX", "items_")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_BUCKET = os.getenv("S3_BUCKET", "models")

POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "15"))
