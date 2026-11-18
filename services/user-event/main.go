// user-event: the front door for user behaviour.
//
//	POST /event   {"user_id":"u1","video_id":"v1","watched":true,"watch_ms":4200}
//	GET  /health
//
// It does almost nothing on purpose: validate, stamp the time, push to Kafka,
// return. Fast and dumb at the edge; the heavy lifting happens downstream.
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

func getenv(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}

func main() {
	brokers := strings.Split(getenv("KAFKA_BROKERS", "localhost:29092"), ",")
	topic := getenv("KAFKA_TOPIC", "interactions")
	port := getenv("PORT", "8002")

	producer := NewProducer(brokers, topic)
	defer producer.Close()

	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})

	mux.HandleFunc("POST /event", func(w http.ResponseWriter, r *http.Request) {
		var event Event
		err := json.NewDecoder(r.Body).Decode(&event)
		if err != nil {
			http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
			return
		}

		err = event.Validate()
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if event.Timestamp.IsZero() {
			event.Timestamp = time.Now().UTC()
		}

		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()

		err = producer.Publish(ctx, event)
		if err != nil {
			log.Printf("kafka publish failed: %v", err)
			http.Error(w, "could not record event", http.StatusServiceUnavailable)
			return
		}

		w.WriteHeader(http.StatusAccepted) // 202: "got it, processing later"
	})

	log.Printf("user-event listening on :%s, topic=%s brokers=%v", port, topic, brokers)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
