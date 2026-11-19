"""
Fast, short-lived state in Redis. Two jobs:

1. TRENDING. Each hour has its own sorted set (a ZSET: members with scores).
   A watch adds +1 to that video's score in the current hour's set.
   "Trending now" = the current hour + the previous hour, added together.
   Old hours expire on their own (TTL), so nothing ever needs cleaning up.

2. SEEN. A short list per user of what they've recently been shown,
   so the feed can avoid serving the same video twice in a row.
"""

from datetime import datetime

BUCKET_TTL_SECONDS = 3 * 60 * 60   # keep 3 hours of buckets
SEEN_LIMIT = 200                   # remember the last 200 videos per user
SEEN_TTL_SECONDS = 24 * 60 * 60


def bucket_key(moment: datetime) -> str:
    return "trending:" + moment.strftime("%Y%m%d%H")


def seen_key(user_id: str) -> str:
    return "seen:" + user_id


def record_events(redis_client, events: list[dict]):
    # A pipeline sends all commands in one round trip instead of one per event.
    pipe = redis_client.pipeline()

    for event in events:
        if event["watched"]:
            key = bucket_key(event["ts"])
            pipe.zincrby(key, 1, event["video_id"])
            pipe.expire(key, BUCKET_TTL_SECONDS)

        user_key = seen_key(event["user_id"])
        pipe.lpush(user_key, event["video_id"])
        pipe.ltrim(user_key, 0, SEEN_LIMIT - 1)
        pipe.expire(user_key, SEEN_TTL_SECONDS)

    pipe.execute()


def top_trending(redis_client, now: datetime, previous: datetime, limit: int = 10):
    """Sum the current and previous hour, return [(video_id, score), ...]."""
    keys = [bucket_key(now), bucket_key(previous)]
    redis_client.zunionstore("trending:now", keys)
    rows = redis_client.zrevrange("trending:now", 0, limit - 1, withscores=True)

    result = []
    for video_id, score in rows:
        if isinstance(video_id, bytes):
            video_id = video_id.decode()
        result.append((video_id, score))
    return result
