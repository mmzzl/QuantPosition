package validator

import "testing"

func TestParse_PriceGtMa5Mul1_05(t *testing.T) {
	node, err := Parse("price > ma5 * 1.05")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if node.Type != NodeOp {
		t.Fatalf("expected NodeOp, got %v", node.Type)
	}
	if node.Op != ">" {
		t.Fatalf("expected op '>', got %q", node.Op)
	}
	if node.Left == nil || node.Left.Type != NodeVar || node.Left.Name != "price" {
		t.Fatalf("expected left var 'price', got %+v", node.Left)
	}
	if node.Right == nil || node.Right.Type != NodeOp || node.Right.Op != "*" {
		t.Fatalf("expected right op '*', got %+v", node.Right)
	}
	if node.Right.Left == nil || node.Right.Left.Type != NodeVar || node.Right.Left.Name != "ma5" {
		t.Fatalf("expected right.left var 'ma5', got %+v", node.Right.Left)
	}
	if node.Right.Right == nil || node.Right.Right.Type != NodeNum || node.Right.Right.Value != 1.05 {
		t.Fatalf("expected right.right num 1.05, got %+v", node.Right.Right)
	}
}

func TestParse_InvalidOp(t *testing.T) {
	_, err := Parse("price >> ma5")
	if err == nil {
		t.Fatal("expected error for '>>', got nil")
	}
}
