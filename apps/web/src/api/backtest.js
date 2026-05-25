import http from '@/utils/http'

export function submitSimpleBacktest(params = {}) {
  return http.post('/backtest/simple', null, { params })
}

export function getBacktestTaskStatus(taskId) {
  return http.get(`/backtest/task/${taskId}`)
}

export function saveBacktestResult(data) {
  return http.post('/backtest/save', data)
}

export function getLatestBacktest() {
  return http.get('/backtest/latest')
}
