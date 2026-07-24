import http from '@/utils/http'

export function runHeatmapSelection() {
  return http.post('/heatmap-selection/run')
}

export function getTaskStatus(taskId) {
  return http.get(`/heatmap-selection/task/${taskId}`)
}

export function getHeatmapSelection(params = {}) {
  return http.get('/heatmap-selection', { params })
}
