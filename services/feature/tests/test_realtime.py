from datetime import datetime, timezone

import fakeredis

from app.realtime import record_events, seen_key, smoothed_rate, top_trending

NOW = datetime(2026, 11, 19, 12, 30, tzinfo=timezone.utc)
HOUR_AGO = datetime(2026, 11, 19, 11, 30, tzinfo=timezone.utc)


def event(video_id, watched=True, user_id="u1", ts=NOW):
    return {"user_id": user_id, "video_id": video_id, "watched": watched, "ts": ts}


def shown(video_id, times, watched, ts=NOW):
    """`times` impressions of a video, the first `watched` of them watched."""
    events = []
    for i in range(times):
        events.append(event(video_id, watched=i < watched, user_id=f"u{i}", ts=ts))
    return events


def test_rate_beats_raw_exposure():
    """The bug this fixes: 'comedy' was shown 1000 times by the model and got
    250 watches. 'gem' was shown 100 times and watched 60. Ranking by count
    puts comedy first; ranking by rate correctly puts the gem first."""
    r = fakeredis.FakeRedis()
    record_events(r, shown("comedy", 1000, 250) + shown("gem", 100, 60), now=NOW)

    top = top_trending(r)
    assert top[0][0] == "gem"
    assert top[1][0] == "comedy"


def test_smoothing_stops_lucky_newcomers():
    r = fakeredis.FakeRedis()
    record_events(r, shown("lucky", 3, 3) + shown("steady", 200, 80), now=NOW)

    names = [video_id for video_id, _ in top_trending(r)]
    assert "lucky" not in names          # 3 views < MIN_SHOWN: not trending yet
    assert names == ["steady"]
    assert abs(smoothed_rate(3, 3) - 5 / 13) < 1e-9   # and even then, far below 100%


def test_counts_current_and_previous_hour():
    r = fakeredis.FakeRedis()
    record_events(r, shown("v", 20, 10, ts=HOUR_AGO) + shown("v", 20, 10, ts=NOW), now=NOW)
    (video_id, score), = top_trending(r)
    assert abs(score - smoothed_rate(20, 40)) < 1e-9


def test_seen_list_is_newest_first():
    r = fakeredis.FakeRedis()
    record_events(r, [event("v1"), event("v2", watched=False)], now=NOW)
    seen = r.lrange(seen_key("u1"), 0, -1)
    assert seen == [b"v2", b"v1"]
