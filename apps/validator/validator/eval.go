package validator

import "fmt"

func Eval(node *Node, ctx map[string]float64) (float64, error) {
	if node == nil {
		return 0, fmt.Errorf("nil node")
	}
	switch node.Type {
	case NodeNum:
		return node.Value, nil
	case NodeVar:
		if ctx == nil {
			return 0, nil
		}
		return ctx[node.Name], nil
	case NodeOp:
		return evalOp(node, ctx)
	default:
		return 0, fmt.Errorf("unknown node type: %v", node.Type)
	}
}

func boolVal(v float64) bool {
	return v != 0
}

func evalOp(node *Node, ctx map[string]float64) (float64, error) {
	switch node.Op {
	case "not":
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if boolVal(right) {
			return 0, nil
		}
		return 1, nil
	case "and":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		if !boolVal(left) {
			return 0, nil
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if boolVal(right) {
			return 1, nil
		}
		return 0, nil
	case "or":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		if boolVal(left) {
			return 1, nil
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if boolVal(right) {
			return 1, nil
		}
		return 0, nil
	case "+":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		return left + right, nil
	case "-":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		return left - right, nil
	case "*":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		return left * right, nil
	case "/":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if right == 0 {
			return 0, nil
		}
		return left / right, nil
	case ">":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left > right {
			return 1, nil
		}
		return 0, nil
	case ">=":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left >= right {
			return 1, nil
		}
		return 0, nil
	case "<":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left < right {
			return 1, nil
		}
		return 0, nil
	case "<=":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left <= right {
			return 1, nil
		}
		return 0, nil
	case "==":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left == right {
			return 1, nil
		}
		return 0, nil
	case "!=":
		left, err := Eval(node.Left, ctx)
		if err != nil {
			return 0, err
		}
		right, err := Eval(node.Right, ctx)
		if err != nil {
			return 0, err
		}
		if left != right {
			return 1, nil
		}
		return 0, nil
	default:
		return 0, fmt.Errorf("unknown operator: %s", node.Op)
	}
}
