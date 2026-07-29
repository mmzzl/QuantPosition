package validator

import (
	"fmt"
	"testing"
)

func genBars(n int) []DailyBar {
	bars := make([]DailyBar, n)
	for i := 0; i < n; i++ {
		ci := float64(i)
		bars[i] = DailyBar{
			Date:      fmt.Sprintf("2025-01-%02d", i+1),
			Close:     100 + ci*0.5,
			Ma5:       99 + ci*0.5,
			Ma10:      98 + ci*0.5,
			Ma20:      97 + ci*0.5,
			Volume:    20000,
			Ma5Vol:    10000,
			Amplitude: 0.05,
		}
	}
	return bars
}

func TestCalcPV_GoodConditions(t *testing.T) {
	bars := genBars(20)
	score := calcPV(bars, 19)
	if score.Total <= 0 {
		t.Fatalf("expected total > 0, got %d (maTrend=%d volPrice=%d breakthrough=%d amp=%d)",
			score.Total, score.MaTrend, score.VolumePrice, score.Breakthrough, score.Amplitude)
	}
	if score.MaTrend != 15 {
		t.Fatalf("expected maTrend=15, got %d", score.MaTrend)
	}
}

func TestCalcPV_PenaltyBelowMa20(t *testing.T) {
	bars := genBars(20)
	for i := range bars {
		bars[i].Ma20 = 105 + float64(i)*0.5
	}
	score := calcPV(bars, 19)
	if score.Total != 0 {
		t.Fatalf("expected total=0 due to close<ma20, got %d", score.Total)
	}
}
