package validator

import (
	"fmt"
	"strconv"
	"strings"
	"unicode"
)

type NodeType int

const (
	NodeVar NodeType = iota
	NodeNum
	NodeOp
)

type Node struct {
	Type  NodeType
	Value float64
	Name  string
	Op    string
	Left  *Node
	Right *Node
}

type parser struct {
	tokens []string
	pos    int
}

func tokenize(expr string) []string {
	parts := strings.Fields(expr)
	var tokens []string
	for _, p := range parts {
		for len(p) > 0 && p[0] == '(' {
			tokens = append(tokens, "(")
			p = p[1:]
		}
		i := len(p)
		for i > 0 && p[i-1] == ')' {
			i--
		}
		if i > 0 {
			tokens = append(tokens, p[:i])
		}
		for j := i; j < len(p); j++ {
			tokens = append(tokens, ")")
		}
	}
	return tokens
}

func isNumber(s string) bool {
	if s == "" {
		return false
	}
	for i, c := range s {
		if c == '.' {
			continue
		}
		if i == 0 && c == '-' && len(s) > 1 {
			continue
		}
		if !unicode.IsDigit(c) {
			return false
		}
	}
	return true
}

func isOperator(s string) bool {
	switch s {
	case ">", "<", ">=", "<=", "==", "!=", "+", "-", "*", "/", "and", "or", "not":
		return true
	}
	return false
}

func Parse(expr string) (*Node, error) {
	tokens := tokenize(expr)
	if len(tokens) == 0 {
		return nil, fmt.Errorf("empty expression")
	}
	p := &parser{tokens: tokens, pos: 0}
	result, err := p.parseExpr()
	if err != nil {
		return nil, err
	}
	if p.pos < len(p.tokens) {
		return nil, fmt.Errorf("unexpected token: %s", p.tokens[p.pos])
	}
	return result, nil
}

func (p *parser) peek() string {
	if p.pos >= len(p.tokens) {
		return ""
	}
	return p.tokens[p.pos]
}

func (p *parser) consume() string {
	tok := p.peek()
	p.pos++
	return tok
}

func (p *parser) expect(expected string) error {
	tok := p.consume()
	if tok != expected {
		return fmt.Errorf("expected %q, got %q", expected, tok)
	}
	return nil
}

func (p *parser) parseExpr() (*Node, error) {
	left, err := p.parseTerm()
	if err != nil {
		return nil, err
	}
	for p.peek() == "or" {
		op := p.consume()
		right, err := p.parseTerm()
		if err != nil {
			return nil, err
		}
		left = &Node{Type: NodeOp, Op: op, Left: left, Right: right}
	}
	return left, nil
}

func (p *parser) parseTerm() (*Node, error) {
	left, err := p.parseFactor()
	if err != nil {
		return nil, err
	}
	for p.peek() == "and" {
		op := p.consume()
		right, err := p.parseFactor()
		if err != nil {
			return nil, err
		}
		left = &Node{Type: NodeOp, Op: op, Left: left, Right: right}
	}
	return left, nil
}

func (p *parser) parseFactor() (*Node, error) {
	left, err := p.parseComparison()
	if err != nil {
		return nil, err
	}
	for {
		tok := p.peek()
		if tok == ">" || tok == ">=" || tok == "<" || tok == "<=" || tok == "==" || tok == "!=" {
			p.consume()
			right, err := p.parseComparison()
			if err != nil {
				return nil, err
			}
			left = &Node{Type: NodeOp, Op: tok, Left: left, Right: right}
		} else {
			break
		}
	}
	return left, nil
}

func (p *parser) parseComparison() (*Node, error) {
	left, err := p.parseSum()
	if err != nil {
		return nil, err
	}
	for {
		tok := p.peek()
		if tok == "+" || tok == "-" {
			p.consume()
			right, err := p.parseSum()
			if err != nil {
				return nil, err
			}
			left = &Node{Type: NodeOp, Op: tok, Left: left, Right: right}
		} else {
			break
		}
	}
	return left, nil
}

func (p *parser) parseSum() (*Node, error) {
	left, err := p.parseProduct()
	if err != nil {
		return nil, err
	}
	for {
		tok := p.peek()
		if tok == "*" || tok == "/" {
			p.consume()
			right, err := p.parseProduct()
			if err != nil {
				return nil, err
			}
			left = &Node{Type: NodeOp, Op: tok, Left: left, Right: right}
		} else {
			break
		}
	}
	return left, nil
}

func (p *parser) parseProduct() (*Node, error) {
	return p.parseUnary()
}

func (p *parser) parseUnary() (*Node, error) {
	if p.peek() == "not" {
		p.consume()
		right, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return &Node{Type: NodeOp, Op: "not", Left: nil, Right: right}, nil
	}
	return p.parsePrimary()
}

func (p *parser) parsePrimary() (*Node, error) {
	tok := p.peek()
	if tok == "" {
		return nil, fmt.Errorf("unexpected end of expression")
	}
	if tok == "(" {
		p.consume()
		node, err := p.parseExpr()
		if err != nil {
			return nil, err
		}
		if err := p.expect(")"); err != nil {
			return nil, err
		}
		return node, nil
	}
	tok = p.consume()
	if isNumber(tok) {
		val, err := strconv.ParseFloat(tok, 64)
		if err != nil {
			return nil, fmt.Errorf("invalid number: %s", tok)
		}
		return &Node{Type: NodeNum, Value: val}, nil
	}
	if !isOperator(tok) {
		return &Node{Type: NodeVar, Name: tok}, nil
	}
	return nil, fmt.Errorf("unexpected operator: %s", tok)
}
