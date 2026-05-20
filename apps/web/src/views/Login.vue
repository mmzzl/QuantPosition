<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>{{ siteName }}</h1>
        <p>{{ siteDescription || '股票持仓管理平台' }}</p>
      </div>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" class="login-form">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item prop="captcha">
          <div class="captcha-row">
            <el-input
              v-model="loginForm.captcha"
              placeholder="验证码"
              prefix-icon="CircleCheck"
              size="large"
              style="flex: 1"
            />
            <div class="captcha-img" @click="refreshCaptcha">
              {{ captchaText }}
            </div>
          </div>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <span>还没有账号？</span>
        <router-link to="/register">去注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'
import { setToken, setUserInfo, setMenuData, fetchUserMenus } from '@/utils/auth'
import { useSite } from '@/utils/site'

const router = useRouter()
const { siteName, siteDescription } = useSite()
const loginFormRef = ref(null)
const loading = ref(false)
const rememberMe = ref(false)
const captchaText = ref('ABCD')

const loginForm = reactive({
  username: '',
  password: '',
  captcha: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ],
  captcha: [
    { required: true, message: '请输入验证码', trigger: 'blur' }
  ]
}

function generateCaptcha() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let result = ''
  for (let i = 0; i < 4; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  captchaText.value = result
}

function refreshCaptcha() {
  generateCaptcha()
}

async function handleLogin() {
  if (!loginFormRef.value) return

  try {
    await loginFormRef.value.validate()
  } catch (e) {
    return
  }

  if (loginForm.captcha.toUpperCase() !== captchaText.value) {
    ElMessage.error('验证码错误')
    refreshCaptcha()
    return
  }

  loading.value = true
  try {
    const res = await login(loginForm.username, loginForm.password)
    setToken(res.data.access_token)
    setUserInfo({
      id: res.data.user_id,
      username: loginForm.username,
      role: res.data.role || 'user'
    })
    
    // 获取菜单
    try {
      const menus = await fetchUserMenus()
      console.log('登录后获取的菜单:', menus)
    } catch (menuErr) {
      console.error('获取菜单失败', menuErr)
    }
    
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

generateCaptcha()
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 24px;
  color: #333;
  margin-bottom: 10px;
}

.login-header p {
  font-size: 14px;
  color: #999;
}

.login-form {
  margin-top: 20px;
}

.captcha-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.captcha-img {
  width: 100px;
  height: 40px;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  color: #333;
  cursor: pointer;
  letter-spacing: 4px;
  user-select: none;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  color: #999;
}

.login-footer a {
  color: #409eff;
  text-decoration: none;
  margin-left: 5px;
}
</style>