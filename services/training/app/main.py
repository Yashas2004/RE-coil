"""
The trainer loop. Every TRAIN_INTERVAL_S seconds:

    enough new interactions since last run?
        no  -> sleep
        yes -> load data -> train -> measure AUC on the newest 20%
               -> save model to S3 (always)
               -> passes the gate? point latest.json at it (promote)
               -> log the run in Postgres (promoted or not)

Nobody presses a button. That's the "self-improving" part.
"""

import logging
import signal
import time
from datetime import datetime, timezone

import psycopg
from qdrant_client import QdrantClient

from app import config
from app.data import count_interactions, fetch_item_vectors, load_interactions
from app.registry import (
    ensure_bucket, get_latest, last_trained_count, promote, record_run,
    s3_client, save_model, should_promote,
)
from app.train import build_dataset, train_two_tower

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("training")

running = True


def stop(signum, frame):
    global running
    running = False


def run_once(db, qdrant, s3, total_rows: int):
    started_at = datetime.now(timezone.utc)
    version = "v" + started_at.strftime("%Y%m%d%H%M%S")

    rows = load_interactions(db, config.MAX_SAMPLES)
    video_ids = set()
    for user_id, video_id, watched in rows:
        video_ids.add(video_id)
    vectors = fetch_item_vectors(qdrant, video_ids)

    dataset = build_dataset(rows, vectors)
    log.info("training %s on %d samples, %d users", version, len(dataset["labels"]), dataset["num_users"])

    model, val_auc = train_two_tower(dataset, epochs=config.EPOCHS)
    key = save_model(s3, model, dataset["user_vocab"], version, dataset["content"].shape[1])

    current = get_latest(s3)
    promoted = should_promote(val_auc, current)
    if promoted:
        promote(s3, version, key, val_auc)

    record_run(db, version, total_rows, val_auc, promoted, key, started_at, datetime.now(timezone.utc))
    log.info("%s auc=%.4f gate=%.2f -> %s", version, val_auc, config.AUC_GATE,
             "PROMOTED" if promoted else "rejected")


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    db = psycopg.connect(config.POSTGRES_DSN, autocommit=True)
    qdrant = QdrantClient(url=config.QDRANT_URL)
    s3 = s3_client()
    ensure_bucket(s3)

    last_count = last_trained_count(db)
    log.info("trainer started; last run saw %d interactions", last_count)

    while running:
        total = count_interactions(db)
        new = total - last_count
        if total >= config.MIN_SAMPLES and new >= config.MIN_NEW_SAMPLES:
            try:
                run_once(db, qdrant, s3, total)
                last_count = total
            except Exception:
                log.exception("training run failed; will retry next interval")
        else:
            log.info("waiting: %d interactions (%d new), need %d total / %d new",
                     total, new, config.MIN_SAMPLES, config.MIN_NEW_SAMPLES)

        # Sleep in 1s steps so a shutdown signal is noticed quickly.
        for _ in range(config.TRAIN_INTERVAL_S):
            if not running:
                break
            time.sleep(1)

    log.info("shutting down")


if __name__ == "__main__":
    main()
