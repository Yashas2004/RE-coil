"""Runs the real Qdrant code against Qdrant's in-memory mode: no server needed."""

import uuid

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app import config
from app.index import cleanup_old_indexes, load_content_vectors, search, write_tower_index
from tests.test_bundle import make_checkpoint
from app.bundle import ModelBundle


def seeded_qdrant(num_videos=20):
    qdrant = QdrantClient(":memory:")
    qdrant.create_collection(
        config.CONTENT_COLLECTION,
        vectors_config=VectorParams(size=256, distance=Distance.DOT),
    )
    rng = np.random.default_rng(1)
    points = []
    for i in range(num_videos):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=rng.normal(size=256).tolist(),
            payload={"video_id": f"v{i}", "category": "pets"},
        ))
    qdrant.upsert(config.CONTENT_COLLECTION, points=points)
    return qdrant


def test_index_build_and_search_with_exclusions():
    qdrant = seeded_qdrant()
    ids, video_ids, categories, content = load_content_vectors(qdrant)
    assert len(video_ids) == 20

    bundle = ModelBundle(make_checkpoint())
    bundle.build_item_index(video_ids, content)
    name = write_tower_index(qdrant, bundle.version, ids, video_ids, categories, bundle.item_matrix)

    user_vector = bundle.user_vector("alice")
    top = search(qdrant, name, user_vector, k=5, exclude=[])
    assert len(top) == 5

    # Retrieval order must agree with the bundle's own scores.
    scored = bundle.score("alice", video_ids)
    assert top[0]["video_id"] == scored[0][0]

    # Excluded (already seen) videos never come back.
    seen = [top[0]["video_id"], top[1]["video_id"]]
    again = search(qdrant, name, user_vector, k=5, exclude=seen)
    for item in again:
        assert item["video_id"] not in seen


def test_cleanup_keeps_only_requested_indexes():
    qdrant = seeded_qdrant(3)
    ids, video_ids, categories, content = load_content_vectors(qdrant)
    bundle = ModelBundle(make_checkpoint())
    bundle.build_item_index(video_ids, content)
    for version in ["v1", "v2", "v3"]:
        write_tower_index(qdrant, version, ids, video_ids, categories, bundle.item_matrix)

    cleanup_old_indexes(qdrant, keep={"items_v2", "items_v3"})
    names = set()
    for collection in qdrant.get_collections().collections:
        names.add(collection.name)
    assert names == {config.CONTENT_COLLECTION, "items_v2", "items_v3"}
