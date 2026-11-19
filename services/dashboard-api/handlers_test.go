package main

import (
	"net/http/httptest"
	"strings"
	"testing"
)

func TestIntParam(t *testing.T) {
	cases := []struct {
		query string
		want  int
	}{
		{"", 30},              // missing -> default
		{"minutes=abc", 30},   // garbage -> default
		{"minutes=-5", 30},    // negative -> default
		{"minutes=99999", 30}, // too big -> default
		{"minutes=60", 60},
	}
	for _, c := range cases {
		r := httptest.NewRequest("GET", "/api/watch-rate?"+c.query, nil)
		got := intParam(r, "minutes", 30, 24*60)
		if got != c.want {
			t.Errorf("%q: want %d, got %d", c.query, c.want, got)
		}
	}
}

// The variant labels in SQL must match the ones the feed and sim produce.
func TestVariantExprCoversAllLabels(t *testing.T) {
	for _, label := range []string{"'control'", "'random'", "'trending'", "'unknown'"} {
		if !strings.Contains(variantExpr, label) {
			t.Errorf("variantExpr does not handle %s", label)
		}
	}
}
