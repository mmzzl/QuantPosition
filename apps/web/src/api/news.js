import http from '@/utils/http'

export function getNews(params = {}) {
  return http.get('/news', { params })
}
