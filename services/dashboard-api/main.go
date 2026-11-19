// dashboard-api: read-only JSON for the React dashboard.
//
// It never writes anything. It just looks at Postgres (history), Redis (right
// now) and the model-server (what's live) and summarises them.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

// withCORS lets the Vite dev server (a different port) call this API during development.
func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		next.ServeHTTP(w, r)
	})
}

func main() {
	ctx := context.Background()

	// A pool keeps a few database connections open and shares them between requests.
	db, err := pgxpool.New(ctx, getenv("POSTGRES_DSN", "postgresql://recoil:recoil@localhost:5432/recoil"))
	if err != nil {
		log.Fatalf("postgres: %v", err)
	}
	defer db.Close()

	redisOptions, err := redis.ParseURL(getenv("REDIS_URL", "redis://localhost:6379/0"))
	if err != nil {
		log.Fatalf("redis: %v", err)
	}

	api := &API{
		db:       db,
		rdb:      redis.NewClient(redisOptions),
		modelURL: getenv("MODEL_SERVER_URL", "http://localhost:8004"),
		feedURL:  getenv("FEED_URL", "http://localhost:8005"),
		http:     &http.Client{Timeout: 2 * time.Second},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("GET /api/overview", api.Overview)
	mux.HandleFunc("GET /api/watch-rate", api.WatchRate)
	mux.HandleFunc("GET /api/ab", api.AB)
	mux.HandleFunc("GET /api/training-runs", api.TrainingRuns)
	mux.HandleFunc("GET /api/trending", api.Trending)
	mux.HandleFunc("GET /api/feed", api.Feed)

	port := getenv("PORT", "8006")
	log.Printf("dashboard-api listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, withCORS(mux)))
}
