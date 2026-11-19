"""
The two-tower model (same idea as YouTube's retrieval model, Yi et al. 2019).

    user_id ──► [embedding table] ──► [user tower MLP] ──► u  (64 numbers)
                                                              \
                                                               dot product ──► score
                                                              /
    video's content vector (256) ──► [item tower MLP] ──► v  (64 numbers)

score = u · v. High score = "this user will probably watch this video".

Why two separate towers instead of one big network that sees both?
Because the towers never mix until the very last step, we can compute every
video's v ONCE, store them in a vector database, and at request time just
compute the user's u and ask "which v's have the biggest dot product with u?".
That's how you search millions of videos in milliseconds.

User index 0 is reserved for "unknown user" (someone who signed up after the
model was trained). They get a generic, average-ish taste vector.
"""

import torch
from torch import nn

UNKNOWN_USER = 0


class TwoTower(nn.Module):
    def __init__(self, num_users: int, content_dim: int = 256, user_dim: int = 32, out_dim: int = 64):
        super().__init__()
        # One learnable row of `user_dim` numbers per user: their "taste".
        self.user_embedding = nn.Embedding(num_users, user_dim)

        self.user_tower = nn.Sequential(
            nn.Linear(user_dim, 128),
            nn.ReLU(),
            nn.Linear(128, out_dim),
        )
        self.item_tower = nn.Sequential(
            nn.Linear(content_dim, 128),
            nn.ReLU(),
            nn.Linear(128, out_dim),
        )

    def user_vectors(self, user_idx: torch.Tensor) -> torch.Tensor:
        return self.user_tower(self.user_embedding(user_idx))

    def item_vectors(self, content: torch.Tensor) -> torch.Tensor:
        return self.item_tower(content)

    def forward(self, user_idx: torch.Tensor, content: torch.Tensor) -> torch.Tensor:
        u = self.user_vectors(user_idx)
        v = self.item_vectors(content)
        # Row-by-row dot product. These are "logits": raw scores, not probabilities.
        # sigmoid(logit) would turn them into a 0..1 watch probability.
        return (u * v).sum(dim=1)
