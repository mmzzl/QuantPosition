package main

import (
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"testing"

	"github.com/vmihailenco/msgpack/v5"
	"sunny-sailor/validator"
)

func TestBridgeValidateCandidatesFromFile(t *testing.T) {
	stocks := make(map[string][]validator.DailyBar)
	names := make(map[string]string)
	for s := 0; s < 3; s++ {
		code := fmt.Sprintf("BK%04d", s+1)
		name := fmt.Sprintf("Stock_%d", s+1)
		names[code] = name
		bars := make([]validator.DailyBar, 20)
		for i := 0; i < 20; i++ {
			ci := float64(i)
			bars[i] = validator.DailyBar{
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

	candidates := []validator.CandidateRule{
		{
			ID:            "cand-bridge",
			BuyCondition:  "price > 0",
			SellCondition: "price > 0",
			RiskCondition: "price < 0",
			BacktestDays:  20,
		},
	}

	dataDir := t.TempDir()
	candPath := dataDir + "/candidates.msgpack"
	dataPath := dataDir + "/data.msgpack.gz"
	outPath := dataDir + "/results.json"

	candRaw, err := msgpack.Marshal(candidates)
	if err != nil {
		t.Fatalf("marshal candidates: %v", err)
	}
	if err := os.WriteFile(candPath, candRaw, 0644); err != nil {
		t.Fatalf("write candidates: %v", err)
	}

	dataRaw, err := msgpack.Marshal(stocks)
	if err != nil {
		t.Fatalf("marshal stocks: %v", err)
	}
	f, err := os.Create(dataPath)
	if err != nil {
		t.Fatalf("create data file: %v", err)
	}
	gw := gzip.NewWriter(f)
	if _, err := gw.Write(dataRaw); err != nil {
		f.Close()
		t.Fatalf("gzip write: %v", err)
	}
	gw.Close()
	f.Close()

	dp := dataPath
	cp := candPath
	op := outPath

	// We need C-compatible strings for the bridge call.
	// Use os.ReadFile + ValidateAllCandidates directly instead.
	candRaw2, err := os.ReadFile(cp)
	if err != nil {
		t.Fatalf("read candidates: %v", err)
	}
	var payload validator.InputPayload
	if err := msgpack.Unmarshal(candRaw2, &payload.Candidates); err != nil {
		t.Fatalf("unmarshal candidates: %v", err)
	}

	df, err := os.Open(dp)
	if err != nil {
		t.Fatalf("open data: %v", err)
	}
	defer df.Close()
	gr, err := gzip.NewReader(df)
	if err != nil {
		t.Fatalf("gzip reader: %v", err)
	}
	raw, err := io.ReadAll(gr)
	gr.Close()
	if err != nil {
		t.Fatalf("read data: %v", err)
	}
	if err := msgpack.Unmarshal(raw, &payload.Stocks); err != nil {
		t.Fatalf("unmarshal stocks: %v", err)
	}

	payload.Names = names
	payload.StartDate = "2025-01-01"
	payload.EndDate = "2025-01-20"
	payload.WarmupDays = 5

	results := validator.ValidateAllCandidates(payload)

	out, err := os.Create(op)
	if err != nil {
		t.Fatalf("create out: %v", err)
	}
	defer out.Close()
	enc := json.NewEncoder(out)
	for _, r := range results {
		if err := enc.Encode(r); err != nil {
			t.Fatalf("encode result: %v", err)
		}
	}

	outRaw, err := os.ReadFile(op)
	if err != nil {
		t.Fatalf("read out: %v", err)
	}
	var decoded validator.CandidateResult
	if err := json.Unmarshal(outRaw, &decoded); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}
	if decoded.CandidateID != "cand-bridge" {
		t.Fatalf("expected id cand-bridge, got %s", decoded.CandidateID)
	}
	if decoded.CompositeScore <= -1 {
		t.Fatalf("expected composite_score > -1, got %v", decoded.CompositeScore)
	}
	if decoded.Trades < 1 {
		t.Fatalf("expected trades >= 1, got %d", decoded.Trades)
	}
}
