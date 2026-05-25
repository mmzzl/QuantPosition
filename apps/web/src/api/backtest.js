import http from '@/utils/http'

export function submitSimpleBacktest(params = {}) {
  return http.post('/backtest/simple', null, { params })
}

export function submitRuleBacktest(params = {}) {
  return http.post('/backtest/with-rules', null, { params })
}

export function getBacktestTaskStatus(taskId) {
  return http.get(`/backtest/task/${taskId}`)
}
