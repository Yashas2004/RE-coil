"""
The feature service: Kafka in, Postgres + Redis out.

The loop:
  1. poll up to BATCH_SIZE messages from Kafka
  2. parse them (skip junk)
  3. write to Postgres, then update Redis
  4. ONLY THEN commit the offsets back to Kafka

Step 4 is the important bit. The "offset" is Kafka's bookmark for our consumer
group: "feature-service has processed up to message #N in partition 2".
Committing after the work is done gives AT-LEAST-ONCE delivery: if we crash
between 3 and 4, we'll reprocess a few messages on restart, but we never lose any.
"""

import logging
import signal

import psycopg
import redis
from confluent_kafka import Consumer

from app import config
from app.events import parse_event
from app.realtime import record_events
from app.sink import write_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("feature")

running = True


def stop(signum, frame):
    # docker compose down sends SIGTERM. We finish the current batch, then exit.
    global running
    running = False


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    consumer = Consumer(
        {
            "bootstrap.servers": config.KAFKA_BROKERS,
            "group.id": config.KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest",   # brand-new group starts from the beginning
            "enable.auto.commit": False,       # we commit ourselves, after the work
        }
    )
    consumer.subscribe([config.KAFKA_TOPIC])

    db = psycopg.connect(config.POSTGRES_DSN)
    redis_client = redis.Redis.from_url(config.REDIS_URL)

    log.info("feature service consuming topic=%s group=%s", config.KAFKA_TOPIC, config.KAFKA_GROUP_ID)
    total = 0

    while running:
        messages = consumer.consume(num_messages=config.BATCH_SIZE, timeout=1.0)
        if not messages:
            continue

        events = []
        skipped = 0
        for message in messages:
            if message.error():
                log.warning("kafka error: %s", message.error())
                continue
            event = parse_event(message.value())
            if event is None:
                skipped += 1
                continue
            events.append(event)

        if events:
            inserted = write_events(db, events)
            record_events(redis_client, events)
            total += inserted
            log.info(
                "batch: %d events, %d stored, %d skipped (total stored %d)",
                len(events), inserted, skipped, total,
            )

        consumer.commit(asynchronous=False)

    log.info("shutting down")
    consumer.close()
    db.close()


if __name__ == "__main__":
    main()
