.PHONY: up down reset logs ps psql topics

# Boot everything and block until every healthcheck passes.
up:
	docker compose up -d --wait

down:
	docker compose down

# Nuke volumes too (fresh database, empty Qdrant, empty MinIO).
reset:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# Open a SQL shell inside Postgres.
psql:
	docker compose exec postgres psql -U recoil -d recoil

# List Kafka topics.
topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
