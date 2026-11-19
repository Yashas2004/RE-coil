package main

import "testing"

func item(id, category string, p float64) Item {
	return Item{VideoID: id, Category: category, PWatch: p, Source: "model"}
}

// The exact situation from the real model: all-comedy at the top, music just below.
func TestBlendCapsOneCategory(t *testing.T) {
	ranked := []Item{
		item("c1", "comedy", 0.99), item("c2", "comedy", 0.98), item("c3", "comedy", 0.97),
		item("c4", "comedy", 0.96), item("m1", "music", 0.90), item("m2", "music", 0.89),
		item("p1", "pets", 0.30),
	}

	feed := Blend(ranked, nil, 5, 2, false)

	counts := map[string]int{}
	for _, it := range feed {
		counts[it.Category]++
	}
	if len(feed) != 5 {
		t.Fatalf("want 5 items, got %d", len(feed))
	}
	if counts["comedy"] != 2 || counts["music"] != 2 {
		t.Errorf("want 2 comedy + 2 music, got %v", counts)
	}
	if feed[0].VideoID != "c1" {
		t.Errorf("best item should still lead, got %s", feed[0].VideoID)
	}
}

func TestBlendRelaxesCapWhenShort(t *testing.T) {
	ranked := []Item{item("c1", "comedy", 0.9), item("c2", "comedy", 0.8), item("c3", "comedy", 0.7)}
	feed := Blend(ranked, nil, 3, 1, false)
	if len(feed) != 3 {
		t.Fatalf("cap should relax to fill the feed, got %d items", len(feed))
	}
}

func TestBlendExploreUsesUnpickedTrending(t *testing.T) {
	ranked := []Item{item("a", "comedy", 0.9), item("b", "music", 0.8)}
	trending := []Item{{VideoID: "a"}, {VideoID: "t1"}}

	feed := Blend(ranked, trending, 2, 2, true)

	last := feed[len(feed)-1]
	if last.VideoID != "t1" || last.Source != "explore" {
		t.Errorf("want explore slot t1, got %+v", last)
	}
}

func TestBlendNeverDuplicates(t *testing.T) {
	ranked := []Item{item("a", "x", 0.9), item("a", "x", 0.9), item("b", "y", 0.5)}
	feed := Blend(ranked, nil, 5, 5, false)
	if len(feed) != 2 {
		t.Errorf("duplicates should be dropped, got %d items", len(feed))
	}
}
