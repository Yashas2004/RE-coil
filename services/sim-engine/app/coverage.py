"""
Taste coverage: has the model discovered BOTH of each bot's hidden tastes?

For every bot we ask the model-server for its top-10 retrieval candidates and
check which of the bot's two liked categories appear there.

    both  -> the model knows the whole person
    one   -> the model found one taste and is stuck on it (the filter bubble:
             u000000 got all comedy, never music)
    none  -> the model knows nothing useful about them

We can compute this ONLY because the bots' tastes are known. With real users
you'd never have the answer key: one more thing simulation buys you.

    docker compose run --rm sim-engine python -m app.coverage
"""

import os

import httpx

from app import config
from app.bots import make_bots

MODEL_URL = os.getenv("MODEL_URL", "http://model-server:8004")
TOP_K = 10


def main():
    bots = make_bots(config.NUM_BOTS, config.SEED)
    counts = {"both": 0, "one": 0, "none": 0}
    version = None

    with httpx.Client(timeout=10) as client:
        for bot in bots:
            response = client.post(
                MODEL_URL + "/candidates", json={"user_id": bot.user_id, "k": TOP_K}
            )
            if response.status_code != 200:
                raise SystemExit(f"model-server said {response.status_code}: {response.text}")
            body = response.json()
            version = body["model_version"]

            found = set()
            for item in body["items"]:
                if item["category"] in bot.likes:
                    found.add(item["category"])

            if len(found) == 2:
                counts["both"] += 1
            elif len(found) == 1:
                counts["one"] += 1
            else:
                counts["none"] += 1

    total = len(bots)
    print(f"model {version}, top-{TOP_K} retrieval for {total} bots:")
    for key, label in [("both", "both tastes found"), ("one", "stuck on one taste"), ("none", "neither found")]:
        print(f"  {label:20s} {counts[key]:4d}  ({counts[key] / total:.1%})")


if __name__ == "__main__":
    main()
