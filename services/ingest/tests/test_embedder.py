import numpy as np

from app.embedder import EMBED_DIM, embed_video


def test_shape_and_unit_length():
    vector = embed_video("v1", "pets")
    assert vector.shape == (EMBED_DIM,)
    assert abs(np.linalg.norm(vector) - 1.0) < 1e-5


def test_deterministic():
    first = embed_video("v1", "pets")
    second = embed_video("v1", "pets")
    assert np.allclose(first, second)


def test_same_category_is_closer_than_different_category():
    pets_a = embed_video("a", "pets")
    pets_b = embed_video("b", "pets")
    tech_c = embed_video("c", "tech")

    # Dot product of unit vectors = cosine similarity (1 = same direction).
    similarity_same = float(np.dot(pets_a, pets_b))
    similarity_diff = float(np.dot(pets_a, tech_c))
    assert similarity_same > similarity_diff
