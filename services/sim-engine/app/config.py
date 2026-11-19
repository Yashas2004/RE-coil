import os

INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8001")
EVENT_URL = os.getenv("EVENT_URL", "http://localhost:8002")
# The feed doesn't exist until Phase 7. Until then the bots fall back to random videos.
FEED_URL = os.getenv("FEED_URL", "http://localhost:8005")

NUM_VIDEOS = int(os.getenv("NUM_VIDEOS", "1000"))
NUM_BOTS = int(os.getenv("NUM_BOTS", "500"))
SEED = int(os.getenv("SEED", "42"))

WORKERS = int(os.getenv("WORKERS", "20"))          # bots acting at the same time
FEED_SIZE = int(os.getenv("FEED_SIZE", "5"))       # videos per feed request
PAUSE_S = float(os.getenv("PAUSE_S", "0.2"))       # breather between feeds
REPORT_EVERY_S = int(os.getenv("REPORT_EVERY_S", "15"))
