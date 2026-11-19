"""
The fake video catalog. Same SEED -> exactly the same 1000 videos every time,
so the seed script and the bots always agree on what exists.
"""

import random

CATEGORIES = [
    "comedy", "dance", "food", "gaming", "music",
    "pets", "sports", "tech", "travel", "fashion",
]

TITLE_WORDS = {
    "comedy": ["Prank", "Stand-up bit", "Sketch", "Fail compilation"],
    "dance": ["Choreo", "Dance challenge", "Freestyle", "Tutorial"],
    "food": ["Street food", "Recipe", "Taste test", "Mukbang"],
    "gaming": ["Speedrun", "Clutch moment", "Boss fight", "Build guide"],
    "music": ["Cover", "Beat making", "Live loop", "Guitar riff"],
    "pets": ["Cat vs cucumber", "Puppy zoomies", "Parrot talks", "Hamster maze"],
    "sports": ["Trick shot", "Highlights", "Workout", "Skate line"],
    "tech": ["Unboxing", "Setup tour", "Code in 60s", "Gadget review"],
    "travel": ["Hidden beach", "City walk", "Night market", "Mountain hike"],
    "fashion": ["Fit check", "Thrift haul", "Get ready with me", "Styling tips"],
}


def video_id(index: int) -> str:
    return f"v{index:06d}"


def make_catalog(num_videos: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    catalog = []
    for index in range(num_videos):
        category = rng.choice(CATEGORIES)
        title = rng.choice(TITLE_WORDS[category]) + " #" + str(index)
        catalog.append({
            "video_id": video_id(index),
            "title": title,
            "category": category,
            "duration_s": rng.randint(8, 60),
        })
    return catalog
