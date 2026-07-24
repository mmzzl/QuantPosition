import http from '@/utils/http'

export function getNewsStocks(params = {}) {
  return http.get('/news-selection/stocks', { params })
}

export function runNewsSelection() {
  return http.post('/news-selection/run')
}

export function getNewsTaskStatus(taskId) {
  return http.get(`/news-selection/task/${taskId}`)
}

