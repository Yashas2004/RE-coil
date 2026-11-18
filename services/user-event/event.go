package main

import (
	"errors"
	"time"
)

// Event is one "a user saw a video" signal.
// The `json:"..."` tags tell Go which JSON field name maps to which struct field.
type Event struct {
	UserID       string    `json:"user_id"`
	VideoID      string    `json:"video_id"`
	Watched      bool      `json:"watched"`       // true = watched (label 1), false = skipped (label 0)
	WatchMs      int       `json:"watch_ms"`      // how long they stayed on it
	ModelVersion string    `json:"model_version"` // which model served it (for A/B later)
	Timestamp    time.Time `json:"ts"`
}

// Validate rejects events we can't learn from. Bad data in = bad model out,
// so we stop it at the front door.
func (e *Event) Validate() error {
	if e.UserID == "" {
		return errors.New("user_id is required")
	}
	if e.VideoID == "" {
		return errors.New("video_id is required")
	}
	if e.WatchMs < 0 {
		return errors.New("watch_ms cannot be negative")
	}
	return nil
}
