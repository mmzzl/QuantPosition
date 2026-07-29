package validator

import (
	"fmt"
	"testing"
)

func genBacktestStocks(numStocks, numBars int) (map[string][]DailyBar, map[string]string) {
	stocks := make(map[string][]DailyBar)
	names := make(map[string]string)
	for s := 0; s < numStocks; s++ {
		code := fmt.Sprintf("%06d", s+1)
		name := fmt.Sprintf("Stock_%d", s+1)
		names[code] = name
		bars := make([]DailyBar, numBars)
		for i := 0; i < numBars; i++ {
			ci := float64(i)
			bars[i] = DailyBar{
				Date:      fmt.Sprintf("2025-01-%02d", i+1),
				Close:     100 + ci*0.5,
				Open:      100 + ci*0.5 - 0.5,
				High:      100 + ci*0.5 + 0.5,
				Low:       100 + ci*0.5 - 1.0,
				Volume:    20000,
				LastClose: 100 + ci*0.5 - 1.0,
				Ma5:       99 + ci*0.5,
				Ma10:      98 + ci*0.5,
				Ma20:      97 + ci*0.5,
				Ma5Vol:    10000,
				High20:    100 + ci*0.5 - 5.0,
				Low20:     100 + ci*0.5 - 10.0,
				Rsi:       55.0,
				Atr:       2.0,
				Adx:       25.0,
				Amplitude: 0.05,
			}
		}
		stocks[code] = bars
	}
	return stocks, names
}

func TestBacktest_1Candidate10Stocks30Days(t *testing.T) {
	stocks, names := genBacktestStocks(10, 30)
	payload := InputPayload{
		Stocks: stocks,
		Names:  names,
		Candidates: []CandidateRule{
			{
				ID:            "cand-001",
				BuyCondition:  "price > 0",
				SellCondition: "price > 0",
				RiskCondition: "price < 0",
				BacktestDays:  30,
			},
		},
		StartDate:  "2025-01-01",
		EndDate:    "2025-01-30",
		WarmupDays: 5,
	}

	results := ValidateAllCandidates(payload)
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	r := results[0]
	if r.CompositeScore <= -1 {
		t.Fatalf("expected composite_score > -1, got %v", r.CompositeScore)
	}
	if r.Trades < 1 {
		t.Fatalf("expected trades >= 1, got %d", r.Trades)
	}
	if !r.ValidationPassed {
		t.Fatal("expected validation_passed=true")
	}
}

func TestBacktest_InvalidRule(t *testing.T) {
	stocks, names := genBacktestStocks(3, 20)
	payload := InputPayload{
		Stocks: stocks,
		Names:  names,
		Candidates: []CandidateRule{
			{
				ID:            "cand-bad",
				BuyCondition:  "price >>> 10",
				SellCondition: "price > 0",
				RiskCondition: "price < 0",
				BacktestDays:  20,
			},
		},
		StartDate:  "2025-01-01",
		EndDate:    "2025-01-20",
		WarmupDays: 0,
	}

	results := ValidateAllCandidates(payload)
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	r := results[0]
	if r.CompositeScore != -999 {
		t.Fatalf("expected composite_score -999 for invalid rule, got %v", r.CompositeScore)
	}
}

func TestBacktest_RiskPreventsDoubleSell(t *testing.T) {
	stocks, names := genBacktestStocks(5, 25)
	payload := InputPayload{
		Stocks: stocks,
		Names:  names,
		Candidates: []CandidateRule{
			{
				ID:            "cand-risk",
				BuyCondition:  "price > 0",
				SellCondition: "price > 0",
				RiskCondition: "price > 0",
				BacktestDays:  25,
			},
		},
		StartDate:  "2025-01-01",
		EndDate:    "2025-01-25",
		WarmupDays: 5,
	}

	results := ValidateAllCandidates(payload)
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	r := results[0]
	if r.Trades <= 0 {
		t.Fatalf("expected trades > 0, got %d", r.Trades)
	}
	if r.Trades >= 40 {
		t.Fatalf("trades=%d suggests double-sell (risk+sell same position)", r.Trades)
	}
}
