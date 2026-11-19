import os

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "interactions")
# All consumers sharing this group id split the partitions between them.
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "feature-service")

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN", "postgresql://recoil:recoil@localhost:5432/recoil"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))
