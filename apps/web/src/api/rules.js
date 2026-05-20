import http from '@/utils/http'

export function getRules(params = {}) {
  return http.get('/rules', { params })
}

export function createRule(data) {
  return http.post('/rules', data)
}

export function getRule(ruleId) {
  return http.get(`/rules/${ruleId}`)
}

export function updateRule(ruleId, data) {
  return http.put(`/rules/${ruleId}`, data)
}

export function deleteRule(ruleId) {
  return http.delete(`/rules/${ruleId}`)
}

export function batchDeleteRules(ruleIds) {
  return http.post('/rules/batch-delete', { rule_ids: ruleIds })
}
