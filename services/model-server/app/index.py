"""
Qdrant side of things.

The "videos" collection holds 256-d CONTENT vectors (from ingest).
A user's tower vector is 64-d and lives in a different space, so we can't
search "videos" with it. Instead, for each model version we build a second
collection, items_<version>, holding every video's 64-d ITEM-TOWER vector.

Why a new collection per version instead of overwriting one?
Because overwriting in place means that, for a few seconds, half the index
is from the old model and half from the new one: garbage results. Building
the new one on the side and then switching to it is an ATOMIC swap.
(This pattern is called blue/green.) We keep the previous one as a fallback.
"""

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchAny, MatchValue, PointStruct, VectorParams,
)

from app import config


def load_content_vectors(qdrant: QdrantClient):
    """Scroll through every video in the content collection, page by page."""
    ids = []
    video_ids = []
    categories = []
    vectors = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=config.CONTENT_COLLECTION,
            limit=512,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        for point in points:
            ids.append(point.id)
            video_ids.append(point.payload["video_id"])
            categories.append(point.payload.get("category"))
            vectors.append(point.vector)
        if offset is None:
            break
    return ids, video_ids, categories, np.array(vectors, dtype=np.float32)


def content_count(qdrant: QdrantClient) -> int:
    return qdrant.count(config.CONTENT_COLLECTION).count


def write_tower_index(qdrant: QdrantClient, version: str, ids, video_ids, categories, matrix):
    name = config.INDEX_PREFIX + version
    if qdrant.collection_exists(name):
        qdrant.delete_collection(name)
    qdrant.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=matrix.shape[1], distance=Distance.DOT),
    )

    batch = []
    for i in range(len(ids)):
        batch.append(PointStruct(
            id=ids[i],
            vector=matrix[i].tolist(),
            payload={"video_id": video_ids[i], "category": categories[i]},
        ))
        if len(batch) == 512:
            qdrant.upsert(collection_name=name, points=batch)
            batch = []
    if batch:
        qdrant.upsert(collection_name=name, points=batch)
    return name


def cleanup_old_indexes(qdrant: QdrantClient, keep: set[str]):
    for collection in qdrant.get_collections().collections:
        if collection.name.startswith(config.INDEX_PREFIX) and collection.name not in keep:
            qdrant.delete_collection(collection.name)


def search(qdrant: QdrantClient, index_name: str, user_vector, k: int, exclude: list[str],
           category: str | None = None):
    """Approximate nearest neighbours: the k videos whose tower vector has the
    biggest dot product with the user's vector. Optionally only within one category."""
    must = []
    must_not = []
    if category is not None:
        must.append(FieldCondition(key="category", match=MatchValue(value=category)))
    if exclude:
        must_not.append(FieldCondition(key="video_id", match=MatchAny(any=exclude)))
    query_filter = None
    if must or must_not:
        query_filter = Filter(must=must or None, must_not=must_not or None)
    result = qdrant.query_points(
        collection_name=index_name,
        query=list(map(float, user_vector)),
        limit=k,
        query_filter=query_filter,
        with_payload=True,
    )
    items = []
    for point in result.points:
        items.append({
            "video_id": point.payload["video_id"],
            "category": point.payload.get("category"),
            "score": point.score,
        })
    return items
