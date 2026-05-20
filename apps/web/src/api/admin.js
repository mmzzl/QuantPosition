import http from '@/utils/http'

export function getSystemSettings() {
  return http.get('/settings')
}

export function updateSystemSettings(settings) {
  return http.put('/settings', settings)
}
