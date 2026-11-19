"""
A ModelBundle is everything needed to serve ONE model version:
  - the trained TwoTower network
  - the user vocabulary (user_id -> row in the embedding table)
  - every video's ITEM-TOWER vector, computed once up front

No network calls in here, so it's easy to test.

Cold start: a user the model never saw (signed up after training) has no
learned row. Instead of using a random vector, we give them the AVERAGE
taste of all known users. Average taste ~= "what's broadly popular".

Speed: everything that needs PyTorch happens ONCE, when the model loads.
Every user's tower vector and every video's tower vector are precomputed into
plain NumPy matrices. A request is then just a row lookup and one matrix
multiply: no PyTorch, no autograd, no thread pools fighting over the CPU.
(Measured: 106 ms -> a few ms p95 under 20 concurrent requests.)
"""

import numpy as np
import torch

from app.model import TwoTower


class ModelBundle:
    def __init__(self, checkpoint: dict):
        self.version = checkpoint["version"]
        self.user_vocab = checkpoint["user_vocab"]

        self.model = TwoTower(
            num_users=checkpoint["num_users"],
            content_dim=checkpoint["content_dim"],
        )
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()   # inference mode: no training behaviour

        # Every user's tower output, computed once. Row i = user index i.
        with torch.no_grad():
            all_rows = torch.arange(checkpoint["num_users"])
            self.user_matrix = self.model.user_vectors(all_rows).numpy()
        self.average_user = self._average_user_vector()

        # Filled by build_item_index().
        self.item_ids: list[str] = []
        self.item_matrix = np.zeros((0, 64), dtype=np.float32)
        self.item_row: dict[str, int] = {}

    def _average_user_vector(self) -> np.ndarray:
        known_rows = list(self.user_vocab.values())
        if not known_rows:
            known_rows = [0]
        return self.user_matrix[known_rows].mean(axis=0)

    def user_vector(self, user_id: str) -> np.ndarray:
        row = self.user_vocab.get(user_id)
        if row is None:
            return self.average_user
        return self.user_matrix[row]

    def is_known(self, user_id: str) -> bool:
        return user_id in self.user_vocab

    def build_item_index(self, video_ids: list[str], content: np.ndarray, batch_size: int = 1024):
        """Run every video's content vector through the item tower, once."""
        outputs = []
        with torch.no_grad():
            for start in range(0, len(video_ids), batch_size):
                batch = torch.tensor(content[start:start + batch_size], dtype=torch.float32)
                outputs.append(self.model.item_vectors(batch).numpy())

        if outputs:
            self.item_matrix = np.concatenate(outputs).astype(np.float32)
        self.item_ids = list(video_ids)
        self.item_row = {}
        for index, video_id in enumerate(self.item_ids):
            self.item_row[video_id] = index

    def score(self, user_id: str, video_ids: list[str]) -> list[tuple[str, float]]:
        """Watch probability for each requested video, highest first.
        Unknown videos are left out."""
        u = self.user_vector(user_id)

        known_ids = []
        rows = []
        for video_id in video_ids:
            row = self.item_row.get(video_id)
            if row is not None:
                known_ids.append(video_id)
                rows.append(row)
        if not rows:
            return []

        # One matrix multiply scores every video at once: (n x 64) @ (64,) -> (n,)
        logits = self.item_matrix[rows] @ u
        probabilities = 1.0 / (1.0 + np.exp(-logits))   # sigmoid, element-wise

        results = []
        for video_id, probability in zip(known_ids, probabilities):
            results.append((video_id, float(probability)))
        results.sort(key=lambda pair: pair[1], reverse=True)
        return results
