import random

from app.bots import LIKED_WATCH_P, OTHER_WATCH_P, decide, make_bots
from app.catalog import CATEGORIES, make_catalog


def test_catalog_is_deterministic():
    assert make_catalog(50, seed=42) == make_catalog(50, seed=42)
    assert make_catalog(50, seed=42) != make_catalog(50, seed=7)


def test_catalog_ids_and_categories():
    catalog = make_catalog(1000, seed=42)
    assert catalog[0]["video_id"] == "v000000"
    assert catalog[999]["video_id"] == "v000999"
    for video in catalog:
        assert video["category"] in CATEGORIES


def test_every_bot_likes_two_categories():
    bots = make_bots(500, seed=42)
    assert bots[0].user_id == "u000000"
    for bot in bots:
        assert len(bot.likes) == 2


def test_bots_watch_liked_videos_far_more():
    bot = make_bots(1, seed=42)[0]
    liked_category = next(iter(bot.likes))
    other_category = next(c for c in CATEGORIES if c not in bot.likes)
    rng = random.Random(0)

    trials = 4000
    liked_watches = 0
    other_watches = 0
    for _ in range(trials):
        if decide(bot, {"category": liked_category, "duration_s": 20}, rng)[0]:
            liked_watches += 1
        if decide(bot, {"category": other_category, "duration_s": 20}, rng)[0]:
            other_watches += 1

    assert abs(liked_watches / trials - LIKED_WATCH_P) < 0.03
    assert abs(other_watches / trials - OTHER_WATCH_P) < 0.03


def test_watch_time_looks_realistic():
    bot = make_bots(1, seed=42)[0]
    liked = next(iter(bot.likes))
    rng = random.Random(1)
    for _ in range(200):
        watched, watch_ms = decide(bot, {"category": liked, "duration_s": 20}, rng)
        if watched:
            assert 12000 <= watch_ms <= 20000
        else:
            assert watch_ms <= 1500
