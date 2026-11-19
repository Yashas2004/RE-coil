package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type API struct {
	db       *pgxpool.Pool
	rdb      *redis.Client
	modelURL string
	feedURL  string
	http     *http.Client
}

func writeJSON(w http.ResponseWriter, value any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(value)
}

func fail(w http.ResponseWriter, err error) {
	http.Error(w, err.Error(), http.StatusInternalServerError)
}

func intParam(r *http.Request, name string, fallback, max int) int {
	value, err := strconv.Atoi(r.URL.Query().Get(name))
	if err != nil || value <= 0 || value > max {
		return fallback
	}
	return value
}

// GET /api/overview: the numbers across the top of the dashboard.
func (a *API) Overview(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var videos, users, interactions, lastMinute int64
	err := a.db.QueryRow(ctx, countsSQL).Scan(&videos, &users, &interactions, &lastMinute)
	if err != nil {
		fail(w, err)
		return
	}

	// The live model, straight from the model-server. If it's down, say so.
	var model map[string]any
	resp, err := a.http.Get(a.modelURL + "/model")
	if err == nil {
		json.NewDecoder(resp.Body).Decode(&model)
		resp.Body.Close()
	}

	writeJSON(w, map[string]any{
		"videos":          videos,
		"users":           users,
		"interactions":    interactions,
		"events_per_sec":  float64(lastMinute) / 60,
		"model":           model,
		"model_server_up": err == nil,
	})
}

type WatchRatePoint struct {
	Minute  time.Time `json:"minute"`
	Variant string    `json:"variant"`
	Shown   int64     `json:"shown"`
	Watched int64     `json:"watched"`
	Rate    float64   `json:"rate"`
}

// GET /api/watch-rate?minutes=30
func (a *API) WatchRate(w http.ResponseWriter, r *http.Request) {
	minutes := intParam(r, "minutes", 30, 24*60)
	rows, err := a.db.Query(r.Context(), watchRateSQL, minutes)
	if err != nil {
		fail(w, err)
		return
	}
	defer rows.Close()

	points := []WatchRatePoint{}
	for rows.Next() {
		var p WatchRatePoint
		if err := rows.Scan(&p.Minute, &p.Variant, &p.Shown, &p.Watched); err != nil {
			fail(w, err)
			return
		}
		if p.Shown > 0 {
			p.Rate = float64(p.Watched) / float64(p.Shown)
		}
		points = append(points, p)
	}
	writeJSON(w, points)
}

type ABRow struct {
	Variant string  `json:"variant"`
	Shown   int64   `json:"shown"`
	Watched int64   `json:"watched"`
	Users   int64   `json:"users"`
	Rate    float64 `json:"rate"`
}

// GET /api/ab?minutes=15: the A/B scoreboard, plus the lift of model over control.
func (a *API) AB(w http.ResponseWriter, r *http.Request) {
	minutes := intParam(r, "minutes", 15, 24*60)
	rows, err := a.db.Query(r.Context(), abSQL, minutes)
	if err != nil {
		fail(w, err)
		return
	}
	defer rows.Close()

	result := []ABRow{}
	rates := map[string]float64{}
	for rows.Next() {
		var row ABRow
		if err := rows.Scan(&row.Variant, &row.Shown, &row.Watched, &row.Users); err != nil {
			fail(w, err)
			return
		}
		if row.Shown > 0 {
			row.Rate = float64(row.Watched) / float64(row.Shown)
		}
		rates[row.Variant] = row.Rate
		result = append(result, row)
	}

	// Lift = how much better the model does than control, in relative terms.
	// 0.45 vs 0.30 -> +50% lift.
	var lift *float64
	if rates["control"] > 0 && rates["model"] > 0 {
		value := rates["model"]/rates["control"] - 1
		lift = &value
	}
	writeJSON(w, map[string]any{"minutes": minutes, "variants": result, "lift": lift})
}

type TrainingRun struct {
	Version    string    `json:"version"`
	Samples    int64     `json:"samples"`
	AUC        float64   `json:"auc"`
	Promoted   bool      `json:"promoted"`
	StartedAt  time.Time `json:"started_at"`
	FinishedAt time.Time `json:"finished_at"`
}

// GET /api/training-runs?limit=20
func (a *API) TrainingRuns(w http.ResponseWriter, r *http.Request) {
	limit := intParam(r, "limit", 20, 200)
	rows, err := a.db.Query(r.Context(), trainingRunsSQL, limit)
	if err != nil {
		fail(w, err)
		return
	}
	defer rows.Close()

	runs := []TrainingRun{}
	for rows.Next() {
		var run TrainingRun
		err := rows.Scan(&run.Version, &run.Samples, &run.AUC, &run.Promoted, &run.StartedAt, &run.FinishedAt)
		if err != nil {
			fail(w, err)
			return
		}
		runs = append(runs, run)
	}
	writeJSON(w, runs)
}

type TrendingItem struct {
	VideoID   string  `json:"video_id"`
	Title     string  `json:"title"`
	Category  string  `json:"category"`
	WatchRate float64 `json:"watch_rate"`
}

// GET /api/trending: the feature service's ranking (smoothed watch rate), with titles.
func (a *API) Trending(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	rows, err := a.rdb.ZRevRangeWithScores(ctx, "trending:score", 0, 9).Result()
	if err != nil {
		fail(w, err)
		return
	}

	items := []TrendingItem{}
	ids := []string{}
	for _, row := range rows {
		id := fmt.Sprint(row.Member)
		ids = append(ids, id)
		items = append(items, TrendingItem{VideoID: id, WatchRate: row.Score})
	}
	details := a.videoDetails(ctx, ids)
	for i := range items {
		items[i].Title = details[items[i].VideoID][0]
		items[i].Category = details[items[i].VideoID][1]
	}
	writeJSON(w, items)
}

// videoDetails returns video_id -> [title, category].
func (a *API) videoDetails(ctx context.Context, ids []string) map[string][2]string {
	result := map[string][2]string{}
	rows, err := a.db.Query(ctx, categoriesSQL, ids)
	if err != nil {
		return result
	}
	defer rows.Close()
	for rows.Next() {
		var id, category, title string
		if rows.Scan(&id, &category, &title) == nil {
			result[id] = [2]string{title, category}
		}
	}
	return result
}

// GET /api/feed?user_id=u000000: proxies the real feed so you can inspect any user.
func (a *API) Feed(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		http.Error(w, "user_id is required", http.StatusBadRequest)
		return
	}
	target := a.feedURL + "/feed?limit=10&user_id=" + url.QueryEscape(userID)
	resp, err := a.http.Get(target)
	if err != nil {
		http.Error(w, "feed-api unreachable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}
