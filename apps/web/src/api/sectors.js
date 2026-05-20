import http from '@/utils/http'

export function getSectorHeatmap(params = {}) {
  return http.get('/sectors/heatmap', { params })
}

export function getSectorStocks(sectorName, params = {}) {
  return http.get(`/sectors/${encodeURIComponent(sectorName)}/stocks`, { params })
}

export function getKlineData(code, params = {}) {
  return http.get(`/sectors/kline/${encodeURIComponent(code)}`, { params })
}
