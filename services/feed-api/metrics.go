package main

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Three kinds of Prometheus metric, all used here:
//
//	Counter   only goes up (requests served). Prometheus turns it into a rate.
//	Histogram counts observations into buckets (latencies). Gives you p50/p95/p99.
//	Gauge     goes up and down (not needed in this service).
//
// Labels split one metric into several series, e.g. latency for "model" vs "control".
// Keep label values to a small fixed set: a label per user_id would create
// millions of series and take Prometheus down. That mistake is called
// "cardinality explosion".
var (
	feedLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "recoil_feed_request_seconds",
		Help:    "Time to build one feed.",
		Buckets: []float64{0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1, 2},
	}, []string{"variant"})

	feedRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "recoil_feed_requests_total",
		Help: "Feed requests by A/B variant and outcome.",
	}, []string{"variant", "outcome"})

	feedItems = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "recoil_feed_items_total",
		Help: "Videos served, by which stage put them in the feed.",
	}, []string{"source"})
)

// variantOf maps a feed's model_version onto a small, fixed label set.
func variantOf(modelVersion string) string {
	switch modelVersion {
	case "control":
		return "control"
	case "trending":
		return "fallback"
	default:
		return "model"
	}
}
