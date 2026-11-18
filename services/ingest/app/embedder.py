"""
Turns a video into a 256-number vector (an "embedding").

For now this is a FAKE embedder: it doesn't look at pixels or audio.
Instead, every category gets a fixed random "centre" point in 256-D space,
and each video is placed near its category's centre plus a bit of noise.

Why fake first?
  - It gives us real structure to learn from (pets videos really ARE close
    to other pets videos), so the whole pipeline can be built and tested
    without downloading multi-GB CLIP/Whisper models.
  - In Phase 11 we swap this file for real CLIP + Whisper. Nothing else changes,
    because every other service only ever sees "a 256-number vector".

Key property: it is DETERMINISTIC. The same video always gets the same vector,
no matter when or where it's computed. That's what stops training and
serving from drifting apart.
"""

import hashlib

import numpy as np

EMBED_DIM = 256

CATEGORIES = [
    "comedy", "dance", "food", "gaming", "music",
    "pets", "sports", "tech", "travel", "fashion",
]


def _seed_from_text(text: str) -> int:
    """Turn any string into a stable integer seed (same text -> same seed, forever)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _normalize(vector: np.ndarray) -> np.ndarray:
    """Scale a vector to length 1, so only its direction matters."""
    length = np.linalg.norm(vector)
    return vector / length


def category_centre(category: str) -> np.ndarray:
    rng = np.random.default_rng(_seed_from_text("category:" + category))
    return _normalize(rng.normal(size=EMBED_DIM))


def embed_video(video_id: str, category: str, noise: float = 0.35) -> np.ndarray:
    """Place the video near its category centre, nudged by video-specific noise."""
    centre = category_centre(category)

    rng = np.random.default_rng(_seed_from_text("video:" + video_id))
    nudge = _normalize(rng.normal(size=EMBED_DIM))

    vector = centre + noise * nudge
    return _normalize(vector).astype(np.float32)
