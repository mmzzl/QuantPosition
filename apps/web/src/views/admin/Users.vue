<template>
  <div class="users-page">
    <div class="page-header">
      <h2>用户管理</h2>
    </div>

    <el-card>
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索用户名" style="width: 200px" clearable @input="fetchUsers" />
        <el-button type="primary" style="margin-left: 10px" @click="fetchUsers">搜索</el-button>
      </div>

      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="email" label="邮箱" width="180" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" @click="handleChangePassword(row)">改密</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑用户" width="400px">
      <el-form :model="editForm" :rules="editRules" ref="editFormRef" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option v-for="role in rolesList" :key="role.id" :label="role.name" :value="role.preset_key || role.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 修改密码对话框 -->
    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="400px">
      <el-form :model="passwordForm" label-width="80px">
        <el-form-item label="旧密码">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmChangePassword" :loading="changingPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, updateUser, deleteUser, changePassword } from '@/api/users'
import { getRoles } from '@/api/roles'
import { getUserId } from '@/utils/auth'

const loading = ref(false)
const saving = ref(false)
const changingPwd = ref(false)
const users = ref([])
const search = ref('')
const rolesList = ref([])

const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editForm = reactive({
  id: '',
  username: '',
  email: '',
  role: 'user',
  is_active: true
})

const editRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ]
}

const passwordDialogVisible = ref(false)
const passwordForm = reactive({
  id: '',
  old_password: '',
  new_password: '',
  confirm_password: ''
})

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await getUsers()
    users.value = (res.data || []).map(u => ({
      id: u.id,
      username: u.username,
      email: u.email || '',
      role: u.role || 'user',
      is_active: u.is_active,
      created_at: u.created_at
    }))
  } catch (e) {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    const res = await getRoles()
    rolesList.value = (res.data || []).map(r => ({
      id: r.id,
      name: r.name,
      preset_key: r.preset_key
    }))
  } catch (e) {
    console.error('获取角色列表失败', e)
  }
}

function handleEdit(row) {
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.role = row.role
  editForm.is_active = row.is_active
  editDialogVisible.value = true
}

async function confirmEdit() {
  if (!editFormRef.value) return
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }
  
  saving.value = true
  try {
    await updateUser(editForm.id, {
      email: editForm.email,
      role: editForm.role,
      is_active: editForm.is_active
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function handleChangePassword(row) {
  passwordForm.id = row.id
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordDialogVisible.value = true
}

async function confirmChangePassword() {
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.error('两次密码不一致')
    return
  }
  
  changingPwd.value = true
  try {
    await changePassword(passwordForm.id, passwordForm.old_password, passwordForm.new_password)
    ElMessage.success('密码修改成功')
    passwordDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改密码失败')
  } finally {
    changingPwd.value = false
  }
}

function handleDelete(row) {
  ElMessageBox.confirm(`确定要删除用户 ${row.username} 吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteUser(row.id)
      ElMessage.success('删除成功')
      fetchUsers()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
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

.toolbar {
  margin-bottom: 15px;
}
</style>