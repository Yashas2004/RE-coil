package main

import (
	"context"
	"encoding/json"
	"time"

	"github.com/segmentio/kafka-go"
)

// Producer wraps a Kafka writer. Everything that publishes events goes through it.
type Producer struct {
	writer *kafka.Writer
}

func NewProducer(brokers []string, topic string) *Producer {
	writer := &kafka.Writer{
		Addr:  kafka.TCP(brokers...),
		Topic: topic,
		// Hash balancer: messages with the same key (user_id) always go to the
		// same partition, so one user's events stay in order.
		Balancer:               &kafka.Hash{},
		BatchTimeout:           10 * time.Millisecond, // don't wait long to fill a batch
		RequiredAcks:           kafka.RequireOne,      // leader confirmed the write
		AllowAutoTopicCreation: true,
	}
	return &Producer{writer: writer}
}

func (p *Producer) Publish(ctx context.Context, event Event) error {
	body, err := json.Marshal(event)
	if err != nil {
		return err
	}
	message := kafka.Message{
		Key:   []byte(event.UserID),
		Value: body,
	}
	return p.writer.WriteMessages(ctx, message)
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
