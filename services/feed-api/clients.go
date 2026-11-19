package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/redis/go-redis/v9"
)

// ---------- model-server ----------

type ModelClient struct {
	baseURL string
	http    *http.Client
}

func NewModelClient(baseURL string) *ModelClient {
	// A short timeout: a slow model must never make the whole feed slow.
	return &ModelClient{baseURL: baseURL, http: &http.Client{Timeout: 800 * time.Millisecond}}
}

func (m *ModelClient) post(ctx context.Context, path string, body any, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, m.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := m.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s returned %d", path, resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

type CandidatesResponse struct {
	ModelVersion string `json:"model_version"`
	Items        []struct {
		VideoID  string `json:"video_id"`
		Category string `json:"category"`
	} `json:"items"`
}

func (m *ModelClient) Candidates(ctx context.Context, userID string, k int, exclude []string) (CandidatesResponse, error) {
	var out CandidatesResponse
	body := map[string]any{"user_id": userID, "k": k, "exclude": exclude}
	err := m.post(ctx, "/candidates", body, &out)
	return out, err
}

type ScoreResponse struct {
	ModelVersion string `json:"model_version"`
	Scores       []struct {
		VideoID string  `json:"video_id"`
		PWatch  float64 `json:"p_watch"`
	} `json:"scores"`
}

func (m *ModelClient) Score(ctx context.Context, userID string, videoIDs []string) (ScoreResponse, error) {
	var out ScoreResponse
	body := map[string]any{"user_id": userID, "video_ids": videoIDs}
	err := m.post(ctx, "/score", body, &out)
	return out, err
}

type ExploreResponse struct {
	ModelVersion string `json:"model_version"`
	Item         struct {
		VideoID  string  `json:"video_id"`
		Category string  `json:"category"`
		Score    float64 `json:"score"`
	} `json:"item"`
}

// Explore asks for the user's best video in a category the feed isn't showing.
func (m *ModelClient) Explore(ctx context.Context, userID string, avoid []string, exclude []string) (Item, error) {
	var out ExploreResponse
	body := map[string]any{"user_id": userID, "avoid_categories": avoid, "exclude": exclude}
	if err := m.post(ctx, "/explore", body, &out); err != nil {
		return Item{}, err
	}
	return Item{VideoID: out.Item.VideoID, Category: out.Item.Category, Source: "explore"}, nil
}

// ---------- Redis (written by the feature service) ----------

type Store struct {
	rdb *redis.Client
}

func NewStore(url string) (*Store, error) {
	options, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}
	return &Store{rdb: redis.NewClient(options)}, nil
}

// Seen returns the videos this user was recently shown, newest first.
func (s *Store) Seen(ctx context.Context, userID string) ([]string, error) {
	return s.rdb.LRange(ctx, "seen:"+userID, 0, 199).Result()
}

// Trending returns the top n videos by smoothed watch RATE. The feature service
// computes the ranking (services/feature/app/realtime.py); we just read it.
func (s *Store) Trending(ctx context.Context, n int) ([]string, error) {
	return s.rdb.ZRevRange(ctx, "trending:score", 0, int64(n-1)).Result()
}
