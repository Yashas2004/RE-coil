"""
Loading training data from the real system.

Labels come from Postgres. Content vectors come from Qdrant: the exact same
vectors the feed will use at serving time. One source of truth means training
and serving can't drift apart.
"""

import uuid

import numpy as np

from app import config


def qdrant_id(video_id: str) -> str:
    """MUST match services/ingest/app/store.py exactly, or we'd look up the wrong
    points. tests/test_contract.py pins the expected output so a change breaks loudly."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "recoil-video:" + video_id))


def load_interactions(db, limit: int) -> list[tuple]:
    """Most recent `limit` rows, returned oldest-first."""
    rows = db.execute(
        """
        SELECT user_id, video_id, watched
        FROM (
            SELECT user_id, video_id, watched, created_at, id
            FROM interactions
            ORDER BY created_at DESC, id DESC
            LIMIT %s
        ) recent
        ORDER BY created_at ASC, id ASC
        """,
        (limit,),
    ).fetchall()
    return rows


def count_interactions(db) -> int:
    return db.execute("SELECT count(*) FROM interactions").fetchone()[0]


def fetch_item_vectors(qdrant, video_ids: set[str]) -> dict[str, np.ndarray]:
    ids = []
    for video_id in video_ids:
        ids.append(qdrant_id(video_id))

    vectors = {}
    chunk = 256
    for start in range(0, len(ids), chunk):
        points = qdrant.retrieve(
            collection_name=config.QDRANT_COLLECTION,
            ids=ids[start:start + chunk],
            with_vectors=True,
            with_payload=True,
        )
        for point in points:
            video_id = point.payload["video_id"]
            vectors[video_id] = np.array(point.vector, dtype=np.float32)
    return vectors
