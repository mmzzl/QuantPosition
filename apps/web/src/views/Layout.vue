<template>
  <el-container class="layout-container">
    <el-aside width="200px" class="sidebar">
      <div class="logo">
        <h2>{{ siteName }}</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="defaultOpeneds"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <span style="color: #bfcbd9">首页</span>
        </el-menu-item>
        <template v-for="item in filteredMenuItems" :key="item.path">
          <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.path">
            <template #title>
              <span style="color: #bfcbd9">{{ item.label }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
              <span style="color: #bfcbd9">{{ child.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <span style="color: #bfcbd9">{{ item.label }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="username">{{ username }}</span>
          <el-tag v-if="userRole" type="warning" size="small" style="margin-left: 10px">
            {{ roleLabel }}
          </el-tag>
        </div>
        <div class="header-right">
          <el-button type="danger" size="small" @click="handleLogout">
            退出登录
          </el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUserInfo, getMenuData, setMenuData, fetchUserMenus, fetchUserPermissions, logout, getUserRole } from '@/utils/auth'
import { useSite } from '@/utils/site'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()

const { siteName } = useSite()
const userInfo = getUserInfo() || {}
const username = computed(() => userInfo.username || '用户')
const userRole = getUserRole()

const roleLabels = {
  'super_admin': '超级管理员',
  'system_admin': '系统管理员',
  'normal_admin': '普通管理员',
  'admin': '管理员'
}
const roleLabel = computed(() => roleLabels[userRole] || userRole || '')

const menuItems = ref([])
const permissions = ref([])

const filteredMenuItems = computed(() => {
  return menuItems.value.filter(item => {
    if (!item.permission) return true
    return permissions.value.includes(item.permission)
  })
})

const activeMenu = computed(() => route.path)
const defaultOpeneds = computed(() => filteredMenuItems.value.filter(item => item.children && item.children.length > 0).map(item => item.path))

function handleMenuSelect(index) {
  console.log('menu selected:', index)
  router.push(index)
}

async function loadMenus() {
  const menus = await fetchUserMenus()
  if (menus && menus.length > 0) {
    menuItems.value = menus
    setMenuData(menus)
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
.layout-container {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #2b3a4a;
}

.logo h2 {
  color: #fff;
  font-size: 18px;
  margin: 0;
}

.header {
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
}

.username {
  font-size: 16px;
  color: #333;
}

.main-content {
  background-color: #f5f7fa;
  padding: 20px;
}
</style>