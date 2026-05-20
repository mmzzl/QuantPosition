import http from '@/utils/http'

export function login(username, password) {
  return http.post('/auth/login', {
    username,
    password
  })
}

export function register(username, password, email) {
  return http.post('/auth/register', {
    username,
    password,
    email
  })
}

export function getCurrentUser() {
  return http.get('/auth/me')
}

export function getMenu() {
  return http.get('/menu')
}