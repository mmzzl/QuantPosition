import http from '@/utils/http'

const TOKEN_KEY = 'access_token'
const USER_INFO_KEY = 'user_info'
const MENU_DATA_KEY = 'menu_data'
const PERMISSIONS_KEY = 'user_permissions'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUserInfo() {
  const info = localStorage.getItem(USER_INFO_KEY)
  return info ? JSON.parse(info) : null
}

export function setUserInfo(userInfo) {
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo))
}

export function removeUserInfo() {
  localStorage.removeItem(USER_INFO_KEY)
}

export function getUserRole() {
  const info = getUserInfo()
  return info ? info.role : null
}

export function getUserId() {
  const info = getUserInfo()
  return info ? info.id : null
}

export function getMenuData() {
  const data = localStorage.getItem(MENU_DATA_KEY)
  return data ? JSON.parse(data) : null
}

export function setMenuData(menuData) {
  localStorage.setItem(MENU_DATA_KEY, JSON.stringify(menuData))
}

export function removeMenuData() {
  localStorage.removeItem(MENU_DATA_KEY)
}

export function getUserPermissions() {
  const perms = localStorage.getItem(PERMISSIONS_KEY)
  return perms ? JSON.parse(perms) : []
}

export function setUserPermissions(permissions) {
  localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(permissions))
}

export function removeUserPermissions() {
  localStorage.removeItem(PERMISSIONS_KEY)
}

export async function fetchUserMenus() {
  const token = getToken()
  if (!token) return []

  try {
    const response = await http.get('/permissions/menus')
    console.log('API response:', response.data)
    const menus = response.data.menus || []
    console.log('menus extracted:', menus)
    setMenuData(menus)
    return menus
  } catch (e) {
    console.error('Failed to fetch menus', e)
    return []
  }
}

export async function fetchUserPermissions() {
  const token = getToken()
  if (!token) return []

  try {
    const rolesRes = await http.get('/users/me/roles')
    const roles = rolesRes.data || []
    const allPerms = []

    for (const role of roles) {
      try {
        const permRes = await http.get(`/roles/${role.id}/effective-permissions`)
        const perms = permRes.data.effective_permissions || []
        allPerms.push(...perms.map(p => p.name))
      } catch (e) {
        console.error('Failed to fetch role permissions', e)
      }
    }

    const uniquePerms = [...new Set(allPerms)]
    setUserPermissions(uniquePerms)
    return uniquePerms
  } catch (e) {
    console.error('Failed to fetch permissions', e)
    return []
  }
}

export function hasPermission(permission) {
  const perms = getUserPermissions()
  return perms.includes(permission)
}

export function logout() {
  removeToken()
  removeUserInfo()
  removeMenuData()
  removeUserPermissions()
}