import numpy as np
import torch

from app.bundle import ModelBundle
from app.model import TwoTower


def make_checkpoint():
    torch.manual_seed(0)
    model = TwoTower(num_users=3, content_dim=256)
    return {
        "state_dict": model.state_dict(),
        "user_vocab": {"alice": 1, "bob": 2},
        "num_users": 3,
        "content_dim": 256,
        "version": "vtest",
    }


def make_bundle():
    bundle = ModelBundle(make_checkpoint())
    rng = np.random.default_rng(0)
    content = rng.normal(size=(5, 256)).astype(np.float32)
    bundle.build_item_index(["v0", "v1", "v2", "v3", "v4"], content)
    return bundle


def test_item_index_shape():
    bundle = make_bundle()
    assert bundle.item_matrix.shape == (5, 64)
    assert bundle.item_row["v3"] == 3


def test_unknown_user_gets_average_taste():
    bundle = make_bundle()
    alice = bundle.user_vector("alice")
    bob = bundle.user_vector("bob")
    stranger = bundle.user_vector("never-seen")
    assert np.allclose(stranger, (alice + bob) / 2, atol=1e-6)
    assert bundle.is_known("alice")
    assert not bundle.is_known("never-seen")


def test_score_is_sorted_probabilities_and_skips_unknown_videos():
    bundle = make_bundle()
    scores = bundle.score("alice", ["v0", "v1", "v2", "nope"])
    assert len(scores) == 3
    probabilities = [p for _, p in scores]
    assert probabilities == sorted(probabilities, reverse=True)
    for p in probabilities:
        assert 0.0 < p < 1.0


def test_score_matches_model_forward():
    """Serving must give the SAME number training would. This is the
    train/serve consistency check."""
    bundle = make_bundle()
    rng = np.random.default_rng(0)
    content = rng.normal(size=(5, 256)).astype(np.float32)
    with torch.no_grad():
        logit = bundle.model(torch.tensor([1]), torch.tensor(content[2:3]))[0].item()
    expected = 1 / (1 + np.exp(-logit))
    served = dict(bundle.score("alice", ["v2"]))["v2"]
    assert abs(served - expected) < 1e-5
