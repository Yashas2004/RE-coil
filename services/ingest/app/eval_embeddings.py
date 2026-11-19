"""
Compare the two embedders on the real catalogue: does CLIP actually understand
anything the hash embedder doesn't?

    docker compose exec ingest python -m app.eval_embeddings

1. Category accuracy: put each video in the category whose average vector
   it's closest to. Both should do well; it's a sanity check that CLIP
   still separates categories after projection to 256 numbers.

2. Neighbours of NEW titles the catalogue has never seen. This is the real
   test of "understanding": the hash embedder can only look at the category
   label; CLIP also reads the title.
"""

import numpy as np
import psycopg

from app import config
from app.embedder import ClipTextEmbedder, HashEmbedder

PROBES = [
    ("music", "Kitten plays piano"),       # a music video that is really about a pet
    ("food", "Cooking with my dog"),       # food, but pets fans should care
    ("travel", "Street food tour in Bangkok"),
    ("sports", "Esports finals highlights"),
]


def load_catalogue():
    with psycopg.connect(config.POSTGRES_DSN) as db:
        return db.execute("SELECT video_id, category, title FROM videos ORDER BY video_id").fetchall()


def category_accuracy(vectors, categories):
    centres = {}
    for category in set(categories):
        rows = [v for v, c in zip(vectors, categories) if c == category]
        centres[category] = np.mean(rows, axis=0)
    correct = 0
    for vector, category in zip(vectors, categories):
        best = max(centres, key=lambda c: float(vector @ centres[c]))
        correct += best == category
    return correct / len(vectors)


def main():
    catalogue = load_catalogue()
    categories = [row[1] for row in catalogue]
    print(f"{len(catalogue)} videos in the catalogue\n")

    for embedder in (HashEmbedder(), ClipTextEmbedder()):
        vectors = np.array([embedder.embed(vid, cat, title) for vid, cat, title in catalogue])
        print(f"=== {embedder.name} ===")
        print(f"category accuracy (nearest centre): {category_accuracy(vectors, categories):.1%}")
        for category, title in PROBES:
            probe = embedder.embed("probe", category, title)
            scores = vectors @ probe
            top = np.argsort(-scores)[:5]
            found = [f"{catalogue[i][1]}:{catalogue[i][2]}" for i in top]
            print(f'  "{title}" ({category}) -> ' + " | ".join(found))
        print()


if __name__ == "__main__":
    main()
