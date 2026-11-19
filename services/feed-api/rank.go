package main

// Item is one video on its way into a feed.
type Item struct {
	VideoID  string  `json:"video_id"`
	Category string  `json:"category,omitempty"`
	PWatch   float64 `json:"p_watch"`
	Source   string  `json:"source"` // "model", "trending" or "explore"
}

// Blend is the final stage of the pipeline: re-ranking.
//
// The ranker already sorted `ranked` by watch probability. If we just took the
// top N, a user who loves comedy would get a feed of nothing but comedy, even
// if they also love music. So we walk down the list and cap how many videos any
// one category may take. If the caps leave the feed short, we relax them.
//
// If explore is true, the last slot goes to a trending video the model did NOT
// pick. That's exploration: without it, the model only ever learns about videos
// it already shows, and it can never discover a taste it hasn't seen yet.
func Blend(ranked []Item, trending []Item, limit int, maxPerCategory int, explore bool) []Item {
	feed := []Item{}
	used := map[string]bool{}
	perCategory := map[string]int{}
	leftovers := []Item{}

	// Pass 1: best-first, respecting the per-category cap.
	for _, item := range ranked {
		if len(feed) == limit {
			break
		}
		if used[item.VideoID] {
			continue
		}
		if item.Category != "" && perCategory[item.Category] >= maxPerCategory {
			leftovers = append(leftovers, item)
			continue
		}
		feed = append(feed, item)
		used[item.VideoID] = true
		perCategory[item.Category]++
	}

	// Pass 2: not enough variety available? Fill up from what the cap held back.
	for _, item := range leftovers {
		if len(feed) == limit {
			break
		}
		feed = append(feed, item)
		used[item.VideoID] = true
	}

	// Exploration slot.
	if explore && len(feed) > 0 {
		for _, item := range trending {
			if used[item.VideoID] {
				continue
			}
			item.Source = "explore"
			feed[len(feed)-1] = item
			break
		}
	}

	return feed
}

// FeedCategories lists the distinct categories already in a feed.
func FeedCategories(items []Item) []string {
	seen := map[string]bool{}
	result := []string{}
	for _, item := range items {
		if item.Category != "" && !seen[item.Category] {
			seen[item.Category] = true
			result = append(result, item.Category)
		}
	}
	return result
}
