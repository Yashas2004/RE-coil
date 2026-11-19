.PHONY: up seed down reset logs ps psql topics test coverage quality-gate

# Build every image (each build runs that service's tests) and wait until healthy.
up:
	docker compose up -d --build --wait

# Load the 1000-video catalog through the ingest API. Safe to run twice.
seed:
	docker compose run --rm sim-engine python -m app.seed

down:
	docker compose down

# Nuke volumes too (fresh database, empty Qdrant, empty object storage).
reset:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# Every Dockerfile runs its service's test suite, so building == testing.
test:
	docker compose build

# Does the model know each bot's hidden tastes? (KNOWS vs SHOWS)
coverage:
	docker compose run --rm sim-engine python -m app.coverage

# Fails (non-zero exit) unless a model above the AUC gate was promoted in the last 10 minutes.
quality-gate:
	docker compose exec -T postgres psql -U recoil -d recoil -q -v ON_ERROR_STOP=1 -f - < infra/postgres/quality_gate.sql

# Open a SQL shell inside Postgres.
psql:
	docker compose exec postgres psql -U recoil -d recoil

# List Kafka topics.
topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
