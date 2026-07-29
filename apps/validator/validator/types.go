package validator

type DailyBar struct {
	Date      string  `msgpack:"date"`
	Open      float64 `msgpack:"open"`
	Close     float64 `msgpack:"close"`
	High      float64 `msgpack:"high"`
	Low       float64 `msgpack:"low"`
	Volume    float64 `msgpack:"volume"`
	LastClose float64 `msgpack:"last_close"`
	Ma5       float64 `msgpack:"ma5"`
	Ma10      float64 `msgpack:"ma10"`
	Ma20      float64 `msgpack:"ma20"`
	Ma60      float64 `msgpack:"ma60"`
	Ma5Vol    float64 `msgpack:"ma5_vol"`
	High20    float64 `msgpack:"high20"`
	Low20     float64 `msgpack:"low20"`
	Rsi       float64 `msgpack:"rsi"`
	Atr       float64 `msgpack:"atr"`
	Adx       float64 `msgpack:"adx"`
	Amplitude float64 `msgpack:"amplitude"`
}

type CandidateRule struct {
	ID            string `msgpack:"id"`
	BuyCondition  string `msgpack:"buy_condition"`
	SellCondition string `msgpack:"sell_condition"`
	RiskCondition string `msgpack:"risk_condition"`
	BacktestDays  int    `msgpack:"backtest_days"`
}

type CandidateResult struct {
	CandidateID      string  `json:"id"`
	CompositeScore   float64 `json:"composite_score"`
	Sharpe           float64 `json:"sharpe"`
	PortfolioReturn  float64 `json:"portfolio_return"`
	WinRate          float64 `json:"win_rate"`
	Trades           int     `json:"trades"`
	ValidationPassed bool    `json:"validation_passed"`
}

type InputPayload struct {
	Stocks     map[string][]DailyBar `msgpack:"stocks"`
	Candidates []CandidateRule       `msgpack:"candidates"`
	Names      map[string]string     `msgpack:"names"`
	StartDate  string                `msgpack:"start_date"`
	EndDate    string                `msgpack:"end_date"`
	WarmupDays int                   `msgpack:"warmup_days"`
}

type position struct {
	Code      string
	Cost      float64
	BuyDate   string
	Shares    int
	CostTotal float64
}

type trade struct {
	Code       string  `json:"code"`
	Name       string  `json:"name"`
	EntryDate  string  `json:"entry_date"`
	ExitDate   string  `json:"exit_date"`
	EntryPrice float64 `json:"entry_price"`
	ExitPrice  float64 `json:"exit_price"`
	PnlPct     float64 `json:"pnl_pct"`
	HoldDays   int     `json:"hold_days"`
	Reason     string  `json:"reason"`
}
