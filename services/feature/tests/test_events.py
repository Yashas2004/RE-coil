import json

from app.events import parse_event, parse_timestamp


def make(**fields):
    base = {"user_id": "u1", "video_id": "v1", "watched": True, "watch_ms": 4200}
    base.update(fields)
    return json.dumps(base).encode()


def test_valid_event():
    event = parse_event(make())
    assert event["user_id"] == "u1"
    assert event["watched"] is True
    assert event["model_version"] is None


def test_rejects_garbage():
    assert parse_event(b"not json") is None
    assert parse_event(b"[1, 2, 3]") is None
    assert parse_event(make(user_id="")) is None
    assert parse_event(make(watch_ms=-5)) is None


def test_go_nanosecond_timestamp():
    moment = parse_timestamp("2026-11-18T19:05:39.209199844Z")
    assert moment.year == 2026
    assert moment.microsecond == 209199
    assert moment.utcoffset().total_seconds() == 0
