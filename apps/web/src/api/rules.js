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

export function validateCondition(condition) {
  return http.post('/rules/validate', { condition })
}

export function getExploreStatus() {
  return http.get('/rules/explore/status')
}

export function startExplore() {
  return http.post('/rules/explore')
}

export function startValidateCandidates(scope = 'all', limit = 500) {
  return http.post('/rules/validate-candidates', { scope, limit })
}

export function applyCandidates() {
  return http.post('/rules/apply-candidates')
}

export function getCandidates(params = {}) {
  return http.get('/rules/candidates', { params })
}

export function deleteCandidate(id) {
  return http.delete(`/rules/candidates/${id}`)
}

export function clearCandidates(scope = 'all') {
  return http.delete('/rules/candidates', { data: { scope } })
}

export function getBlacklist(params = {}) {
  return http.get('/rules/blacklist', { params })
}

export function deleteBlacklist(id) {
  return http.delete(`/rules/blacklist/${id}`)
}

export function applyCandidate(id) {
  return http.post(`/rules/candidates/${id}/apply`)
}

export function getBackups() {
  return http.get('/rules/backup')
}

export function restoreBackup(id) {
  return http.post(`/rules/backup/${id}/restore`)
}
