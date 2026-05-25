import http from '@/utils/http'

export function getPaperPositions() {
  return http.get('/paper-trading/positions')
}

export function syncPaperBuy() {
  return http.post('/paper-trading/sync-buy')
}

export function syncPaperSell() {
  return http.post('/paper-trading/sync-sell')
}

export function clearPaper() {
  return http.post('/paper-trading/clear')
}
