"""
Loads the catalog into the system through the ingest API, the same front
door a real uploader would use. Safe to run twice (ingest upserts).

    docker compose run --rm sim-engine python -m app.seed
"""

import time

import httpx

from app import config
from app.catalog import make_catalog

BATCH = 100


def wait_for(url: str, attempts: int = 30):
    for _ in range(attempts):
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise SystemExit(f"{url} never became healthy")


def main():
    wait_for(config.INGEST_URL + "/health")
    catalog = make_catalog(config.NUM_VIDEOS, config.SEED)

    sent = 0
    for start in range(0, len(catalog), BATCH):
        batch = catalog[start:start + BATCH]
        response = httpx.post(config.INGEST_URL + "/videos/batch", json=batch, timeout=60)
        response.raise_for_status()
        sent += len(batch)
        print(f"ingested {sent}/{len(catalog)}")

    count = httpx.get(config.INGEST_URL + "/videos/count", timeout=10).json()["count"]
    print(f"done: {count} videos in the system")


if __name__ == "__main__":
    main()
