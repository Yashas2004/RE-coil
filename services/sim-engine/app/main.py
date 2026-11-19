"""
The simulation loop. WORKERS bots act at once; each round a worker:

  1. picks a random bot
  2. asks the feed for FEED_SIZE videos (or picks random ones if there's no feed yet)
  3. lets the bot watch or skip each one
  4. sends every decision to user-event, exactly like a phone app would

Every REPORT_EVERY_S seconds it prints the watch rate, split by which model
served the videos. "random" is the no-model baseline (~21%).
Watch that number climb once a trained model takes over.

asyncio lets one Python process juggle many bots at once: while one bot
waits for an HTTP reply, the others keep going.
"""

import asyncio
import random
import time
from collections import defaultdict

import httpx

from app import config
from app.bots import decide, make_bots
from app.catalog import make_catalog


class Stats:
    def __init__(self):
        self.shown = defaultdict(int)
        self.watched = defaultdict(int)
        self.errors = 0

    def add(self, model_version: str, watched: bool):
        self.shown[model_version] += 1
        if watched:
            self.watched[model_version] += 1

    def report_and_reset(self):
        parts = []
        for version in sorted(self.shown):
            rate = self.watched[version] / self.shown[version]
            parts.append(f"{version}: {rate:.1%} of {self.shown[version]}")
        line = " | ".join(parts) if parts else "no events yet"
        print(f"[sim] watch rate -> {line}  (errors: {self.errors})", flush=True)
        self.shown.clear()
        self.watched.clear()
        self.errors = 0


async def get_feed(client, bot, catalog_by_id, catalog, rng):
    """Returns (model_version, [video dicts]). Falls back to random videos."""
    try:
        response = await client.get(
            config.FEED_URL + "/feed",
            params={"user_id": bot.user_id, "limit": config.FEED_SIZE},
            timeout=2,
        )
        if response.status_code == 200:
            body = response.json()
            videos = []
            for item in body.get("items", []):
                video = catalog_by_id.get(item["video_id"])
                if video is not None:
                    videos.append(video)
            if videos:
                return body.get("model_version") or "unknown", videos
    except httpx.HTTPError:
        pass
    return "random", rng.sample(catalog, config.FEED_SIZE)


async def worker(client, bots, catalog, catalog_by_id, stats, seed):
    rng = random.Random(seed)
    while True:
        bot = rng.choice(bots)
        model_version, videos = await get_feed(client, bot, catalog_by_id, catalog, rng)

        sends = []
        for video in videos:
            watched, watch_ms = decide(bot, video, rng)
            stats.add(model_version, watched)
            event = {
                "user_id": bot.user_id,
                "video_id": video["video_id"],
                "watched": watched,
                "watch_ms": watch_ms,
                "model_version": model_version,
            }
            sends.append(client.post(config.EVENT_URL + "/event", json=event, timeout=2))

        results = await asyncio.gather(*sends, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) or result.status_code != 202:
                stats.errors += 1

        await asyncio.sleep(config.PAUSE_S)


async def reporter(stats):
    while True:
        await asyncio.sleep(config.REPORT_EVERY_S)
        stats.report_and_reset()


async def main():
    catalog = make_catalog(config.NUM_VIDEOS, config.SEED)
    catalog_by_id = {}
    for video in catalog:
        catalog_by_id[video["video_id"]] = video
    bots = make_bots(config.NUM_BOTS, config.SEED)
    stats = Stats()

    print(f"[sim] {len(bots)} bots, {len(catalog)} videos, {config.WORKERS} workers", flush=True)
    async with httpx.AsyncClient() as client:
        tasks = [asyncio.create_task(reporter(stats))]
        for i in range(config.WORKERS):
            tasks.append(asyncio.create_task(
                worker(client, bots, catalog, catalog_by_id, stats, seed=config.SEED + 100 + i)
            ))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
