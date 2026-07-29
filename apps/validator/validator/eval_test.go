package validator

import "testing"

func TestEval_PriceGtMa5Mul1_05_True(t *testing.T) {
	node, err := Parse("price > ma5 * 1.05")
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	ctx := map[string]float64{"price": 10, "ma5": 9}
	result, err := Eval(node, ctx)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if result != 1 {
		t.Fatalf("expected 1 (true), got %v", result)
	}
}

func TestEval_PriceGtMa5Mul1_05_False(t *testing.T) {
	node, err := Parse("price > ma5 * 1.05")
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	ctx := map[string]float64{"price": 9, "ma5": 10}
	result, err := Eval(node, ctx)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if result != 0 {
		t.Fatalf("expected 0 (false), got %v", result)
	}
}
