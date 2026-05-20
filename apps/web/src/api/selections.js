import http from '@/utils/http'

export function runDualMASelection() {
  return http.post('/selections/dual-ma')
}

export function getTaskStatus(taskId) {
  return http.get(`/selections/dual-ma/task/${taskId}`)
}

export function getDualMAResults(params = {}) {
  return http.get('/selections/dual-ma', { params })
}
