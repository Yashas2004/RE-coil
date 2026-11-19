from datetime import datetime, timezone

import fakeredis

from app.realtime import record_events, seen_key, top_trending

NOW = datetime(2026, 11, 19, 12, 30, tzinfo=timezone.utc)
HOUR_AGO = datetime(2026, 11, 19, 11, 30, tzinfo=timezone.utc)


def event(video_id, watched=True, user_id="u1", ts=NOW):
    return {"user_id": user_id, "video_id": video_id, "watched": watched, "ts": ts}


def test_trending_counts_watches_across_two_hours():
    r = fakeredis.FakeRedis()
    record_events(r, [
        event("v1"), event("v1"), event("v2"),
        event("v2", ts=HOUR_AGO), event("v2", ts=HOUR_AGO),
        event("v3", watched=False),          # skips don't count as trending
    ])

    top = top_trending(r, NOW, HOUR_AGO)
    assert top[0] == ("v2", 3.0)
    assert top[1] == ("v1", 2.0)
    assert len(top) == 2


def test_seen_list_is_newest_first():
    r = fakeredis.FakeRedis()
    record_events(r, [event("v1"), event("v2", watched=False)])
    seen = r.lrange(seen_key("u1"), 0, -1)
    assert seen == [b"v2", b"v1"]
