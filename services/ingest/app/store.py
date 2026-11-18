"""
Writes a video to both places it needs to live:
  - Postgres: the facts (title, category, duration). Good for joins and history.
  - Qdrant:   the vector. Good for "find the N nearest videos to this vector".
"""

import uuid

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app import config
from app.embedder import EMBED_DIM


def qdrant_id(video_id: str) -> str:
    """Qdrant only accepts numbers or UUIDs as ids, so we derive a stable UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "recoil-video:" + video_id))


class Store:
    def __init__(self):
        self.db = psycopg.connect(config.POSTGRES_DSN, autocommit=True)
        self.qdrant = QdrantClient(url=config.QDRANT_URL)

    def ensure_collection(self):
        """Create the Qdrant collection once. Dot product, because our vectors
        are unit length, so dot product == cosine similarity."""
        if not self.qdrant.collection_exists(config.QDRANT_COLLECTION):
            self.qdrant.create_collection(
                collection_name=config.QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.DOT),
            )

    def save_video(self, video_id, title, category, duration_s, vector):
        # Upsert = insert, or update if it already exists. Makes re-running safe.
        self.db.execute(
            """
            INSERT INTO videos (video_id, title, category, duration_s)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE
               SET title = EXCLUDED.title,
                   category = EXCLUDED.category,
                   duration_s = EXCLUDED.duration_s
            """,
            (video_id, title, category, duration_s),
        )

        point = PointStruct(
            id=qdrant_id(video_id),
            vector=vector.tolist(),
            payload={"video_id": video_id, "category": category},
        )
        self.qdrant.upsert(collection_name=config.QDRANT_COLLECTION, points=[point])

    def count_videos(self) -> int:
        row = self.db.execute("SELECT count(*) FROM videos").fetchone()
        return row[0]
