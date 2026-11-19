import os

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://recoil:recoil@localhost:5432/recoil")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "videos")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_BUCKET = os.getenv("S3_BUCKET", "models")

# The quality gate: a new model must beat this AUC to be promoted.
AUC_GATE = float(os.getenv("AUC_GATE", "0.65"))
# ...and must not be noticeably worse than the model currently serving.
AUC_TOLERANCE = float(os.getenv("AUC_TOLERANCE", "0.02"))

MIN_SAMPLES = int(os.getenv("MIN_SAMPLES", "1000"))        # don't train on tiny data
MIN_NEW_SAMPLES = int(os.getenv("MIN_NEW_SAMPLES", "500"))  # retrain after this many new events
MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", "200000"))       # train on the most recent N
TRAIN_INTERVAL_S = int(os.getenv("TRAIN_INTERVAL_S", "30"))
EPOCHS = int(os.getenv("EPOCHS", "5"))
