package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
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

// Trending sums this hour's and last hour's watch counts and returns the top n.
// Key format must match services/feature/app/realtime.py: trending:YYYYMMDDHH (UTC).
func (s *Store) Trending(ctx context.Context, n int) ([]string, error) {
	now := time.Now().UTC()
	keys := []string{
		"trending:" + now.Format("2006010215"),
		"trending:" + now.Add(-time.Hour).Format("2006010215"),
	}
	rows, err := s.rdb.ZUnionWithScores(ctx, redis.ZStore{Keys: keys}).Result()
	if err != nil {
		return nil, err
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Score > rows[j].Score })

	ids := []string{}
	for _, row := range rows {
		if len(ids) == n {
			break
		}
		ids = append(ids, fmt.Sprint(row.Member))
	}
	return ids, nil
}
