import http from '@/utils/http'

export function submitSimpleBacktest(params = {}) {
  return http.post('/backtest/simple', null, { params })
}

export function getBacktestTaskStatus(taskId) {
  return http.get(`/backtest/task/${taskId}`)
}

export function getLatestBacktest() {
  return http.get('/backtest/latest')
}

export function getStrategies() {
  return http.get('/backtest/strategies')
}
