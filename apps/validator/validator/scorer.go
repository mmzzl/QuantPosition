package validator

type PriceVolumeScore struct {
	Total        int
	MaTrend      int
	VolumePrice  int
	Breakthrough int
	Amplitude    int
}

const (
	pvVolHighThreshold    = 1.2
	pvDropVolThreshold    = 1.5
	pvHighPosVolThreshold = 1.3
	pvStageGainThreshold  = 0.30
	pvGainTodayThreshold  = 0.005
	pvDropPctThreshold    = -0.05
	pvAmpLow              = 0.03
	pvAmpHigh             = 0.08
	pvAmpLow2             = 0.02
	pvAmpHigh2            = 0.12
)

func PrecomputePVScores(stocks map[string][]DailyBar, allDates []string) map[string]map[string]PriceVolumeScore {
	scores := make(map[string]map[string]PriceVolumeScore)
	for code, bars := range stocks {
		scores[code] = make(map[string]PriceVolumeScore)
		for i, bar := range bars {
			scores[code][bar.Date] = calcPV(bars, i)
		}
	}
	return scores
}

func calcPV(bars []DailyBar, i int) PriceVolumeScore {
	bar := bars[i]
	close := bar.Close
	ma5 := bar.Ma5
	ma10 := bar.Ma10
	ma20 := bar.Ma20
	vol5 := bar.Ma5Vol

	maTrend := 0
	if ma5 > ma10 && ma10 > ma20 && close > ma5 {
		maTrend = 15
	} else if close > ma5 {
		maTrend = 5
		if ma5 > ma10 {
			maTrend += 5
		}
	} else if close > ma10 && ma10 > ma20 {
		maTrend = 2
	}

	volumePrice := 0
	if i >= 2 {
		day3ago := bars[0].Close
		if i >= 3 {
			day3ago = bars[i-3].Close
		}
		if close > day3ago {
			volumePrice += 4
		}
		if vol5 > 0 && bar.Volume > vol5*pvVolHighThreshold {
			volumePrice += 4
		}
		hasRetracement := false
		allLowVolume := true
		if i >= 1 && bars[i-1].Close < bars[i].Close {
			hasRetracement = true
			if bars[i-1].Volume >= vol5 {
				allLowVolume = false
			}
		}
		if i >= 2 && bars[i-2].Close < bars[i-1].Close {
			hasRetracement = true
			if bars[i-2].Volume >= vol5 {
				allLowVolume = false
			}
		}
		if hasRetracement && allLowVolume {
			volumePrice += 4
		}
	}

	breakthrough := 0
	if i >= 19 {
		high20 := 0.0
		for j := 0; j < 20; j++ {
			if bars[i-j].Close > high20 {
				high20 = bars[i-j].Close
			}
		}
		if close >= high20 {
			breakthrough = 8
		}
	}
	if breakthrough == 0 && i >= 9 {
		high10 := 0.0
		for j := 0; j < 10; j++ {
			if bars[i-j].Close > high10 {
				high10 = bars[i-j].Close
			}
		}
		if close >= high10 {
			breakthrough = 4
		}
	}

	amplitude := 0
	ampSum := 0.0
	ampCount := 0
	for j := 0; j < 5 && i-j >= 0; j++ {
		a := bars[i-j].Amplitude
		if a > 0 {
			ampSum += a
			ampCount++
		}
	}
	if ampCount > 0 {
		avgAmp := ampSum / float64(ampCount)
		if avgAmp >= pvAmpLow && avgAmp <= pvAmpHigh {
			amplitude = 5
		} else if (avgAmp >= pvAmpLow2 && avgAmp < pvAmpLow) || (avgAmp > pvAmpHigh && avgAmp <= pvAmpHigh2) {
			amplitude = 3
		}
	}

	total := maTrend + volumePrice + breakthrough + amplitude
	if total > 40 {
		total = 40
	}

	if penaltyBelowMa20(bars, i, ma20, close) {
		total = 0
	} else if penaltyConsecutiveDrop(bars, i, vol5) {
		total = 0
	} else if penaltyHighPosition(bars, i, close, vol5) {
		total = 0
	}

	return PriceVolumeScore{
		Total:        total,
		MaTrend:      maTrend,
		VolumePrice:  volumePrice,
		Breakthrough: breakthrough,
		Amplitude:    amplitude,
	}
}

func penaltyBelowMa20(bars []DailyBar, i int, ma20, close float64) bool {
	if i < 2 {
		return false
	}
	return ma20 > 0 && close < ma20
}

func penaltyConsecutiveDrop(bars []DailyBar, i int, vol5 float64) bool {
	if i < 2 || vol5 <= 0 {
		return false
	}
	recent3 := []DailyBar{bars[i], bars[i-1], bars[i-2]}
	totalDropPct := (recent3[0].Close - recent3[2].Close) / recent3[2].Close
	if totalDropPct >= pvDropPctThreshold {
		return false
	}
	for _, k := range recent3 {
		if k.Volume <= vol5*pvDropVolThreshold {
			return false
		}
	}
	return true
}

func penaltyHighPosition(bars []DailyBar, i int, close float64, vol5 float64) bool {
	if i < 19 {
		return false
	}
	price20dAgo := bars[i-19].Close
	if price20dAgo <= 0 {
		return false
	}
	stageGain := (close - price20dAgo) / price20dAgo
	if stageGain <= pvStageGainThreshold {
		return false
	}
	if vol5 <= 0 || bars[i].Volume <= vol5*pvHighPosVolThreshold {
		return false
	}
	gainToday := (close - bars[i-1].Close) / bars[i-1].Close
	return gainToday < pvGainTodayThreshold
}
