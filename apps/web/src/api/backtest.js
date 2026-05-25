import http from '@/utils/http'

export function getSimpleBacktest(params = {}) {
  return http.get('/backtest/simple', { params })
}

export function getRuleBacktest(params = {}) {
  return http.get('/backtest/with-rules', { params })
}
