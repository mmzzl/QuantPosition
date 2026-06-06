import axios from 'axios'
import { getToken, logout } from './auth'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const http = axios.create({
  baseURL: API_BASE,
  timeout: 10000
})

http.interceptors.request.use(
  config => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

http.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      logout()
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default http
