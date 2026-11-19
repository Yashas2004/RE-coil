"""/explore must return a video from a category the feed is NOT showing,
never one the user has already seen."""

import uuid

import numpy as np
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import app.main as server
from app import config
from app.bundle import ModelBundle
from app.index import load_content_vectors, write_tower_index
from tests.test_bundle import make_checkpoint

CATEGORIES = ["comedy", "music", "pets", "tech"]


def live_server():
    qdrant = QdrantClient(":memory:")
    qdrant.create_collection(config.CONTENT_COLLECTION,
                             vectors_config=VectorParams(size=256, distance=Distance.DOT))
    rng = np.random.default_rng(3)
    points = []
    for i in range(40):
        points.append(PointStruct(id=str(uuid.uuid4()), vector=rng.normal(size=256).tolist(),
                                  payload={"video_id": f"v{i}", "category": CATEGORIES[i % 4]}))
    qdrant.upsert(config.CONTENT_COLLECTION, points=points)

    ids, video_ids, categories, content = load_content_vectors(qdrant)
    bundle = ModelBundle(make_checkpoint())
    bundle.build_item_index(video_ids, content)
    name = write_tower_index(qdrant, bundle.version, ids, video_ids, categories, bundle.item_matrix)

    server.qdrant = qdrant
    server.current = server.Live(bundle, name, 0.8, len(video_ids), sorted(set(categories)))
    return TestClient(server.app)


def test_explore_avoids_categories_already_in_the_feed():
    client = live_server()
    for _ in range(20):
        r = client.post("/explore", json={"user_id": "alice", "avoid_categories": ["comedy", "music"]})
        assert r.status_code == 200
        assert r.json()["item"]["category"] in ("pets", "tech")


def test_explore_never_returns_seen_videos():
    client = live_server()
    seen = [f"v{i}" for i in range(40) if CATEGORIES[i % 4] == "pets"][:-1]   # all pets but one
    for _ in range(10):
        r = client.post("/explore", json={
            "user_id": "alice", "avoid_categories": ["comedy", "music", "tech"], "exclude": seen})
        assert r.json()["item"]["video_id"] not in seen


def test_explore_404_when_every_category_is_avoided():
    client = live_server()
    r = client.post("/explore", json={"user_id": "alice", "avoid_categories": CATEGORIES})
    assert r.status_code == 404
