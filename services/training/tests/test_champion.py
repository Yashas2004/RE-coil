"""
Champion vs. challenger, and the bug it fixes.

The bug: the live model's AUC was measured on EASY data (bots watching random
videos). Later models were measured on HARDER data (bots watching videos the
model already picked for them). Comparing those two numbers made every new
model look worse, so nothing got promoted and the loop froze.
"""

import random
import contextlib
import io

import numpy as np

from app.train import build_dataset, champion_auc, train_two_tower
from tests.test_learning import make_world


def quiet_train(dataset, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return train_two_tower(dataset, **kwargs)


def make_stream(policy, seed, num_events=20000, num_users=200, num_videos=500, num_categories=10):
    """One fixed world (videos, categories, hidden tastes: always seed 0) and a
    FRESH stream of events from it, shown by one of two policies:

        "random": videos picked at random, like the bots before any model existed
        "feed":   90% of videos picked from the user's liked categories, like a
                  good personalized feed

    Under "feed", most decisions are "liked video: watch or skip?", which is
    much harder to predict than "liked vs not liked"."""
    world = np.random.default_rng(0)
    centres = world.normal(size=(num_categories, 256))
    vectors, video_category = {}, {}
    by_category = {c: [] for c in range(num_categories)}
    for i in range(num_videos):
        category = int(world.integers(num_categories))
        vector = centres[category] / np.linalg.norm(centres[category]) + 0.02 * world.normal(size=256)
        vectors[f"v{i}"] = (vector / np.linalg.norm(vector)).astype(np.float32)
        video_category[f"v{i}"] = category
        by_category[category].append(f"v{i}")
    likes = {}
    for u in range(num_users):
        likes[f"u{u}"] = world.choice(num_categories, size=2, replace=False).tolist()

    rng = random.Random(seed)
    rows = []
    for _ in range(num_events):
        user_id = f"u{rng.randrange(num_users)}"
        if policy == "feed" and rng.random() < 0.9:
            video_id = rng.choice(by_category[rng.choice(likes[user_id])])
        else:
            video_id = f"v{rng.randrange(num_videos)}"
        liked = video_category[video_id] in likes[user_id]
        rows.append((user_id, video_id, rng.random() < (0.8 if liked else 0.1)))
    return rows, vectors


def test_champion_scored_on_own_data_matches_its_training_auc():
    rows, vectors = make_world()
    dataset = build_dataset(rows, vectors)
    model, val_auc = quiet_train(dataset, epochs=8)

    rescored = champion_auc(model, dataset["user_vocab"], dataset)
    assert abs(rescored - val_auc) < 1e-9


def test_unknown_users_map_to_index_zero():
    rows, vectors = make_world()
    dataset = build_dataset(rows, vectors)
    model, _ = quiet_train(dataset, epochs=1)

    # A champion that has never heard of any of these users must still score them.
    result = champion_auc(model, {}, dataset)
    assert 0.0 <= result <= 1.0


def test_auc_drops_on_harder_data_even_for_the_same_model():
    """The exact situation from the dashboard: one fixed model, two fresh test sets."""
    train_rows, vectors = make_stream("random", seed=1)
    champion, _ = quiet_train(build_dataset(train_rows, vectors), epochs=8)
    vocab = build_dataset(train_rows, vectors)["user_vocab"]

    easy_rows, _ = make_stream("random", seed=2)
    hard_rows, _ = make_stream("feed", seed=3)
    easy_auc = champion_auc(champion, vocab, build_dataset(easy_rows, vectors))
    hard_auc = champion_auc(champion, vocab, build_dataset(hard_rows, vectors))

    print(f"champion: {easy_auc:.3f} on random-feed data, {hard_auc:.3f} on personalized-feed data")
    # Same model, same weights, lower number. AUCs from different data can't be compared.
    assert hard_auc < easy_auc - 0.05
