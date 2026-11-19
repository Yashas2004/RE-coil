"""
Turns a video into a 256-number vector (an "embedding").

Two embedders, same output shape, so nothing downstream ever notices which
one is running (EMBEDDER=clip or EMBEDDER=hash):

1. ClipTextEmbedder (default in Docker). A real pretrained model: OpenAI's
   CLIP (ViT-B/32), via sentence-transformers. CLIP was trained on 400M
   image/caption pairs, so its text side "understands" content: "Puppy
   zoomies" lands near "Cat vs cucumber" and far from "Code in 60s",
   without us ever telling it what a pet is.

   What we embed: "a <category> video: <title>". Our catalogue has no real
   frames or audio, only metadata, so this uses CLIP's TEXT encoder. A real
   system would embed video frames with CLIP's IMAGE encoder (same vector
   space) and audio with Whisper, then combine them. That would replace
   only this file.

   CLIP outputs 512 numbers; we keep the rest of the system at 256 with a
   fixed random projection. Multiplying by a random Gaussian matrix keeps
   distances between vectors roughly intact (the Johnson-Lindenstrauss
   lemma), and the seed never changes, so the same text always gets the
   same vector.

2. HashEmbedder (the original fake). Each category gets a fixed random
   "centre" and each video lands near it. No understanding at all: "Kitten
   plays piano" filed under music is exactly as far from pets as from tech.
   Kept as the baseline for comparisons, and for tests that must not
   download a 600 MB model.

Both are DETERMINISTIC: the same video always gets the same vector, which
is what keeps training and serving from drifting apart.
"""

import hashlib
import os
import re
from functools import lru_cache

import numpy as np

EMBED_DIM = 256
CLIP_DIM = 512
CLIP_MODEL = "clip-ViT-B-32"
# Videos sharing a title still differ in their frames and audio. We only have
# text, so a small fixed per-video offset stands in for that difference.
PER_VIDEO_JITTER = 0.08

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
    return vector / np.linalg.norm(vector)


def _unit_noise(seed_text: str, size: int) -> np.ndarray:
    rng = np.random.default_rng(_seed_from_text(seed_text))
    return _normalize(rng.normal(size=size))


# ---------------------------------------------------------------- the fake one

class HashEmbedder:
    name = "hash"

    def embed(self, video_id: str, category: str, title: str = "", noise: float = 0.35) -> np.ndarray:
        centre = _unit_noise("category:" + category, EMBED_DIM)
        nudge = _unit_noise("video:" + video_id, EMBED_DIM)
        return _normalize(centre + noise * nudge).astype(np.float32)


# ---------------------------------------------------------------- the real one

def clean_title(title: str) -> str:
    """'Prank #795' -> 'Prank'. The number is our catalogue's ID, not content."""
    return re.sub(r"\s*#\d+\s*$", "", title).strip()


def describe(category: str, title: str) -> str:
    return f"a {category} video: {clean_title(title)}"


class ClipTextEmbedder:
    name = "clip"

    def __init__(self, encoder=None):
        if encoder is None:
            # Imported here, not at the top, so tests and the hash embedder
            # never need torch or the model weights.
            from sentence_transformers import SentenceTransformer
            encoder = SentenceTransformer(CLIP_MODEL, device="cpu")
        self.encoder = encoder

        rng = np.random.default_rng(_seed_from_text("projection:clip-512-to-256"))
        self.projection = rng.normal(size=(CLIP_DIM, EMBED_DIM)) / np.sqrt(EMBED_DIM)

        # Many videos share a description ("a pets video: Puppy zoomies"), so
        # remember each one: 1000 videos -> ~40 actual model calls.
        self._encode_text = lru_cache(maxsize=4096)(self._encode_uncached)

    def _encode_uncached(self, text: str) -> tuple:
        vector = self.encoder.encode([text], normalize_embeddings=True)[0]
        return tuple(float(x) for x in vector)

    def embed(self, video_id: str, category: str, title: str = "") -> np.ndarray:
        base = np.array(self._encode_text(describe(category, title)))
        projected = _normalize(base @ self.projection)
        jitter = _unit_noise("video:" + video_id, EMBED_DIM)
        return _normalize(projected + PER_VIDEO_JITTER * jitter).astype(np.float32)


# ---------------------------------------------------------------- picking one

_active = None


def get_embedder():
    """Created once per process (loading CLIP takes a few seconds)."""
    global _active
    if _active is None:
        if os.getenv("EMBEDDER", "hash") == "clip":
            _active = ClipTextEmbedder()
        else:
            _active = HashEmbedder()
    return _active


def embed_video(video_id: str, category: str, title: str = "") -> np.ndarray:
    return get_embedder().embed(video_id, category, title)
