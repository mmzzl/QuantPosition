import http from '@/utils/http'

export function getPermissions() {
  return http.get('/permissions')
}

export function createPermission(name, description, menu_path, menu_label) {
  return http.post('/permissions', {
    name,
    description,
    menu_path,
    menu_label
  })
}

export function deletePermission(permissionId) {
  return http.delete(`/permissions/${permissionId}`)
}