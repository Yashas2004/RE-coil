"""All settings come from environment variables, with defaults for local runs.
Inside docker compose, hosts are service names ("postgres", "qdrant")."""

import os

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN", "postgresql://recoil:recoil@localhost:5432/recoil"
)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "videos")
