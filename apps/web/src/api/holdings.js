import http from '@/utils/http'
import { getUserId } from '@/utils/auth'

function getUserIdOrDefault() {
  return getUserId() || 'default'
}

export function getHoldings(page = 1, pageSize = 20) {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/${userId}`, {
    params: { page, page_size: pageSize }
  })
}

export function buyHolding(code, name, quantity, averageCost) {
  const userId = getUserIdOrDefault()
  return http.post(`/holdings/${userId}`, {
    code,
    name,
    quantity,
    average_cost: averageCost
  })
}

export function sellHolding(code, quantity, price) {
  const userId = getUserIdOrDefault()
  return http.post(`/holdings/${userId}/${code}/sell`, {
    quantity,
    price
  })
}

export function deleteHolding(code) {
  const userId = getUserIdOrDefault()
  return http.delete(`/holdings/${userId}/${code}`)
}

export function getHistory(page = 1, pageSize = 20) {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/${userId}/history`, {
    params: { page, page_size: pageSize }
  })
}

export function getTransactions(page = 1, pageSize = 20) {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/transactions/${userId}`, {
    params: { page, page_size: pageSize }
  })
}

export function getPortfolio() {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/portfolio/${userId}`)
}

export function getRealizedPnl() {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/pnl/${userId}`)
}

export function getExitRule(code) {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/${userId}/${code}/exit-rule`)
}

export function setExitRule(code, exitRule) {
  const userId = getUserIdOrDefault()
  return http.put(`/holdings/${userId}/${code}/exit-rule`, exitRule)
}

export function getStockPrices(codes) {
  return http.post('/holdings/prices', { codes })
}

export function getAllHoldings(page = 1, pageSize = 20) {
  return http.get('/holdings/admin', {
    params: { page, page_size: pageSize }
  })
}

export function getAllRealizedPnl() {
  return http.get('/holdings/pnl/admin')
}

export function getSectorExposure() {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/${userId}/sector-exposure`)
}

export function getCorrelation() {
  const userId = getUserIdOrDefault()
  return http.get(`/holdings/${userId}/correlation`)
}