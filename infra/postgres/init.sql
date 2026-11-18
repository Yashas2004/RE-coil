-- Runs once, the first time the Postgres volume is created.
-- If you change this file later, run `make reset` to wipe and recreate.

CREATE TABLE IF NOT EXISTS videos (
    video_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    duration_s   INT  NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per "user saw video" event. This table IS the training data.
-- watched = true  -> positive example (label 1)
-- watched = false -> skipped, negative example (label 0)
CREATE TABLE IF NOT EXISTS interactions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    video_id     TEXT NOT NULL REFERENCES videos(video_id),
    watched      BOOLEAN NOT NULL,
    watch_ms     INT NOT NULL DEFAULT 0,
    model_version TEXT,                    -- which model served this video (for A/B later)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions (created_at);
CREATE INDEX IF NOT EXISTS idx_interactions_user    ON interactions (user_id);

-- One row per training attempt, promoted or not.
CREATE TABLE IF NOT EXISTS training_runs (
    run_id       BIGSERIAL PRIMARY KEY,
    model_version TEXT NOT NULL,
    num_samples  INT NOT NULL,
    auc          DOUBLE PRECISION,
    promoted     BOOLEAN NOT NULL DEFAULT false,
    artifact_key TEXT,                     -- path of the model file in MinIO
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);
