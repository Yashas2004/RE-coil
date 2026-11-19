"""
Cold-start demo: can the system recommend a video NOBODY has watched yet?

Uploads one brand-new video, "Kitten plays piano", filed under MUSIC, then
asks the live model how likely each bot is to watch it, before a single
person has seen it. All the model has to go on is the video's embedding.

    docker compose run --rm sim-engine python -m app.coldstart
    docker compose run --rm -e COLD_TITLE="Guitar solo" sim-engine python -m app.coldstart

The second line is the CONTROL: same category (music), no animal in the
title. If pets fans score like everyone else there, then the bump for
"Kitten plays piano" came from the word "kitten", not from anything else.

What to look for:
  hash embedder -> only music fans score high. Pets fans look like everyone
                   else, because the fake embedder only sees the label "music".
  CLIP embedder -> pets fans ALSO score above average, because CLIP read the
                   word "kitten". That's content understanding solving cold start.
"""

import os
import re
import time

import httpx

from app import config
from app.bots import make_bots
from app.coverage import in_holdout

MODEL_URL = os.getenv("MODEL_URL", "http://model-server:8004")
TITLE = os.getenv("COLD_TITLE", "Kitten plays piano")
CATEGORY = "music"


def main():
    with httpx.Client(timeout=30) as client:
        health = client.get(config.INGEST_URL + "/health").json()
        embedder = health.get("embedder", "hash")
        slug = re.sub(r"[^a-z0-9]+", "_", TITLE.lower()).strip("_")
        video_id = f"v_cold_{embedder}_{slug}"    # one ID per embedder + title, so runs never mix

        client.post(config.INGEST_URL + "/videos", json={
            "video_id": video_id, "title": TITLE, "category": CATEGORY, "duration_s": 30,
        }).raise_for_status()
        print(f'uploaded "{TITLE}" as {video_id} (category={CATEGORY}, embedder={embedder})')

        # The model-server notices the new video on its next refresh (<= ~1 min).
        print("waiting for the model-server to index it", end="", flush=True)
        for _ in range(90):
            r = client.post(MODEL_URL + "/score", json={"user_id": "u000001", "video_ids": [video_id]})
            if r.status_code == 200 and r.json()["scores"]:
                break
            print(".", end="", flush=True)
            time.sleep(2)
        else:
            raise SystemExit("\nnever got indexed; is the model-server running?")
        print(" done\n")

        groups = {"likes music": [], "likes pets (not music)": [], "likes neither": []}
        for bot in make_bots(config.NUM_BOTS, config.SEED):
            if in_holdout(bot.user_id):
                continue
            r = client.post(MODEL_URL + "/score", json={"user_id": bot.user_id, "video_ids": [video_id]})
            p = r.json()["scores"][0]["p_watch"]
            if "music" in bot.likes:
                groups["likes music"].append(p)
            elif "pets" in bot.likes:
                groups["likes pets (not music)"].append(p)
            else:
                groups["likes neither"].append(p)

    print(f"predicted watch probability, before anyone has watched it ({embedder} embedder):")
    for name, values in groups.items():
        print(f"  {name:24s} {sum(values) / len(values):.2f}   ({len(values)} bots)")


if __name__ == "__main__":
    main()
