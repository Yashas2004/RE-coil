package main

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// result is one of: accepted, invalid, kafka_error
	eventsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "recoil_events_received_total",
		Help: "Events received at the front door, by result.",
	}, []string{"result"})

	publishSeconds = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "recoil_kafka_publish_seconds",
		Help:    "Time for Kafka to acknowledge one event.",
		Buckets: []float64{0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2},
	})
)
