"""Prometheus metrics for the feature service.

A worker with no HTTP API still needs a /metrics page, so start_http_server
runs a tiny web server on its own thread just for Prometheus to scrape.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

events_consumed = Counter("recoil_events_consumed_total", "Events read from Kafka and parsed.")
events_skipped = Counter("recoil_events_skipped_total", "Kafka messages that failed parsing.")
rows_stored = Counter("recoil_interactions_stored_total", "Rows written to Postgres.")
batch_seconds = Histogram(
    "recoil_feature_batch_seconds", "Time to write one batch to Postgres and Redis.",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5],
)
last_batch_size = Gauge("recoil_feature_last_batch_size", "Events in the most recent batch.")

METRICS_PORT = 9100


def serve():
    start_http_server(METRICS_PORT)
