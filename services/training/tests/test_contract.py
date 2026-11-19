"""Ingest and training each compute the Qdrant id from a video_id.
If those two ever disagree, the trainer silently finds no vectors.
This pins the exact output so any drift fails the build."""

from app.data import qdrant_id


def test_qdrant_id_matches_ingest():
    assert qdrant_id("v000001") == "a1160b4f-bab8-5f21-8b7e-7625c5300653"
