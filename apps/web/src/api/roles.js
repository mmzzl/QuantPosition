import http from '@/utils/http'

export function getRoles() {
  return http.get('/roles')
}

export function getRole(roleId) {
  return http.get(`/roles/${roleId}`)
}

export function getRoleEffectivePermissions(roleId) {
  return http.get(`/roles/${roleId}/effective-permissions`)
}

export function createRole(data) {
  return http.post('/roles', data)
}

export function updateRole(roleId, data) {
  return http.put(`/roles/${roleId}`, data)
}

export function deleteRole(roleId) {
  return http.delete(`/roles/${roleId}`)
}