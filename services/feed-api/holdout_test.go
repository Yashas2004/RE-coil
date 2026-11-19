package main

import (
	"fmt"
	"testing"
)

func TestHoldoutIsStable(t *testing.T) {
	for i := 0; i < 100; i++ {
		id := fmt.Sprintf("u%06d", i)
		if InHoldout(id, 10) != InHoldout(id, 10) {
			t.Fatalf("%s switched groups", id)
		}
	}
}

func TestHoldoutSizeIsRoughlyRight(t *testing.T) {
	inControl := 0
	for i := 0; i < 5000; i++ {
		if InHoldout(fmt.Sprintf("u%06d", i), 10) {
			inControl++
		}
	}
	share := float64(inControl) / 5000
	if share < 0.08 || share > 0.12 {
		t.Errorf("want ~10%% in control, got %.1f%%", share*100)
	}
}

func TestHoldoutZeroPercentMeansNobody(t *testing.T) {
	for i := 0; i < 1000; i++ {
		if InHoldout(fmt.Sprintf("u%06d", i), 0) {
			t.Fatal("0% holdout should put nobody in control")
		}
	}
}
