import http from '@/utils/http'

export function submitBacktest(params = {}) {
  return http.post('/backtest/run', null, { params })
}

export function getTaskStatus(taskId) {
  return http.get(`/backtest/task/${taskId}`)
}

export function getLatestBacktest() {
  return http.get('/backtest/latest')
}

export function getCandidateBacktest(id) {
  return http.get('/rules/candidates/backtest', { params: { id } })
}

export function getOptimizedCandidateBacktest(id) {
  return http.get('/rules/optimized-candidates/backtest', { params: { id } })
}
