"""
The ingest HTTP service.

  POST /videos        add one video
  POST /videos/batch  add many at once (the seed script uses this)
  GET  /videos/count  how many videos we have
  GET  /health        "am I alive?" — used by Docker's healthcheck

Run locally:  uvicorn app.main:app --reload --port 8001
Then open:    http://localhost:8001/docs   (FastAPI builds a test UI for free)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.embedder import CATEGORIES, embed_video
from app.store import Store

store: Store | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup: connect to databases, make sure the collection exists.
    global store
    store = Store()
    store.ensure_collection()
    yield
    # (anything after yield runs at shutdown)


app = FastAPI(title="RE-coil ingest", lifespan=lifespan)


class VideoIn(BaseModel):
    video_id: str = Field(examples=["v000001"])
    title: str = Field(examples=["Cat discovers cucumber"])
    category: str = Field(examples=["pets"])
    duration_s: int = Field(gt=0, examples=[30])


def ingest_one(video: VideoIn):
    vector = embed_video(video.video_id, video.category)
    store.save_video(
        video.video_id, video.title, video.category, video.duration_s, vector
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/categories")
def categories():
    return {"categories": CATEGORIES}


@app.post("/videos")
def add_video(video: VideoIn):
    ingest_one(video)
    return {"ingested": video.video_id}


@app.post("/videos/batch")
def add_videos(videos: list[VideoIn]):
    for video in videos:
        ingest_one(video)
    return {"ingested": len(videos)}


@app.get("/videos/count")
def count():
    return {"count": store.count_videos()}
