"""
Taste coverage: has the model discovered BOTH of each bot's hidden tastes?

Two questions, because they have different answers:

1. KNOWS: score every video for the bot, average the scores per category, and
   check whether the bot's two liked categories are the model's top-2.
   This is what the model has LEARNED about the person.

2. SHOWS: look at the bot's top-10 retrieval candidates and check which liked
   categories appear. Videos in one category have similar vectors, so a
   top-10 is often all one category even when the model knows both tastes.
   The feed's category caps and exploration exist to close exactly this gap.

Control-group bots (the A/B holdout) never get model feeds, so they're left out.
We can only compute any of this because the bots' true tastes are known.

    docker compose run --rm sim-engine python -m app.coverage
"""

import os

import httpx

from app import config
from app.bots import make_bots
from app.catalog import make_catalog

MODEL_URL = os.getenv("MODEL_URL", "http://model-server:8004")
HOLDOUT_PCT = int(os.getenv("HOLDOUT_PCT", "10"))
TOP_K = 10


def fnv32a(text: str) -> int:
    """Same hash as feed-api/holdout.go, so we agree on who is in control."""
    value = 0x811C9DC5
    for byte in text.encode():
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value


def in_holdout(user_id: str) -> bool:
    return fnv32a(user_id) % 100 < HOLDOUT_PCT


def bucket(found: int) -> str:
    if found == 2:
        return "both"
    if found == 1:
        return "one"
    return "none"


def top_two_categories(scores: list[dict], category_of: dict) -> set:
    totals = {}
    counts = {}
    for row in scores:
        category = category_of[row["video_id"]]
        totals[category] = totals.get(category, 0.0) + row["p_watch"]
        counts[category] = counts.get(category, 0) + 1
    averages = []
    for category in totals:
        averages.append((totals[category] / counts[category], category))
    averages.sort(reverse=True)
    return {averages[0][1], averages[1][1]}


def main():
    catalog = make_catalog(config.NUM_VIDEOS, config.SEED)
    category_of = {}
    all_ids = []
    for video in catalog:
        category_of[video["video_id"]] = video["category"]
        all_ids.append(video["video_id"])

    bots = [bot for bot in make_bots(config.NUM_BOTS, config.SEED) if not in_holdout(bot.user_id)]
    knows = {"both": 0, "one": 0, "none": 0}
    shows = {"both": 0, "one": 0, "none": 0}
    version = None

    with httpx.Client(timeout=30) as client:
        for bot in bots:
            scored = client.post(MODEL_URL + "/score", json={"user_id": bot.user_id, "video_ids": all_ids})
            retrieved = client.post(MODEL_URL + "/candidates", json={"user_id": bot.user_id, "k": TOP_K})
            for response in (scored, retrieved):
                if response.status_code != 200:
                    raise SystemExit(f"model-server said {response.status_code}: {response.text}")
            version = scored.json()["model_version"]

            top_two = top_two_categories(scored.json()["scores"], category_of)
            knows[bucket(len(top_two & bot.likes))] += 1

            shown = set()
            for item in retrieved.json()["items"]:
                if item["category"] in bot.likes:
                    shown.add(item["category"])
            shows[bucket(len(shown))] += 1

    total = len(bots)
    print(f"model {version}, {total} model-group bots (control group excluded)\n")
    print(f"  {'':22s}{'KNOWS (top-2 categories)':>26s}{'SHOWS (top-' + str(TOP_K) + ' retrieval)':>26s}")
    for key, label in [("both", "both tastes"), ("one", "only one taste"), ("none", "neither")]:
        print(f"  {label:22s}{knows[key]:>12d} ({knows[key] / total:6.1%})  {shows[key]:>12d} ({shows[key] / total:6.1%})")


if __name__ == "__main__":
    main()
