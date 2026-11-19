# RE-coil

A short-video recommender built end to end: videos go in, personalized feeds come out, and the ranking model retrains itself from what users do, with no human in the loop.

It's the same shape as a TikTok-style system: two-tower retrieval, a multi-stage ranking pipeline, a streaming retrain loop with a quality gate, an A/B holdout, and full observability. It runs on one laptop as a monorepo of services.

![ci](https://github.com/Yashas2004/RE-coil/actions/workflows/ci.yml/badge.svg)

## Results

Measured on a live run with 500 simulated users and 1,000 videos:

| | |
|---|---|
| Watch rate, random feed (no model) | **21%** |
| Watch rate, self-trained model | **47%** at first promotion, **~61%** at steady state |
| Theoretical ceiling with the diversity cap | ~60% (see *Trade-offs*) |
| A/B: model vs. trending-only control | **60.9% vs. 17.1%** watch rate |
| Validation AUC (champion re-scored on live data) | **~0.76** |
| Model knows both of a user's hidden tastes | **98.5%** of users |
| Predicted vs. true watch probability (liked videos) | 0.72–0.74 vs. 0.75 (well calibrated) |
| Feed latency p95 | 230 ms → **~100 ms** after removing PyTorch from the request path |

Nobody tells the model what any user likes. Each simulated user secretly loves 2 of 10 categories; the system has to discover that from watches and skips alone.

## Architecture

```mermaid
flowchart LR
    subgraph content [Content in]
        ING[ingest<br/>Python] -->|vectors| QD[(Qdrant)]
        ING -->|metadata| PG[(Postgres)]
    end

    subgraph behaviour [Behaviour in]
        SIM[sim-engine<br/>500 bots] -->|watch / skip| UE[user-event<br/>Go]
        UE --> KF[[Kafka]]
        KF --> FT[feature<br/>Python]
        FT -->|interactions| PG
        FT -->|trending, seen| RD[(Redis)]
    end

    subgraph learning [Learning loop]
        PG --> TR[training<br/>PyTorch]
        QD --> TR
        TR -->|model + latest.json| S3[(S3 / SeaweedFS)]
        S3 --> MS[model-server<br/>Python]
        MS -->|per-version tower index| QD
    end

    subgraph serving [Feeds out]
        SIM -->|GET /feed| FA[feed-api<br/>Go]
        FA --> MS
        FA --> RD
    end

    DA[dashboard-api<br/>Go] --> PG & RD & MS
    UI[React dashboard] --> DA
    PR[Prometheus] --> GF[Grafana]
```

**Stack:** Python 3.13 (FastAPI, PyTorch) for ML services · Go for the serving path · React + Vite dashboard · Kafka (KRaft) · Qdrant · Redis · Postgres · SeaweedFS (S3-compatible) · Prometheus + Grafana · Docker Compose.

## How it works

**Two-tower model.** One small network turns a user into a 64-number taste vector; another turns a video's content vector into 64 numbers in the same space. Their dot product is the score. Because the towers only meet at the very end, every video's vector is computed once and stored in Qdrant, and a request only computes the user's side. That's what makes searching the whole catalogue fast. Trained pointwise with binary cross-entropy on watched/skipped.

**Feed pipeline** (`feed-api`), the multi-stage funnel real recommenders use:
1. **Retrieval:** nearest neighbours to the user's vector in Qdrant (200 candidates), with recently seen videos filtered out inside the search.
2. **Ranking:** watch probability for every candidate plus trending videos.
3. **Re-ranking:** at most 2 videos per category, plus an **exploration** slot: the user's best guess from a category the feed isn't showing.

It degrades gracefully: no model yet, or model-server down, means a trending feed instead of an error.

**Retrain loop** (`training`). Every 30 s, if enough new interactions arrived: train on the most recent 200k events, then score **both the new model and the live model on the same validation rows**. Promote only if the new one clears an absolute AUC of 0.65 and isn't worse than the live one. Promotion just rewrites `latest.json`; the model-server hot-swaps to it with zero downtime (blue/green index per version).

**A/B holdout.** 10% of users, picked by hashing their ID so they never switch groups, get a trending-only feed. Both groups run at the same time, which makes the comparison fair in a way that before-and-after numbers can't be.

## What broke, and what I learned

The most useful part of this project was the bugs. Each one was caught by a test, a metric, or the dashboard.

1. **The first models couldn't pass the gate (AUC 0.54).** With ~17 events per user, 5 epochs at batch 512 meant only ~70 gradient updates. More steps and a higher learning rate fixed it, and the quality gate correctly refused to ship the bad models in the meantime.

2. **The loop froze: every new model was rejected.** The live model claimed AUC 0.81, and new ones scored ~0.75. But the 0.81 was measured when users saw *random* videos (easy to predict); later data came from *personalized* feeds (much harder). One fixed model scores 0.79 vs. 0.62 on the two kinds of data. AUCs from different data can't be compared. Fix: **champion vs. challenger** on identical rows. Re-scored fairly, the "0.81" champion was really 0.754, and the challenger won with 0.760.

3. **Different videos got identical scores.** The higher learning rate from bug 1 had killed **97.7% of the item tower's ReLU neurons**; only 416 of 1,000 videos kept a distinct vector. Switching to LeakyReLU at lr 0.003 restored all 1,000 and raised AUC on larger data from 0.70 to 0.81. A regression test now fails if two videos ever share a vector.

4. **Grafana showed feed p99 ~8× what I'd measured by hand.** The model-server called PyTorch on every request, and 20 concurrent requests plus the trainer fought over the CPU cores (0.37 ms alone, **106 ms p95** under load). All tower vectors are now precomputed when a model loads, so requests are a NumPy lookup and one matrix multiply: **0.3 ms p95**. `/score` dropped from ~200 ms to ~0 in production.

5. **I misdiagnosed a "filter bubble".** One user who likes comedy and music got only comedy, and I assumed the model hadn't learned music. A coverage metric against the bots' hidden tastes proved me wrong: the model *knew* both tastes for 98.5% of users. Raw top-10 retrieval just showed both only 20.8% of the time, because same-category videos have similar vectors. That gap is the job of the category cap and exploration.

6. **Trending measured exposure, not quality.** It ranked by watch *count*, and the model shows comedy to comedy fans, so trending became mostly comedy and control users did worse than random (17% vs. 21%). It now ranks by **smoothed watch rate**, so a video shown 100 times and watched 60 beats one shown 1,000 times and watched 250.

## Trade-offs and honest limits

- **Engagement vs. variety.** With a 5-video feed, 2 liked categories and a cap of 2 per category, the best possible watch rate is ~60%, and the model reaches it. A cap of 3 would score higher with less variety. `MAX_PER_CATEGORY` is an env var.
- **Simulated users.** Signals come from bots with simple, fixed tastes, not people.
- **Single objective.** The model predicts one thing (watch or skip). Production systems predict several (likes, shares, follows, watch time) and blend them; that multi-task ranking head is the biggest gap between this and the real thing.
- **Fake content embeddings.** Videos get deterministic 256-d vectors clustered by category instead of CLIP/Whisper embeddings. Every service only sees "a 256-number vector", so swapping in real encoders touches one file (`services/ingest/app/embedder.py`).
- **One machine.** No sharding, replication, or autoscaling.

## Run it

Requires Docker Desktop.

```bash
make up            # build every image (each build runs that service's tests) and start 16 services
make seed          # load 1,000 videos
make coverage      # what the model knows vs. what retrieval shows
make quality-gate  # fails unless a good model was promoted in the last 10 minutes
make down
```

No `make` (e.g. Windows cmd)? Each target is one line in the `Makefile`. For example, `make up` is `docker compose up -d --build --wait`.

| What | Where |
|---|---|
| Live dashboard: watch rate, A/B, training runs, feed inspector | http://localhost:3000 |
| Grafana: latency, throughput, AUC (admin/admin) | http://localhost:3001 |
| Prometheus targets | http://localhost:9090/targets |
| A feed, directly | `curl "localhost:8005/feed?user_id=u000001&limit=5"` |

## Layout

```
services/
  ingest/          Python  videos -> embeddings -> Postgres + Qdrant
  user-event/      Go      POST /event -> Kafka
  feature/         Python  Kafka -> interactions (Postgres) + trending/seen (Redis)
  training/        Python  retrain loop, champion vs. challenger, model registry
  model-server/    Python  hot-swapped model: /candidates, /score, /explore
  feed-api/        Go      retrieval -> ranking -> re-ranking, A/B holdout
  sim-engine/      Python  500 bots with hidden tastes, seeding, coverage report
  dashboard-api/   Go      read-only stats for the dashboard
dashboard/         React   live dashboard
infra/             Postgres schema + quality gate, Prometheus, Grafana dashboards
```

Each service has its own tests; CI runs all of them on every push.


