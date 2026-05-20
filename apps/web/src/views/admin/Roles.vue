<template>
  <div class="roles-page">
    <div class="page-header">
      <h2>角色管理</h2>
      <el-button type="primary" @click="handleAdd">添加角色</el-button>
    </div>

    <el-card>
      <el-table :data="roles" v-loading="loading" stripe>
        <el-table-column prop="name" label="角色名" width="150">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.role_type === 'preset'" type="warning" size="small" style="margin-left: 4px">预设</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="permissions" label="权限数量" width="100">
          <template #default="{ row }">
            {{ row.permission_ids?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)" :disabled="row.locked">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)" :disabled="row.role_type === 'preset'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '添加角色'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="角色名">
          <el-input v-model="form.name" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="继承角色">
          <el-select v-model="form.parent_roles" multiple placeholder="选择继承的角色" style="width: 100%">
            <el-option
              v-for="role in availableRoles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="权限">
          <div class="permission-tree">
            <div v-for="menu in permissionGroups" :key="menu.path" class="permission-group">
              <div class="permission-group-header">
                <el-checkbox
                  :model-value="isGroupAllSelected(menu)"
                  @change="toggleGroup(menu)"
                  :indeterminate="isGroupPartiallySelected(menu)"
                >
                  <span class="menu-label">{{ menu.label }}</span>
                  <span class="menu-path">{{ menu.path }}</span>
                </el-checkbox>
              </div>
              <div class="permission-group-items">
                <el-checkbox
                  v-for="perm in menu.permissions"
                  :key="perm.id"
                  :model-value="form.permission_ids.includes(perm.id)"
                  @change="togglePermission(perm.id)"
                >
                  {{ perm.description || perm.name }}
                </el-checkbox>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRoles, createRole, updateRole, deleteRole } from '@/api/roles'
import { getPermissions } from '@/api/permissions'

const loading = ref(false)
const saving = ref(false)
const roles = ref([])
const availablePermissions = ref([])
const availableRoles = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)

const form = reactive({
  id: '',
  name: '',
  description: '',
  parent_roles: [],
  permission_ids: []
})

const permissionGroups = computed(() => {
  const groups = {}
  for (const perm of availablePermissions.value) {
    const path = perm.menu_path || '/other'
    const label = perm.menu_label || path
    if (!groups[path]) {
      groups[path] = { path, label, permissions: [] }
    }
    groups[path].permissions.push(perm)
  }
  return Object.values(groups)
})

function isGroupAllSelected(menu) {
  if (menu.permissions.length === 0) return false
  return menu.permissions.every(p => form.permission_ids.includes(p.id))
}

function isGroupPartiallySelected(menu) {
  const selected = menu.permissions.filter(p => form.permission_ids.includes(p.id)).length
  return selected > 0 && selected < menu.permissions.length
}

function toggleGroup(menu) {
  if (isGroupAllSelected(menu)) {
    form.permission_ids = form.permission_ids.filter(id => !menu.permissions.some(p => p.id === id))
  } else {
    const ids = menu.permissions.map(p => p.id)
    form.permission_ids = [...new Set([...form.permission_ids, ...ids])]
  }
}

function togglePermission(permId) {
  const idx = form.permission_ids.indexOf(permId)
  if (idx >= 0) {
    form.permission_ids.splice(idx, 1)
  } else {
    form.permission_ids.push(permId)
  }
}

async function fetchRoles() {
  loading.value = true
  try {
    const res = await getRoles()
    roles.value = (res.data || []).map(r => ({
      id: r.id,
      name: r.name,
      role_type: r.role_type || 'custom',
      preset_key: r.preset_key,
      locked: r.locked || false,
      description: r.description || '',
      parent_roles: r.parent_roles || [],
      permission_ids: r.permission_ids || []
    }))
    availableRoles.value = roles.value.filter(r => r.id !== form.id)
  } catch (e) {
    ElMessage.error('获取角色列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchPermissions() {
  try {
    const res = await getPermissions()
    availablePermissions.value = (res.data.items || res.data || []).map(p => ({
      id: p.id,
      name: p.name,
      description: p.description,
      menu_path: p.menu_path,
      menu_label: p.menu_label
    }))
  } catch (e) {
    console.error('获取权限列表失败', e)
  }
}

function handleAdd() {
  isEdit.value = false
  form.id = ''
  form.name = ''
  form.description = ''
  form.parent_roles = []
  form.permission_ids = []
  dialogVisible.value = true
}

function handleEdit(row) {
  if (row.locked) {
    ElMessage.warning('该角色不允许编辑')
    return
  }

  if (row.preset_key === 'super_admin') {
    ElMessage.warning('超级管理员角色不允许编辑')
    return
  }

  isEdit.value = true
  form.id = row.id
  form.name = row.name
  form.description = row.description
  form.parent_roles = [...(row.parent_roles || [])]
  form.permission_ids = [...(row.permission_ids || [])]
  dialogVisible.value = true
}

async function confirmSave() {
  saving.value = true
  try {
    if (isEdit.value) {
      await updateRole(form.id, {
        description: form.description,
        parent_roles: form.parent_roles,
        permission_ids: form.permission_ids
      })
    } else {
      await createRole({
        name: form.name,
        description: form.description,
        parent_roles: form.parent_roles,
        permission_ids: form.permission_ids
      })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchRoles()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function handleDelete(row) {
  if (row.role_type === 'preset') {
    ElMessage.warning('预设角色不允许删除')
    return
  }

  ElMessageBox.confirm(`确定要删除角色 ${row.name} 吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteRole(row.id)
      ElMessage.success('删除成功')
      fetchRoles()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchRoles()
  fetchPermissions()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.permission-tree {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
}

.permission-group {
  margin-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 10px;
}

.permission-group:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.permission-group-header {
  font-weight: 600;
  margin-bottom: 5px;
}

.menu-path {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
  margin-left: 8px;
}

.permission-group-items {
  padding-left: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>