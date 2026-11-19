"""Prometheus metrics for the trainer."""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

runs = Counter("recoil_training_runs_total", "Training runs by outcome.", ["outcome"])
duration = Histogram(
    "recoil_training_seconds", "Wall time of one training run.",
    buckets=[1, 2, 5, 10, 20, 30, 60, 120, 300],
)
# role is "challenger" or "champion": both measured on the SAME validation rows.
auc = Gauge("recoil_model_auc", "Validation AUC from the latest run.", ["role"])
samples = Gauge("recoil_training_samples", "Rows used in the latest run.")
last_promotion = Gauge("recoil_last_promotion_timestamp_seconds", "Unix time of the last promotion.")

METRICS_PORT = 9101


def serve():
    start_http_server(METRICS_PORT)
