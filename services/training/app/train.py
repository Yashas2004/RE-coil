"""
Pure training logic: arrays in, (model, AUC) out. No databases here,
which is what makes it easy to test.

The dataset is a dict:
    user_idx : int array  (N,)      which user
    content  : float array (N, 256) the video's content vector
    labels   : 0/1 array  (N,)      1 = watched, 0 = skipped
    num_users: int                  size of the user vocabulary (incl. index 0)
"""

import numpy as np
import torch
from torch import nn

from app.metrics import auc
from app.model import TwoTower


def time_split(n: int, val_fraction: float = 0.2) -> tuple[slice, slice]:
    """Rows are sorted oldest -> newest. Train on the past, validate on the most
    recent slice. A random split would let the model peek at the 'future',
    which makes the AUC look better than it really is (this is called leakage)."""
    cut = int(n * (1 - val_fraction))
    return slice(0, cut), slice(cut, n)


def train_two_tower(dataset: dict, epochs: int = 5, batch_size: int = 256,
                    lr: float = 3e-3, seed: int = 0) -> tuple[TwoTower, float]:
    torch.manual_seed(seed)

    users = torch.tensor(dataset["user_idx"], dtype=torch.long)
    content = torch.tensor(dataset["content"], dtype=torch.float32)
    labels = torch.tensor(dataset["labels"], dtype=torch.float32)

    train_part, val_part = time_split(len(labels))

    model = TwoTower(num_users=dataset["num_users"], content_dim=content.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    # Binary cross-entropy on raw logits. It punishes confident wrong answers hard.
    loss_fn = nn.BCEWithLogitsLoss()

    train_users = users[train_part]
    train_content = content[train_part]
    train_labels = labels[train_part]
    num_train = len(train_labels)

    for epoch in range(epochs):
        model.train()
        order = torch.randperm(num_train)  # shuffle each epoch
        total_loss = 0.0

        for start in range(0, num_train, batch_size):
            batch = order[start:start + batch_size]

            logits = model(train_users[batch], train_content[batch])
            loss = loss_fn(logits, train_labels[batch])

            optimizer.zero_grad()   # clear old gradients
            loss.backward()         # compute new gradients
            optimizer.step()        # nudge weights downhill

            total_loss += loss.item() * len(batch)

        print(f"epoch {epoch + 1}/{epochs}  loss={total_loss / num_train:.4f}")

    model.eval()
    with torch.no_grad():
        val_scores = model(users[val_part], content[val_part])

    val_auc = auc(labels[val_part].int().tolist(), val_scores.tolist())
    return model, val_auc


def model_from_checkpoint(checkpoint: dict) -> tuple[TwoTower, dict]:
    model = TwoTower(num_users=checkpoint["num_users"], content_dim=checkpoint["content_dim"])
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint["user_vocab"]


def champion_auc(champion: TwoTower, champion_vocab: dict, dataset: dict) -> float:
    """Score the CURRENTLY LIVE model on the challenger's validation slice.

    AUC only means something relative to the data it was measured on. As the
    model gets better, the feed shows users more of what they like, and the
    remaining "watch or skip?" decisions get harder. So a newer model measured
    on newer data can look worse than an old model measured on easy old data,
    even when it's actually better. Comparing both on the SAME rows is the only
    fair test. This is called champion vs. challenger.

    The two models number their users differently, so we translate each row's
    user back to its user_id, then into the champion's numbering (0 = unknown).
    """
    _, val_part = time_split(len(dataset["labels"]))

    index_to_user = {}
    for user_id, index in dataset["user_vocab"].items():
        index_to_user[index] = user_id

    champion_users = []
    for index in dataset["user_idx"][val_part]:
        user_id = index_to_user[int(index)]
        champion_users.append(champion_vocab.get(user_id, 0))

    with torch.no_grad():
        scores = champion(
            torch.tensor(champion_users, dtype=torch.long),
            torch.tensor(dataset["content"][val_part], dtype=torch.float32),
        )
    return auc(dataset["labels"][val_part].tolist(), scores.tolist())


def build_dataset(rows: list[tuple], vectors: dict[str, np.ndarray]) -> dict:
    """rows: (user_id, video_id, watched), oldest first.
    vectors: video_id -> content vector. Rows for videos with no vector are dropped."""
    user_vocab = {}
    user_idx = []
    content = []
    labels = []

    for user_id, video_id, watched in rows:
        vector = vectors.get(video_id)
        if vector is None:
            continue
        if user_id not in user_vocab:
            user_vocab[user_id] = len(user_vocab) + 1   # 0 is reserved for unknown
        user_idx.append(user_vocab[user_id])
        content.append(vector)
        labels.append(1 if watched else 0)

    return {
        "user_idx": np.array(user_idx, dtype=np.int64),
        "content": np.array(content, dtype=np.float32),
        "labels": np.array(labels, dtype=np.int64),
        "num_users": len(user_vocab) + 1,
        "user_vocab": user_vocab,
    }
