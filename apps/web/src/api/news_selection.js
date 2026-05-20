import http from '@/utils/http'

export function getNewsStocks(params = {}) {
  return http.get('/news-selection/stocks', { params })
}

export function runNewsSelection() {
  return http.post('/news-selection/run')
}

