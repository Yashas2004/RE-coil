"""
The bots: 500 simulated users, each with HIDDEN tastes.

Each bot secretly loves 2 categories and is lukewarm on everything else.
The recommender never gets told these tastes. It has to discover them from
watch/skip behaviour alone. That's the whole test: if the model learns,
the bots' watch rate goes up.

    liked category    -> watches ~75% of the time
    anything else     -> watches ~8% of the time

So a RANDOM feed gets about 0.2*0.75 + 0.8*0.08 ~= 21% watch rate,
and a PERFECT feed (only liked categories) gets ~75%.
Where the real model lands between those two is your scoreboard.
"""

import random
from dataclasses import dataclass

from app.catalog import CATEGORIES

LIKED_WATCH_P = 0.75
OTHER_WATCH_P = 0.08


@dataclass
class Bot:
    user_id: str
    likes: set[str]


def make_bots(num_bots: int, seed: int) -> list[Bot]:
    rng = random.Random(seed + 1)   # different stream from the catalog
    bots = []
    for index in range(num_bots):
        likes = set(rng.sample(CATEGORIES, 2))
        bots.append(Bot(user_id=f"u{index:06d}", likes=likes))
    return bots


def decide(bot: Bot, video: dict, rng: random.Random) -> tuple[bool, int]:
    """Does this bot watch this video, and for how long (ms)?"""
    if video["category"] in bot.likes:
        p_watch = LIKED_WATCH_P
    else:
        p_watch = OTHER_WATCH_P

    duration_ms = video.get("duration_s", 30) * 1000

    if rng.random() < p_watch:
        # Watchers stay for most of the video.
        return True, int(duration_ms * rng.uniform(0.6, 1.0))
    # Skippers swipe away within the first second or so.
    return False, rng.randint(200, 1500)
