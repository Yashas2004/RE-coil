"""
model-server: serves whichever model the trainer last promoted.

  GET  /health
  GET  /model                     which version is live, its AUC, sizes
  POST /candidates  {user_id, k, exclude}   retrieval: top-k videos for a user
  POST /score       {user_id, video_ids}    ranking: watch probability per video

A background thread polls the registry every POLL_INTERVAL_S seconds.
When latest.json points at a new version (or new videos were ingested), it:
  1. downloads the model and loads it              (requests still use the OLD one)
  2. builds the item index for it in Qdrant        (still the OLD one)
  3. swaps `current` to the new bundle in one step (now everyone uses the NEW one)
Zero downtime, no request ever sees a half-loaded model. This is a "hot swap".
"""

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient

from app import config
from app.bundle import ModelBundle
from app.index import (
    cleanup_old_indexes, content_count, load_content_vectors, search, write_tower_index,
)
from app.loader import download_checkpoint, read_latest, s3_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("model-server")


class Live:
    """What's currently being served. Replaced as a whole, never edited in place."""
    def __init__(self, bundle, index_name, auc, num_items):
        self.bundle = bundle
        self.index_name = index_name
        self.auc = auc
        self.num_items = num_items


current: Live | None = None
qdrant = QdrantClient(url=config.QDRANT_URL)


def refresh():
    global current
    s3 = s3_client()
    latest = read_latest(s3)
    if latest is None:
        return  # nothing promoted yet

    items_now = content_count(qdrant)
    same_version = current is not None and current.bundle.version == latest["version"]
    if same_version and current.num_items == items_now:
        return  # nothing changed

    log.info("loading %s (auc=%.4f) over %d videos", latest["version"], latest["auc"], items_now)
    checkpoint = download_checkpoint(s3, latest["key"])
    bundle = ModelBundle(checkpoint)

    ids, video_ids, categories, content = load_content_vectors(qdrant)
    bundle.build_item_index(video_ids, content)
    index_name = write_tower_index(qdrant, bundle.version, ids, video_ids, categories, bundle.item_matrix)

    previous = current
    current = Live(bundle, index_name, latest["auc"], len(video_ids))   # <- the swap
    log.info("now serving %s", bundle.version)

    keep = {index_name}
    if previous is not None:
        keep.add(previous.index_name)
    cleanup_old_indexes(qdrant, keep)


def poll_forever():
    while True:
        try:
            refresh()
        except Exception:
            log.exception("refresh failed; still serving the previous model")
        time.sleep(config.POLL_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # daemon=True: the thread dies with the process, no cleanup needed.
    thread = threading.Thread(target=poll_forever, daemon=True)
    thread.start()
    yield


app = FastAPI(title="RE-coil model-server", lifespan=lifespan)


def require_model() -> Live:
    live = current   # read once, so a swap mid-request can't mix two models
    if live is None:
        raise HTTPException(status_code=503, detail="no model promoted yet")
    return live


class CandidatesIn(BaseModel):
    user_id: str
    k: int = 200
    exclude: list[str] = []


class ScoreIn(BaseModel):
    user_id: str
    video_ids: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model")
def model_info():
    live = current
    if live is None:
        return {"version": None}
    return {
        "version": live.bundle.version,
        "auc": live.auc,
        "users": len(live.bundle.user_vocab),
        "items": live.num_items,
    }


@app.post("/candidates")
def candidates(body: CandidatesIn):
    live = require_model()
    user_vector = live.bundle.user_vector(body.user_id)
    items = search(qdrant, live.index_name, user_vector, body.k, body.exclude)
    return {
        "model_version": live.bundle.version,
        "known_user": live.bundle.is_known(body.user_id),
        "items": items,
    }


@app.post("/score")
def score(body: ScoreIn):
    live = require_model()
    scored = live.bundle.score(body.user_id, body.video_ids)
    results = []
    for video_id, probability in scored:
        results.append({"video_id": video_id, "p_watch": probability})
    return {"model_version": live.bundle.version, "scores": results}
