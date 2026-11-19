"""
Tests for the CLIP path WITHOUT downloading CLIP.

FakeEncoder stands in for the real model: it maps a few known words to fixed
directions, the way CLIP maps related words to nearby vectors. That's enough
to test everything OUR code does (prompting, projection, caching,
determinism, shape) without a 600 MB download in CI.
"""

import numpy as np

from app.embedder import (
    CLIP_DIM, EMBED_DIM, ClipTextEmbedder, HashEmbedder, clean_title, describe,
)

WORD_DIRECTIONS = {}


def direction(word):
    if word not in WORD_DIRECTIONS:
        rng = np.random.default_rng(len(WORD_DIRECTIONS) + 100)
        WORD_DIRECTIONS[word] = rng.normal(size=CLIP_DIM)
    return WORD_DIRECTIONS[word]


class FakeEncoder:
    """'animal' words share a direction, like CLIP would place them."""
    calls = 0
    animal = {"kitten", "puppy", "cat", "pets", "parrot"}

    def encode(self, texts, normalize_embeddings=True):
        FakeEncoder.calls += 1
        out = []
        for text in texts:
            vector = np.zeros(CLIP_DIM)
            for word in text.lower().replace(":", " ").split():
                vector += direction("ANIMAL" if word in self.animal else word)
            out.append(vector / np.linalg.norm(vector))
        return np.array(out)


def test_title_cleanup_and_prompt():
    assert clean_title("Prank #795") == "Prank"
    assert clean_title("Code in 60s") == "Code in 60s"      # digits mid-title stay
    assert describe("pets", "Puppy zoomies #88") == "a pets video: Puppy zoomies"


def test_shape_unit_length_and_determinism():
    embedder = ClipTextEmbedder(encoder=FakeEncoder())
    first = embedder.embed("v1", "pets", "Puppy zoomies #1")
    again = ClipTextEmbedder(encoder=FakeEncoder()).embed("v1", "pets", "Puppy zoomies #1")
    assert first.shape == (EMBED_DIM,)
    assert abs(np.linalg.norm(first) - 1) < 1e-5
    assert np.allclose(first, again)          # a new process gives the same vector


def test_same_title_different_videos_stay_distinct_but_close():
    embedder = ClipTextEmbedder(encoder=FakeEncoder())
    a = embedder.embed("v1", "pets", "Puppy zoomies #1")
    b = embedder.embed("v2", "pets", "Puppy zoomies #2")
    assert not np.allclose(a, b)
    assert float(a @ b) > 0.95


def test_meaning_survives_the_projection():
    """A kitten video filed under MUSIC should sit closer to pets videos than
    to tech videos. The hash embedder can't do that; the CLIP path can."""
    clip = ClipTextEmbedder(encoder=FakeEncoder())
    kitten = clip.embed("new", "music", "Kitten plays piano")
    pets = clip.embed("p", "pets", "Cat vs cucumber")
    tech = clip.embed("t", "tech", "Gadget review")
    assert float(kitten @ pets) > float(kitten @ tech)

    hashed = HashEmbedder()
    h_kitten = hashed.embed("new", "music", "Kitten plays piano")
    h_pets = hashed.embed("p", "pets", "Cat vs cucumber")
    h_tech = hashed.embed("t", "tech", "Gadget review")
    # The fake embedder has no idea a kitten is an animal: pets and tech are equally far.
    assert abs(float(h_kitten @ h_pets) - float(h_kitten @ h_tech)) < 0.2


def test_repeated_descriptions_hit_the_cache():
    FakeEncoder.calls = 0
    embedder = ClipTextEmbedder(encoder=FakeEncoder())
    for i in range(50):
        embedder.embed(f"v{i}", "pets", f"Puppy zoomies #{i}")
    assert FakeEncoder.calls == 1             # 50 videos, one model call
