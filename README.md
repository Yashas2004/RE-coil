# RE-coil

A short-video recommendation system built end to end: content goes in, personalized feeds come out, and the ranking model retrains itself from user behaviour.

> Work in progress — being built phase by phase.

## Run the infrastructure

```bash
make up     # Kafka, Qdrant, Redis, MinIO, Postgres, Prometheus, Grafana
make ps     # everything should say "healthy"
make down
```

| What                   | Where                           |
| ---------------------- | ------------------------------- |
| Grafana (admin/admin)  | http://localhost:3001           |
| Prometheus             | http://localhost:9090           |
| SeaweedFS file browser | http://localhost:8888           |
| Qdrant dashboard       | http://localhost:6333/dashboard |
