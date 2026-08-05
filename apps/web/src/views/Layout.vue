<template>
  <div class="layout-root">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-brand" @click="sidebarCollapsed = !sidebarCollapsed">
        <svg class="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="4" y="4" width="24" height="24" rx="5" stroke="currentColor" stroke-width="2.5"/>
          <path d="M10 19L14 14L18 17L22 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="22" cy="10" r="1.5" fill="currentColor"/>
        </svg>
        <div class="brand-text" v-show="!sidebarCollapsed">
          <span class="brand-name">{{ siteName }}</span>
          <span class="brand-tag">量化终端</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <!-- 首页 -->
        <div class="nav-item" :class="{ active: activeMenu === '/dashboard' }" @click="handleMenuSelect('/dashboard')">
          <span class="nav-icon-wrap" v-html="iconHome"></span>
          <span v-show="!sidebarCollapsed" class="nav-label">首页</span>
        </div>

        <!-- 动态菜单 -->
        <template v-for="item in filteredMenuItems" :key="item.path">
          <template v-if="item.children && item.children.length > 0">
            <div
              class="nav-group-title"
              :class="{ collapsed: sidebarCollapsed }"
              @click="sidebarCollapsed ? (sidebarCollapsed = false) : toggleGroup(item.path)"
            >
              <span class="nav-icon-wrap" v-html="getMenuIcon(item)"></span>
              <span v-show="!sidebarCollapsed" class="nav-label">{{ item.label }}</span>
              <svg v-show="!sidebarCollapsed" class="nav-arrow" :class="{ expanded: expandedGroups[item.path] !== false }" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <transition name="collapse">
              <div class="nav-children" v-show="expandedGroups[item.path] !== false && !sidebarCollapsed">
                <div
                  v-for="child in item.children"
                  :key="child.path"
                  class="nav-item child"
                  :class="{ active: activeMenu === child.path }"
                  @click="handleMenuSelect(child.path)"
                >
                  <span class="nav-icon-wrap child-icon" v-html="getMenuIcon(child)"></span>
                  <span class="nav-label">{{ child.label }}</span>
                </div>
              </div>
            </transition>
          </template>
          <div v-else class="nav-item" :class="{ active: activeMenu === item.path }" @click="handleMenuSelect(item.path)">
            <span class="nav-icon-wrap" v-html="getMenuIcon(item)"></span>
            <span v-show="!sidebarCollapsed" class="nav-label">{{ item.label }}</span>
          </div>
        </template>
      </nav>

      <div class="sidebar-footer">
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" :class="{ rotated: sidebarCollapsed }">
            <path d="M10 3L6 8L10 13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span v-show="!sidebarCollapsed" class="collapse-text">收起</span>
        </button>
        <div class="status-row" v-show="!sidebarCollapsed">
          <span class="status-dot"></span>
          <span>实时行情</span>
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <div class="breadcrumb">
            <span class="breadcrumb-item" v-for="(part, idx) in breadcrumbs" :key="idx">
              <span v-if="idx > 0" class="breadcrumb-sep">/</span>
              {{ part }}
            </span>
          </div>
        </div>
        <div class="topbar-right">
          <div class="user-info">
            <div class="user-avatar">{{ (username || 'U').charAt(0).toUpperCase() }}</div>
            <span class="user-name">{{ username }}</span>
            <span class="user-role" v-if="userRole">{{ roleLabel }}</span>
          </div>
          <button class="logout-btn" @click="handleLogout">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <path d="M9 11L13 7.5L9 4M13 7.5H5.5M5.5 2H3.5C2.39543 2 1.5 2.89543 1.5 4V11C1.5 12.1046 2.39543 13 3.5 13H5.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </header>

      <main class="content-area">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUserInfo, setMenuData, fetchUserMenus, fetchUserPermissions, logout, getUserRole } from '@/utils/auth'
import { useSite } from '@/utils/site'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()

const { siteName } = useSite()
const userInfo = getUserInfo() || {}
const username = computed(() => userInfo.username || '用户')
const userRole = getUserRole()

const menuItems = ref([])
const permissions = ref([])
const expandedGroups = reactive({})
const sidebarCollapsed = ref(false)

const roleLabels = {
  'super_admin': '超级管理员',
  'system_admin': '系统管理员',
  'normal_admin': '普通管理员',
  'admin': '管理员'
}
const roleLabel = computed(() => roleLabels[userRole] || userRole || '')

const adminKeywords = ['系统管理', '系统', '管理', 'admin', '设置']
const hiddenMenus = ['模拟']

const filteredMenuItems = computed(() => {
  const items = menuItems.value
    .filter(item => {
      if (hiddenMenus.some(k => (item.label || '').includes(k))) return false
      if (!item.permission) return true
      return permissions.value.includes(item.permission)
    })
    .map(item => {
      // 也过滤子菜单中的隐藏项
      if (item.children && item.children.length > 0) {
        const filteredChildren = item.children.filter(child =>
          !hiddenMenus.some(k => (child.label || '').includes(k))
        )
        return { ...item, children: filteredChildren }
      }
      return item
    })
  return [...items].sort((a, b) => {
    const aIsAdmin = adminKeywords.some(k => (a.label || '').includes(k))
    const bIsAdmin = adminKeywords.some(k => (b.label || '').includes(k))
    if (aIsAdmin && !bIsAdmin) return 1
    if (!aIsAdmin && bIsAdmin) return -1
    return 0
  })
})

const activeMenu = computed(() => route.path)

const breadcrumbs = computed(() => {
  const crumbs = ['首页']
  const meta = route.meta
  if (meta && meta.title) crumbs[0] = meta.title
  return crumbs
})

// ============================================
// 图标系统 — 返回完整 SVG 字符串
// ============================================

const svgWrap = (inner, size = 18, strokeW = 1.5) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg"><g stroke="currentColor" stroke-width="${strokeW}" stroke-linecap="round" stroke-linejoin="round">${inner}</g></svg>`

const iconHome = svgWrap('<path d="M2 9L4 7M4 7L9 2L14 7M4 7V16H8M14 7L16 9M14 7V16H10M8 16V11H10V16M8 16H10"/>')

const iconMap = {
  '持仓': svgWrap('<circle cx="9" cy="5" r="2.5"/><rect x="2" y="10" width="14" height="6" rx="1.5"/>'),
  '交易': svgWrap('<path d="M5 13L8 9L11 12L13 10"/><circle cx="13" cy="10" r="1.5"/>'),
  '板块': svgWrap('<rect x="2" y="2" width="6" height="6" rx="1"/><rect x="10" y="2" width="6" height="6" rx="1"/><rect x="2" y="10" width="6" height="6" rx="1"/><rect x="10" y="10" width="6" height="6" rx="1"/>'),
  '买入': svgWrap('<path d="M9 3V15M3 9H15"/>'),
  '卖出': svgWrap('<path d="M3 9H15"/>'),
  '汇总': svgWrap('<path d="M3 15V10M8 15V3M13 15V7"/>'),
  '历史': svgWrap('<circle cx="9" cy="9" r="6.5"/><path d="M9 5V9L11.5 10.5"/>'),
  '选股': svgWrap('<circle cx="9" cy="9" r="7"/><circle cx="9" cy="9" r="2.5" fill="currentColor" stroke="none"/><line x1="14" y1="14" x2="16" y2="16"/>'),
  '策略': svgWrap('<polyline points="2,14 5,10 9,13 12,8 16,12"/><polyline points="12,8 16,8 16,4"/>'),
  '回测': svgWrap('<circle cx="9" cy="9" r="7"/><polyline points="9,5 9,9 12,11"/>'),
  '新闻': svgWrap('<rect x="3" y="3" width="12" height="12" rx="1.5"/><path d="M6 7H12M6 10H10"/>'),
  '规则': svgWrap('<path d="M3 3H15V5H3V3ZM3 7.5H11V9.5H3V7.5ZM3 12H15V14H3V12Z"/>'),
  '模拟': svgWrap('<rect x="2" y="11" width="14" height="5" rx="1"/><path d="M5 11V7L8 3L12 8L14 5V11"/>'),
  '用户': svgWrap('<circle cx="7" cy="5" r="3"/><path d="M1 16C1 12 4 10 7 10C10 10 13 12 13 16"/>'),
  '角色': svgWrap('<path d="M9 2L11 7H16L12 10L14 15L9 11.5L4 15L6 10L2 7H7L9 2Z"/>'),
  '系统': svgWrap('<circle cx="9" cy="9" r="2.5"/><path d="M9 1V3.5M9 14.5V17M1 9H3.5M14.5 9H17"/>'),
  '设置': svgWrap('<circle cx="9" cy="9" r="2.5"/><path d="M9 1V3.5M9 14.5V17M1 9H3.5M14.5 9H17"/>'),
  '热力图': svgWrap(
    '<rect x="2" y="2" width="5" height="5" rx="0.5" fill="currentColor" opacity="0.9" stroke="none"/>' +
    '<rect x="8.5" y="2" width="5" height="5" rx="0.5" fill="currentColor" opacity="0.5" stroke="none"/>' +
    '<rect x="2" y="8.5" width="5" height="5" rx="0.5" fill="currentColor" opacity="0.6" stroke="none"/>' +
    '<rect x="8.5" y="8.5" width="5" height="5" rx="0.5" fill="currentColor" opacity="0.3" stroke="none"/>',
    18, 0
  ),
}

function getMenuIcon(item) {
  const label = item.label || ''
  for (const [key, icon] of Object.entries(iconMap)) {
    if (label.includes(key)) return icon
  }
  return svgWrap('<path d="M4 5H14M4 9H14M4 13H10"/>')
}

function toggleGroup(path) {
  expandedGroups[path] = expandedGroups[path] === false ? true : false
}

function handleMenuSelect(index) {
  if (sidebarCollapsed.value) {
    sidebarCollapsed.value = false
  }
  router.push(index)
}

async function loadMenus() {
  const menus = await fetchUserMenus()
  if (menus && menus.length > 0) {
    menuItems.value = menus
    setMenuData(menus)
    menus.forEach(item => {
      if (item.children && item.children.length > 0) {
        expandedGroups[item.path] = true
      }
    })
  }

  const perms = await fetchUserPermissions()
  permissions.value = perms
}

onMounted(() => {
  loadMenus()
})

function handleLogout() {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    logout()
    router.push('/')
  }).catch(() => {})
}
</script>

<style scoped>
.layout-root {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ============================================
   侧边栏
   ============================================ */
.sidebar {
  width: 210px;
  flex-shrink: 0;
  background: #ffffff;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: 10;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.sidebar.collapsed {
  width: 56px;
}

.sidebar-brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: padding 0.25s;
  flex-shrink: 0;
}

.sidebar.collapsed .sidebar-brand {
  padding: 0 19px;
  justify-content: center;
}

.brand-icon {
  width: 28px;
  height: 28px;
  color: var(--accent);
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  overflow: hidden;
  white-space: nowrap;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.brand-tag {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 10px;
}

.sidebar.collapsed .sidebar-nav {
  padding: 8px 6px;
}

/* — 分组标题 — */
.nav-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
  margin-top: 6px;
  white-space: nowrap;
  border-radius: 6px;
}

.sidebar.collapsed .nav-group-title {
  justify-content: center;
  padding: 10px 0;
  cursor: pointer;
}

.nav-group-title .nav-icon-wrap {
  color: var(--text-muted);
  opacity: 0.7;
}

.sidebar.collapsed .nav-group-title .nav-icon-wrap {
  opacity: 0.5;
}

.nav-group-title:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-group-title:hover .nav-icon-wrap {
  color: var(--text-secondary);
}

.nav-group-title .nav-arrow {
  margin-left: auto;
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.nav-arrow {
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.nav-arrow.expanded {
  transform: rotate(180deg);
}

.nav-children {
  overflow: hidden;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
}

.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}

/* — 通用菜单项 — */
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.15s ease;
  margin-bottom: 1px;
  white-space: nowrap;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px 0;
}

.nav-item.child {
  padding-left: 28px;
  font-size: 13px;
}

.nav-icon-wrap.child-icon {
  width: 16px;
  height: 16px;
  opacity: 0.5;
}

.nav-icon-wrap.child-icon :deep(svg) {
  width: 16px;
  height: 16px;
}

.nav-item.child:hover .nav-icon-wrap {
  color: var(--text-secondary);
}

.nav-item.child.active .nav-icon-wrap {
  color: var(--accent);
}

/* — 图标容器 — */
.nav-icon-wrap {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: var(--text-muted);
  transition: color 0.15s;
}

.nav-icon-wrap :deep(svg) {
  width: 18px;
  height: 18px;
  display: block;
}

.nav-item:hover .nav-icon-wrap {
  color: var(--text-secondary);
}

.nav-item.active .nav-icon-wrap {
  color: var(--accent);
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

.nav-indicator {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ============================================
   底部 — 折叠按钮
   ============================================ */
.sidebar-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar.collapsed .sidebar-footer {
  padding: 10px 0;
  justify-content: center;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 32px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  padding: 0 10px;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-strong);
}

.collapse-btn:active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}

.collapse-btn svg {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.collapse-btn svg.rotated {
  transform: rotate(180deg);
}

.collapse-text {
  font-size: 12px;
  font-weight: 500;
}

.sidebar.collapsed .collapse-btn {
  width: 36px;
  height: 36px;
  padding: 0;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.sidebar.collapsed .status-row {
  display: none;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ============================================
   顶栏
   ============================================ */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.breadcrumb {
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.breadcrumb-sep {
  margin: 0 2px;
  opacity: 0.4;
}

.topbar-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.user-role {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.logout-btn {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  margin-left: 8px;
}

.logout-btn:hover {
  border-color: var(--border-strong);
  color: var(--up);
}

/* ============================================
   内容区
   ============================================ */
.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
</style>
