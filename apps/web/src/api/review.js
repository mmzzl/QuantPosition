import http from '@/utils/http'

export function getLatestReview() {
  return http.get('/review/latest')
}

export function getReviewList(page = 1, pageSize = 10) {
  return http.get('/review/list', {
    params: { page, page_size: pageSize }
  })
}

export function getReviewByDate(date) {
  return http.get(`/review/${date}`)
}
