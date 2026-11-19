"""
Writes events into Postgres. This table is the training data.

Two foreign keys to respect:
  - users: we auto-register any user we haven't seen (ON CONFLICT DO NOTHING).
  - videos: an event for a video we don't know is useless for training,
    so the INSERT ... SELECT ... WHERE EXISTS quietly skips it.
"""

INSERT_USER = """
    INSERT INTO users (user_id) VALUES (%s)
    ON CONFLICT (user_id) DO NOTHING
"""

INSERT_INTERACTION = """
    INSERT INTO interactions (user_id, video_id, watched, watch_ms, model_version, created_at)
    SELECT %s, %s, %s, %s, %s, %s
    WHERE EXISTS (SELECT 1 FROM videos WHERE video_id = %s)
"""


def write_events(db, events: list[dict]) -> int:
    """Insert a batch inside one transaction. Returns how many rows landed."""
    user_ids = set()
    for event in events:
        user_ids.add(event["user_id"])

    inserted = 0
    with db.transaction():
        with db.cursor() as cur:
            for user_id in user_ids:
                cur.execute(INSERT_USER, (user_id,))

            for event in events:
                cur.execute(
                    INSERT_INTERACTION,
                    (
                        event["user_id"],
                        event["video_id"],
                        event["watched"],
                        event["watch_ms"],
                        event["model_version"],
                        event["ts"],
                        event["video_id"],
                    ),
                )
                inserted += cur.rowcount
    return inserted
