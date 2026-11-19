"""
Fast, short-lived state in Redis. Two jobs:

1. TRENDING. Each hour has two sorted sets (ZSETs: members with scores):
       trending:<hour>  how many times each video was WATCHED
       shown:<hour>     how many times each video was SHOWN
   Old hours expire on their own (TTL), so nothing ever needs cleaning up.

   The ranking itself lives in one more ZSET, trending:score, which holds
   each video's smoothed WATCH RATE over the current + previous hour.

   Why a rate and not a count? We used to rank by raw watch count. But the
   model shows comedy to comedy fans, so comedy piled up watches simply
   because it was SHOWN the most, and the trending list turned into a
   comedy list. A count measures exposure; a rate measures quality.

   Why "smoothed"? A video shown twice and watched twice has a 100% rate,
   which is luck, not quality. We pretend every video starts with
   PRIOR_WATCHES watches out of PRIOR_SHOWN views (a 20% rate, about the
   site average), so it needs real evidence to climb. This trick is called
   additive (Bayesian) smoothing.

2. SEEN. A short list per user of what they've recently been shown,
   so the feed can avoid serving the same video twice in a row.
"""

from datetime import datetime, timedelta, timezone

BUCKET_TTL_SECONDS = 3 * 60 * 60   # keep 3 hours of buckets
SEEN_LIMIT = 200                   # remember the last 200 videos per user
SEEN_TTL_SECONDS = 24 * 60 * 60

SCORE_KEY = "trending:score"
PRIOR_WATCHES = 2                  # smoothing: start every video at 2 watches...
PRIOR_SHOWN = 10                   # ...out of 10 views (20%)
MIN_SHOWN = 20                     # need this many views before it can trend


def bucket_key(moment: datetime) -> str:
    return "trending:" + moment.strftime("%Y%m%d%H")


def shown_key(moment: datetime) -> str:
    return "shown:" + moment.strftime("%Y%m%d%H")


def seen_key(user_id: str) -> str:
    return "seen:" + user_id


def smoothed_rate(watched: float, shown: float) -> float:
    return (watched + PRIOR_WATCHES) / (shown + PRIOR_SHOWN)


def record_events(redis_client, events: list[dict], now: datetime | None = None):
    # A pipeline sends all commands in one round trip instead of one per event.
    pipe = redis_client.pipeline()
    touched = set()

    for event in events:
        shown = shown_key(event["ts"])
        pipe.zincrby(shown, 1, event["video_id"])
        pipe.expire(shown, BUCKET_TTL_SECONDS)
        touched.add(event["video_id"])

        if event["watched"]:
            key = bucket_key(event["ts"])
            pipe.zincrby(key, 1, event["video_id"])
            pipe.expire(key, BUCKET_TTL_SECONDS)

        user_key = seen_key(event["user_id"])
        pipe.lpush(user_key, event["video_id"])
        pipe.ltrim(user_key, 0, SEEN_LIMIT - 1)
        pipe.expire(user_key, SEEN_TTL_SECONDS)

    pipe.execute()
    update_trending_scores(redis_client, touched, now)


def update_trending_scores(redis_client, video_ids: set, now: datetime | None = None):
    """Recompute the smoothed watch rate for every video this batch touched."""
    if not video_ids:
        return
    if now is None:
        now = datetime.now(timezone.utc)
    previous = now - timedelta(hours=1)
    keys = [bucket_key(now), bucket_key(previous), shown_key(now), shown_key(previous)]

    ordered = sorted(video_ids)
    pipe = redis_client.pipeline()
    for video_id in ordered:
        for key in keys:
            pipe.zscore(key, video_id)
    raw = pipe.execute()

    scores = {}
    too_new = []
    for i, video_id in enumerate(ordered):
        watched_now, watched_before, shown_now, shown_before = raw[i * 4:(i + 1) * 4]
        watched = (watched_now or 0) + (watched_before or 0)
        shown = (shown_now or 0) + (shown_before or 0)
        if shown < MIN_SHOWN:
            too_new.append(video_id)
        else:
            scores[video_id] = smoothed_rate(watched, shown)

    pipe = redis_client.pipeline()
    if scores:
        pipe.zadd(SCORE_KEY, scores)
    if too_new:
        pipe.zrem(SCORE_KEY, *too_new)
    pipe.expire(SCORE_KEY, BUCKET_TTL_SECONDS)
    pipe.execute()


def top_trending(redis_client, limit: int = 10):
    """[(video_id, smoothed watch rate), ...], best first."""
    rows = redis_client.zrevrange(SCORE_KEY, 0, limit - 1, withscores=True)
    result = []
    for video_id, score in rows:
        if isinstance(video_id, bytes):
            video_id = video_id.decode()
        result.append((video_id, score))
    return result
