// feed-api: the endpoint every phone would call.
//
//	GET /feed?user_id=u000000&limit=5
//
// It runs the multi-stage pipeline real recommenders use:
//
//  1. RETRIEVAL  model-server /candidates: ~200 good-looking videos out of all of them
//  2. FILTERING  drop what this user saw recently (Redis seen list)
//  3. RANKING    model-server /score: watch probability for candidates + trending
//  4. RE-RANKING Blend(): category caps for variety, one exploration slot
//
// If the model is down or not trained yet, it degrades to trending instead of failing.
package main

import (
	"context"
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Config struct {
	Port           string
	ModelURL       string
	RedisURL       string
	Candidates     int
	MaxPerCategory int
	ExploreRate    float64
	HoldoutPct     int
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func loadConfig() Config {
	candidates, _ := strconv.Atoi(getenv("CANDIDATES", "200"))
	maxPerCategory, _ := strconv.Atoi(getenv("MAX_PER_CATEGORY", "2"))
	exploreRate, _ := strconv.ParseFloat(getenv("EXPLORE_RATE", "0.2"), 64)
	holdoutPct, _ := strconv.Atoi(getenv("HOLDOUT_PCT", "10"))
	return Config{
		Port:           getenv("PORT", "8005"),
		ModelURL:       getenv("MODEL_SERVER_URL", "http://localhost:8004"),
		RedisURL:       getenv("REDIS_URL", "redis://localhost:6379/0"),
		Candidates:     candidates,
		MaxPerCategory: maxPerCategory,
		ExploreRate:    exploreRate,
		HoldoutPct:     holdoutPct,
	}
}

type FeedResponse struct {
	UserID       string  `json:"user_id"`
	ModelVersion string  `json:"model_version"`
	Items        []Item  `json:"items"`
	LatencyMs    float64 `json:"latency_ms"`
}

type Server struct {
	cfg   Config
	model *ModelClient
	store *Store
}

func (s *Server) buildFeed(ctx context.Context, userID string, limit int) (FeedResponse, error) {
	// A/B test: the control group never touches the model.
	if InHoldout(userID, s.cfg.HoldoutPct) {
		seen, _ := s.store.Seen(ctx, userID)
		trendingIDs, _ := s.store.Trending(ctx, 200)
		feed := s.trendingOnly(userID, trendingIDs, seen, limit)
		feed.ModelVersion = "control"
		return feed, nil
	}

	seen, err := s.store.Seen(ctx, userID)
	if err != nil {
		log.Printf("redis seen: %v", err) // not fatal: we just might repeat a video
	}
	trendingIDs, err := s.store.Trending(ctx, 20)
	if err != nil {
		log.Printf("redis trending: %v", err)
	}

	// 1 + 2: retrieval, with recently-seen videos filtered out inside Qdrant.
	candidates, err := s.model.Candidates(ctx, userID, s.cfg.Candidates, seen)
	if err != nil {
		return s.trendingOnly(userID, trendingIDs, seen, limit), nil
	}

	category := map[string]string{}
	toScore := []string{}
	for _, c := range candidates.Items {
		category[c.VideoID] = c.Category
		toScore = append(toScore, c.VideoID)
	}
	seenSet := map[string]bool{}
	for _, id := range seen {
		seenSet[id] = true
	}
	trending := []Item{}
	for _, id := range trendingIDs {
		if seenSet[id] {
			continue
		}
		trending = append(trending, Item{VideoID: id, Category: category[id], Source: "trending"})
		if _, alreadyCandidate := category[id]; !alreadyCandidate {
			toScore = append(toScore, id)
		}
	}

	// 3: ranking. The model-server returns them sorted by p_watch already.
	scores, err := s.model.Score(ctx, userID, toScore)
	if err != nil {
		return s.trendingOnly(userID, trendingIDs, seen, limit), nil
	}
	ranked := []Item{}
	for _, sc := range scores.Scores {
		source := "model"
		if _, fromRetrieval := category[sc.VideoID]; !fromRetrieval {
			source = "trending"
		}
		ranked = append(ranked, Item{
			VideoID: sc.VideoID, Category: category[sc.VideoID], PWatch: sc.PWatch, Source: source,
		})
	}

	// 4: re-ranking.
	explore := rand.Float64() < s.cfg.ExploreRate
	items := Blend(ranked, trending, limit, s.cfg.MaxPerCategory, explore)

	return FeedResponse{UserID: userID, ModelVersion: candidates.ModelVersion, Items: items}, nil
}

// trendingOnly is the fallback when there's no model: popular videos the user hasn't seen.
func (s *Server) trendingOnly(userID string, trendingIDs, seen []string, limit int) FeedResponse {
	seenSet := map[string]bool{}
	for _, id := range seen {
		seenSet[id] = true
	}
	items := []Item{}
	for _, id := range trendingIDs {
		if len(items) == limit {
			break
		}
		if !seenSet[id] {
			items = append(items, Item{VideoID: id, Source: "trending"})
		}
	}
	return FeedResponse{UserID: userID, ModelVersion: "trending", Items: items}
}

func (s *Server) handleFeed(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		http.Error(w, "user_id is required", http.StatusBadRequest)
		return
	}
	limit, err := strconv.Atoi(r.URL.Query().Get("limit"))
	if err != nil || limit <= 0 || limit > 50 {
		limit = 10
	}

	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	feed, err := s.buildFeed(ctx, userID, limit)
	if err != nil {
		feedRequests.WithLabelValues("unknown", "error").Inc()
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	variant := variantOf(feed.ModelVersion)
	if len(feed.Items) == 0 {
		feedRequests.WithLabelValues(variant, "empty").Inc()
		http.Error(w, "nothing to recommend yet", http.StatusServiceUnavailable)
		return
	}

	elapsed := time.Since(start)
	feedLatency.WithLabelValues(variant).Observe(elapsed.Seconds())
	feedRequests.WithLabelValues(variant, "ok").Inc()
	for _, item := range feed.Items {
		feedItems.WithLabelValues(item.Source).Inc()
	}

	feed.LatencyMs = float64(elapsed.Microseconds()) / 1000
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(feed)
}

func main() {
	cfg := loadConfig()
	store, err := NewStore(cfg.RedisURL)
	if err != nil {
		log.Fatalf("redis: %v", err)
	}
	server := &Server{cfg: cfg, model: NewModelClient(cfg.ModelURL), store: store}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("GET /feed", server.handleFeed)
	mux.Handle("GET /metrics", promhttp.Handler()) // Prometheus scrapes this

	log.Printf("feed-api listening on :%s (model=%s)", cfg.Port, cfg.ModelURL)
	log.Fatal(http.ListenAndServe(":"+cfg.Port, mux))
}
