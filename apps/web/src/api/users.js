import http from '@/utils/http'
import { getUserId } from '@/utils/auth'

export function getUsers() {
  return http.get('/users')
}

export function getUser(userId) {
  return http.get(`/users/${userId}`)
}

export function updateUser(userId, data) {
  return http.put(`/users/${userId}`, data)
}

export function changePassword(userId, oldPassword, newPassword) {
  return http.put(`/users/${userId}/password`, {
    old_password: oldPassword,
    new_password: newPassword
  })
}

export function assignRole(userId, roleId) {
  return http.put(`/users/${userId}/role`, {
    role_id: roleId
  })
}

export function deleteUser(userId) {
  return http.delete(`/users/${userId}`)
}