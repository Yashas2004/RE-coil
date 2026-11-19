"""
The most important test in the repo: does the model actually LEARN?

We invent a tiny world where the truth is known: each user secretly likes
2 of 10 categories. They watch liked-category videos 80% of the time and
others 10% of the time. If the two-tower model can't discover that
pattern and clear the 0.65 AUC gate, something is broken.
"""

import numpy as np

from app.train import build_dataset, train_two_tower

NUM_CATEGORIES = 10
NUM_USERS = 200
NUM_VIDEOS = 500
NUM_EVENTS = 20000


def make_world(seed=0):
    rng = np.random.default_rng(seed)

    centres = rng.normal(size=(NUM_CATEGORIES, 256))
    for i in range(NUM_CATEGORIES):
        centres[i] = centres[i] / np.linalg.norm(centres[i])

    vectors = {}
    video_category = {}
    for i in range(NUM_VIDEOS):
        video_id = f"v{i}"
        category = int(rng.integers(NUM_CATEGORIES))
        vector = centres[category] + 0.35 * rng.normal(size=256) / 16
        vectors[video_id] = (vector / np.linalg.norm(vector)).astype(np.float32)
        video_category[video_id] = category

    likes = {}
    for u in range(NUM_USERS):
        likes[f"u{u}"] = set(rng.choice(NUM_CATEGORIES, size=2, replace=False).tolist())

    rows = []
    for _ in range(NUM_EVENTS):
        user_id = f"u{int(rng.integers(NUM_USERS))}"
        video_id = f"v{int(rng.integers(NUM_VIDEOS))}"
        liked = video_category[video_id] in likes[user_id]
        watch_probability = 0.8 if liked else 0.1
        watched = rng.random() < watch_probability
        rows.append((user_id, video_id, watched))

    return rows, vectors


def test_model_learns_hidden_tastes():
    rows, vectors = make_world()
    dataset = build_dataset(rows, vectors)

    model, val_auc = train_two_tower(dataset, epochs=8)

    print("validation AUC:", val_auc)
    assert val_auc > 0.65


def test_build_dataset_reserves_index_zero():
    rows = [("a", "v1", True), ("b", "v1", False), ("a", "missing", True)]
    vectors = {"v1": np.zeros(256, dtype=np.float32)}
    dataset = build_dataset(rows, vectors)

    assert dataset["user_vocab"] == {"a": 1, "b": 2}
    assert dataset["num_users"] == 3
    assert len(dataset["labels"]) == 2   # the row with no vector was dropped
