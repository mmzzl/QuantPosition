package validator

import (
	"math"
	"sort"
	"strings"
	"sync"
)

const commission = 0.001

type buyCandidate struct {
	Code    string
	Name    string
	Score   int
	MaTrend int
}

func ValidateAllCandidates(payload InputPayload) []CandidateResult {
	allDates := extractAllDates(payload.Stocks)
	sort.Strings(allDates)

	dateIndex := buildDateIndex(payload.Stocks)
	pvCache := PrecomputePVScores(payload.Stocks, allDates)

	startIdx := 0
	endIdx := len(allDates) - 1
	if payload.StartDate != "" {
		for idx, d := range allDates {
			if d >= payload.StartDate {
				startIdx = idx
				break
			}
		}
	}
	if payload.EndDate != "" {
		for idx, d := range allDates {
			if d > payload.EndDate {
				endIdx = idx - 1
				break
			}
		}
	}

	warmupIdx := startIdx + payload.WarmupDays
	if warmupIdx > endIdx {
		warmupIdx = endIdx
	}

	candidateResults := make([]CandidateResult, len(payload.Candidates))

	var wg sync.WaitGroup
	for ci, cand := range payload.Candidates {
		wg.Add(1)
		go func(ci int, cand CandidateRule) {
			defer wg.Done()
			buyNode, errBuy := Parse(cand.BuyCondition)
			sellNode, errSell := Parse(cand.SellCondition)
			riskNode, errRisk := Parse(cand.RiskCondition)
			if errBuy != nil || errSell != nil || errRisk != nil {
				candidateResults[ci] = CandidateResult{
					CandidateID:      cand.ID,
					CompositeScore:   -999,
					Trades:           0,
					ValidationPassed: false,
				}
				return
			}

			startCash := 100000.0
			cash := startCash
			var pos *position
			var trades []trade
			equity := []float64{startCash}

			for di := warmupIdx; di <= endIdx; di++ {
				dateStr := allDates[di]
				var posValue float64
				if pos != nil {
					bar := getBar(pos.Code, dateStr, payload.Stocks, dateIndex)
					if bar != nil {
						posValue = float64(pos.Shares) * bar.Close
					} else {
						posValue = float64(pos.Shares) * pos.Cost
					}
				}
				equity = append(equity, cash+posValue)

				if pos != nil {
					ctx := buildContext(pos.Code, dateStr, payload.Stocks, dateIndex, pos, payload.Names)
					if ctx == nil {
						continue
					}

					sold := false
					riskVal, _ := Eval(riskNode, ctx)
					if riskVal != 0 {
						sellPrice := ctx["price"]
						proceed := float64(pos.Shares) * sellPrice * (1 - commission)
						pnlPct := (sellPrice - pos.Cost) / pos.Cost * 100
						holdDays := calcHoldDays(pos.BuyDate, dateStr)
						stockName := payload.Names[pos.Code]
						if stockName == "" {
							stockName = pos.Code
						}
						trades = append(trades, trade{
							Code:       pos.Code,
							Name:       stockName,
							EntryDate:  pos.BuyDate,
							ExitDate:   dateStr,
							EntryPrice: pos.Cost,
							ExitPrice:  sellPrice,
							PnlPct:     pnlPct,
							HoldDays:   holdDays,
							Reason:     "risk",
						})
						cash += proceed
						pos = nil
						sold = true
					}

					if !sold {
						sellVal, _ := Eval(sellNode, ctx)
						if sellVal != 0 {
							sellPrice := ctx["price"]
							proceed := float64(pos.Shares) * sellPrice * (1 - commission)
							pnlPct := (sellPrice - pos.Cost) / pos.Cost * 100
							holdDays := calcHoldDays(pos.BuyDate, dateStr)
							stockName := payload.Names[pos.Code]
							if stockName == "" {
								stockName = pos.Code
							}
							trades = append(trades, trade{
								Code:       pos.Code,
								Name:       stockName,
								EntryDate:  pos.BuyDate,
								ExitDate:   dateStr,
								EntryPrice: pos.Cost,
								ExitPrice:  sellPrice,
								PnlPct:     pnlPct,
								HoldDays:   holdDays,
								Reason:     "sell",
							})
							cash += proceed
							pos = nil
						}
					}
				}

				if pos == nil {
					var candidates []buyCandidate
					for code := range payload.Stocks {
						bar := getBar(code, dateStr, payload.Stocks, dateIndex)
						if bar == nil {
							continue
						}
						if bar.Ma5 <= bar.Ma10 {
							continue
						}
						pvs, ok := pvCache[code][dateStr]
						if !ok || pvs.Total <= 0 {
							continue
						}

						ctx := map[string]float64{
							"price":      bar.Close,
							"vol":        bar.Volume,
							"ma5":        bar.Ma5,
							"ma10":       bar.Ma10,
							"ma20":       bar.Ma20,
							"ma60":       bar.Ma60,
							"ma5_vol":    bar.Ma5Vol,
							"last_close": bar.LastClose,
							"high":       bar.High,
							"low":        bar.Low,
							"open":       bar.Open,
							"rsi":        bar.Rsi,
							"atr":        bar.Atr,
							"adx":        bar.Adx,
							"amplitude":  bar.Amplitude,
							"has_pos":    0,
							"cost":       0,
							"buy_date":   0,
							"today":      dateToFloat(dateStr),
						}

						buyVal, err := Eval(buyNode, ctx)
						if err != nil || buyVal == 0 {
							continue
						}
						stockName := payload.Names[code]
						if stockName == "" {
							stockName = code
						}
						candidates = append(candidates, buyCandidate{
							Code:    code,
							Name:    stockName,
							Score:   pvs.Total,
							MaTrend: pvs.MaTrend,
						})
					}

					if len(candidates) > 0 {
						sort.Slice(candidates, func(a, b int) bool {
							if candidates[a].Score != candidates[b].Score {
								return candidates[a].Score > candidates[b].Score
							}
							return candidates[a].MaTrend > candidates[b].MaTrend
						})

						best := candidates[0]
						bar := getBar(best.Code, dateStr, payload.Stocks, dateIndex)
						if bar != nil {
							price := bar.Close
							shares := int(cash / (price * (1 + commission)))
							if shares >= 100 {
								costTotal := float64(shares) * price * (1 + commission)
								pos = &position{
									Code:      best.Code,
									Cost:      price,
									BuyDate:   dateStr,
									Shares:    shares,
									CostTotal: costTotal,
								}
								cash -= costTotal
							}
						}
					}
				}
			}

			if pos != nil {
				lastBar := getBar(pos.Code, allDates[endIdx], payload.Stocks, dateIndex)
				if lastBar != nil {
					sellPrice := lastBar.Close
					proceed := float64(pos.Shares) * sellPrice * (1 - commission)
					pnlPct := (sellPrice - pos.Cost) / pos.Cost * 100
					holdDays := calcHoldDays(pos.BuyDate, allDates[endIdx])
					stockName := payload.Names[pos.Code]
					if stockName == "" {
						stockName = pos.Code
					}
					trades = append(trades, trade{
						Code:       pos.Code,
						Name:       stockName,
						EntryDate:  pos.BuyDate,
						ExitDate:   allDates[endIdx],
						EntryPrice: pos.Cost,
						ExitPrice:  sellPrice,
						PnlPct:     pnlPct,
						HoldDays:   holdDays,
						Reason:     "liquidate",
					})
					cash += proceed
					pos = nil
				}
			}

			lastEquity := cash
			equity = append(equity, lastEquity)
			candidateResults[ci] = calcMetrics(cand.ID, trades, equity, startCash)
		}(ci, cand)
	}
	wg.Wait()

	return candidateResults
}

func getBar(code, date string, stocks map[string][]DailyBar, dateIndex map[string]map[string]int) *DailyBar {
	idxMap, ok := dateIndex[code]
	if !ok {
		return nil
	}
	idx, ok := idxMap[date]
	if !ok {
		return nil
	}
	bars := stocks[code]
	if idx < 0 || idx >= len(bars) {
		return nil
	}
	return &bars[idx]
}

func extractAllDates(stocks map[string][]DailyBar) []string {
	seen := make(map[string]bool)
	for _, bars := range stocks {
		for _, bar := range bars {
			seen[bar.Date] = true
		}
	}
	result := make([]string, 0, len(seen))
	for d := range seen {
		result = append(result, d)
	}
	return result
}

func buildDateIndex(stocks map[string][]DailyBar) map[string]map[string]int {
	idx := make(map[string]map[string]int)
	for code, bars := range stocks {
		m := make(map[string]int, len(bars))
		for i, bar := range bars {
			m[bar.Date] = i
		}
		idx[code] = m
	}
	return idx
}

func buildContext(code, date string, stocks map[string][]DailyBar, dateIndex map[string]map[string]int, pos *position, names map[string]string) map[string]float64 {
	bar := getBar(code, date, stocks, dateIndex)
	if bar == nil {
		return nil
	}
	ctx := map[string]float64{
		"price":      bar.Close,
		"vol":        bar.Volume,
		"ma5":        bar.Ma5,
		"ma10":       bar.Ma10,
		"ma20":       bar.Ma20,
		"ma60":       bar.Ma60,
		"ma5_vol":    bar.Ma5Vol,
		"last_close": bar.LastClose,
		"high":       bar.High,
		"low":        bar.Low,
		"open":       bar.Open,
		"rsi":        bar.Rsi,
		"atr":        bar.Atr,
		"adx":        bar.Adx,
		"amplitude":  bar.Amplitude,
		"today":      dateToFloat(date),
	}
	if pos != nil {
		ctx["has_pos"] = 1
		ctx["cost"] = pos.Cost
		ctx["buy_date"] = dateToFloat(pos.BuyDate)
	} else {
		ctx["has_pos"] = 0
		ctx["cost"] = 0
		ctx["buy_date"] = 0
	}
	return ctx
}

func dateToFloat(dateStr string) float64 {
	s := strings.ReplaceAll(dateStr, "-", "")
	if len(s) < 8 {
		return 0
	}
	val := 0.0
	for _, c := range s {
		val = val*10 + float64(c-'0')
	}
	return val
}

func calcHoldDays(buyDate, sellDate string) int {
	buy := strings.ReplaceAll(buyDate, "-", "")
	sell := strings.ReplaceAll(sellDate, "-", "")
	return max(0, int(parseFloatDate(sell)-parseFloatDate(buy)))
}

func parseFloatDate(s string) float64 {
	if len(s) < 8 {
		return 0
	}
	v := 0.0
	for _, c := range s {
		v = v*10 + float64(c-'0')
	}
	return v
}

func calcMetrics(id string, trades []trade, equity []float64, initCash float64) CandidateResult {
	if len(trades) < 5 {
		return CandidateResult{
			CandidateID:      id,
			CompositeScore:   -999,
			Trades:           len(trades),
			ValidationPassed: false,
		}
	}

	finalValue := equity[len(equity)-1]
	totalReturn := (finalValue - initCash) / initCash * 100

	dailyReturns := make([]float64, 0, len(equity)-1)
	for i := 1; i < len(equity); i++ {
		if equity[i-1] > 0 {
			dailyReturns = append(dailyReturns, (equity[i]-equity[i-1])/equity[i-1])
		}
	}

	sharpe := 0.0
	if len(dailyReturns) > 1 {
		mean, std := meanStd(dailyReturns)
		if std > 0 {
			sharpe = mean / std * math.Sqrt(252)
		}
	} else if len(dailyReturns) == 1 {
		sharpe = dailyReturns[0] * math.Sqrt(252)
	}

	winCount := 0
	for _, t := range trades {
		if t.PnlPct > 0 {
			winCount++
		}
	}
	winRate := float64(winCount) / float64(len(trades))

	compositeScore := sharpe * winRate
	if totalReturn > 0 {
		compositeScore *= (1 + totalReturn/100)
	}
	if compositeScore < 0 {
		compositeScore = 0
	}

	return CandidateResult{
		CandidateID:      id,
		CompositeScore:   compositeScore,
		Sharpe:           sharpe,
		PortfolioReturn:  totalReturn,
		WinRate:          winRate,
		Trades:           len(trades),
		ValidationPassed: true,
	}
}

func meanStd(vals []float64) (float64, float64) {
	n := len(vals)
	if n == 0 {
		return 0, 0
	}
	sum := 0.0
	for _, v := range vals {
		sum += v
	}
	mean := sum / float64(n)
	var sqSum float64
	for _, v := range vals {
		d := v - mean
		sqSum += d * d
	}
	std := math.Sqrt(sqSum / float64(n-1))
	return mean, std
}
