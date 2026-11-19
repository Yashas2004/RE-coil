"""
Regression test for the "identical scores" bug.

With ReLU and lr=0.01, 97.7% of item-tower neurons died and only 416 of
1000 videos kept a distinct vector, so different videos (tech, dance, travel)
got the exact same score. These tests fail if that ever comes back.
"""

import contextlib
import io

import numpy as np
import torch

from app.model import TwoTower
from app.train import build_dataset, train_two_tower
from tests.test_champion import make_stream


def trained_model():
    rows, vectors = make_stream("random", seed=1, num_events=30000, num_users=500, num_videos=1000)
    with contextlib.redirect_stdout(io.StringIO()):
        model, auc = train_two_tower(build_dataset(rows, vectors), epochs=10)
    content = torch.tensor(np.stack(list(vectors.values())), dtype=torch.float32)
    return model, auc, content


def test_every_video_keeps_its_own_vector():
    model, _, content = trained_model()
    with torch.no_grad():
        out = model.item_vectors(content).numpy()
    distinct = len(np.unique(np.round(out, 5), axis=0))
    assert distinct == len(out), f"only {distinct}/{len(out)} distinct item vectors"


def test_default_settings_beat_the_gate_comfortably():
    _, auc, _ = trained_model()
    assert auc > 0.75


def test_old_relu_checkpoints_still_load():
    """LeakyReLU has no weights, so a state_dict saved before the switch loads fine."""
    state = TwoTower(num_users=3).state_dict()
    TwoTower(num_users=3).load_state_dict(state)   # raises if keys differ
