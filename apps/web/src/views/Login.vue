<template>
  <div class="login-root">
    <!-- 背景：极淡网格 -->
    <div class="bg-pattern"></div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <div class="card-top">
        <svg class="logo-icon" viewBox="0 0 36 36" fill="none">
          <rect x="5" y="5" width="26" height="26" rx="5" stroke="currentColor" stroke-width="2.5"/>
          <path d="M11 20L15 14L19 18L24 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="24" cy="10" r="1.8" fill="currentColor"/>
        </svg>
        <h1 class="login-title">{{ siteName }}</h1>
        <p class="login-sub">专业量化持仓管理终端</p>
      </div>

      <form class="form" @submit.prevent="handleLogin">
        <div class="field">
          <label class="label">用户名</label>
          <div class="input-wrap">
            <svg class="input-icon" viewBox="0 0 16 16" fill="none" width="14" height="14">
              <circle cx="8" cy="5" r="3" stroke="currentColor" stroke-width="1.4"/>
              <path d="M2 14C2 11.2386 4.68629 9 8 9C11.3137 9 14 11.2386 14 14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <input v-model="loginForm.username" class="input" placeholder="请输入用户名" autocomplete="username" />
          </div>
        </div>

        <div class="field">
          <label class="label">密码</label>
          <div class="input-wrap">
            <svg class="input-icon" viewBox="0 0 16 16" fill="none" width="14" height="14">
              <rect x="3" y="7" width="10" height="7" rx="2" stroke="currentColor" stroke-width="1.4"/>
              <path d="M5 7V5C5 3.34315 6.34315 2 8 2C9.65685 2 11 3.34315 11 5V7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <input v-model="loginForm.password" :type="showPwd ? 'text' : 'password'" class="input" placeholder="请输入密码" autocomplete="current-password" @keyup.enter="handleLogin" />
            <button type="button" class="input-suffix" @click="showPwd = !showPwd">
              <svg v-if="!showPwd" viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M1 8C1 8 3.5 3 8 3C12.5 3 15 8 15 8C15 8 12.5 13 8 13C3.5 13 1 8 1 8Z" stroke="currentColor" stroke-width="1.4"/>
                <circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.4"/>
              </svg>
              <svg v-else viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M1 8C1 8 3.5 3 8 3C12.5 3 15 8 15 8C15 8 12.5 13 8 13C3.5 13 1 8 1 8Z" stroke="currentColor" stroke-width="1.4"/>
                <circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.4"/>
                <path d="M2 2L14 14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="field">
          <label class="label">验证码</label>
          <div class="captcha-row">
            <div class="input-wrap" style="flex:1">
              <svg class="input-icon" viewBox="0 0 16 16" fill="none" width="14" height="14">
                <rect x="2" y="2" width="12" height="12" rx="3" stroke="currentColor" stroke-width="1.4"/>
                <path d="M5 8L7 10L11 6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <input v-model="loginForm.captcha" class="input" placeholder="验证码" @keyup.enter="handleLogin" />
            </div>
            <div class="captcha-box" @click="refreshCaptcha">{{ captchaText }}</div>
          </div>
        </div>

        <div class="form-opt">
          <label class="cb">
            <input type="checkbox" v-model="rememberMe" class="cb-input" />
            <span class="cb-mark"></span>
            <span class="cb-text">记住我</span>
          </label>
        </div>

        <button class="submit-btn" :disabled="loading">
          <span v-if="!loading">登 录</span>
          <span v-else class="spinner"></span>
        </button>
      </form>

      <div class="card-foot">
        <span>还没有账号？</span>
        <router-link to="/register" class="link">立即注册</router-link>
      </div>

      <!-- 行情 ticker -->
      <div class="ticker-bar">
        <div class="ticker-track">
          <span v-for="(t, i) in tickerItems" :key="i" class="ticker-item">
            <span class="t-name">{{ t.name }}</span>
            <span class="t-pct" :class="t.up ? 't-up' : 't-down'">{{ t.up ? '+' : '' }}{{ t.pct }}%</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'
import { setToken, setUserInfo, fetchUserMenus } from '@/utils/auth'
import { useSite } from '@/utils/site'

const router = useRouter()
const { siteName } = useSite()
const loading = ref(false)
const rememberMe = ref(false)
const showPwd = ref(false)
const captchaText = ref('ABCD')

const tickerItems = ref([
  { name: '上证指数', pct: 0.52, up: true },
  { name: '深证成指', pct: 0.78, up: true },
  { name: '创业板指', pct: -0.34, up: false },
  { name: '沪深300', pct: 0.41, up: true },
  { name: '科创50', pct: -0.12, up: false },
  { name: '北证50', pct: 1.23, up: true },
])

const loginForm = reactive({ username: '', password: '', captcha: '' })

function generateCaptcha() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let r = ''
  for (let i = 0; i < 4; i++) r += chars.charAt(Math.floor(Math.random() * chars.length))
  captchaText.value = r
}
function refreshCaptcha() { generateCaptcha() }

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) { ElMessage.error('请输入用户名和密码'); return }
  if (loginForm.captcha.toUpperCase() !== captchaText.value) { ElMessage.error('验证码错误'); refreshCaptcha(); return }
  loading.value = true
  try {
    const res = await login(loginForm.username, loginForm.password)
    setToken(res.data.access_token)
    setUserInfo({ id: res.data.user_id, username: loginForm.username, role: res.data.role || 'user' })
    try { await fetchUserMenus() } catch {}
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
    refreshCaptcha()
  } finally { loading.value = false }
}

generateCaptcha()
</script>

<style scoped>
.login-root {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
  background: #f0f4f8;
}

.bg-pattern {
  position: absolute; inset: 0;
  background-image: radial-gradient(#cbd5e1 0.7px, transparent 0.7px);
  background-size: 24px 24px;
  mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 30%, transparent);
  -webkit-mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 30%, transparent);
}

.login-card {
  width: 400px; max-width: 90vw;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 24px rgba(0,0,0,0.06), 0 1px 4px rgba(0,0,0,0.04);
  padding: 36px 32px 24px;
  position: relative; z-index: 1;
  animation: appear 0.5s cubic-bezier(0.16,1,0.3,1);
}
@keyframes appear { from { opacity:0; transform:translateY(12px) scale(0.98); } to { opacity:1; transform:translateY(0) scale(1); } }

.card-top { text-align: center; margin-bottom: 28px; }
.logo-icon { width: 40px; height: 40px; color: var(--accent); margin: 0 auto 12px; display: block; }
.login-title { font-family: var(--font-display); font-size: 22px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.login-sub { font-size: 12px; color: var(--text-muted); }

.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.label { font-size: 12px; font-weight: 500; color: var(--text-secondary); }
.input-wrap {
  display: flex; align-items: center; gap: 8px;
  height: 40px; padding: 0 12px;
  background: var(--bg-elevated); border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  transition: all 0.2s;
}
.input-wrap:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); background: #fff; }
.input-icon { color: var(--text-muted); flex-shrink: 0; }
.input-wrap:focus-within .input-icon { color: var(--accent); }
.input {
  flex:1; background: none; border: none; outline: none; color: var(--text-primary);
  font-size: 13px; font-family: var(--font-ui);
}
.input::placeholder { color: var(--text-muted); }
.input-suffix {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  padding: 2px; display: flex; transition: color 0.15s;
}
.input-suffix:hover { color: var(--text-secondary); }

.captcha-row { display: flex; gap: 10px; }
.captcha-box {
  width: 90px; height: 40px;
  background: var(--bg-elevated); border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 17px; font-weight: 700;
  color: var(--accent); cursor: pointer; letter-spacing: 4px; user-select: none;
  flex-shrink: 0; transition: all 0.2s;
}
.captcha-box:hover { border-color: var(--accent); background: var(--accent-soft); }

.form-opt { display: flex; align-items: center; }
.cb { display: flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }
.cb-input { display: none; }
.cb-mark {
  width: 15px; height: 15px; border: 1.5px solid var(--border-strong); border-radius: 4px;
  transition: all 0.2s; position: relative;
}
.cb-input:checked + .cb-mark { background: var(--accent); border-color: var(--accent); }
.cb-input:checked + .cb-mark::after {
  content:''; position:absolute; top:2px; left:4px;
  width:4px; height:8px; border:solid #fff; border-width:0 2px 2px 0; transform:rotate(45deg);
}
.cb-text { font-size: 13px; color: var(--text-secondary); }

.submit-btn {
  height: 42px; border: none; border-radius: var(--radius-sm);
  background: var(--accent); color: #fff; font-size: 15px; font-weight: 600;
  font-family: var(--font-ui); cursor: pointer;
  box-shadow: 0 2px 8px rgba(37,99,235,0.25);
  transition: all 0.2s; letter-spacing: 2px; margin-top: 4px;
}
.submit-btn:hover:not(:disabled) { background: #1d4ed8; box-shadow: 0 4px 12px rgba(37,99,235,0.35); transform: translateY(-1px); }
.submit-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.spinner {
  display:inline-block; width:18px; height:18px;
  border:2px solid rgba(255,255,255,.3); border-top-color:#fff; border-radius:50%;
  animation:spin .6s linear infinite;
}
@keyframes spin { to { transform:rotate(360deg); } }

.card-foot { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-muted); }
.link { color: var(--accent); text-decoration: none; font-weight: 500; margin-left: 4px; }
.link:hover { text-decoration: underline; }

/* ticker */
.ticker-bar {
  margin: 20px -32px -24px; padding: 10px 0;
  border-top: 1px solid var(--border);
  overflow: hidden;
}
.ticker-track {
  display: flex; gap: 28px;
  animation: scroll 30s linear infinite;
  white-space: nowrap; padding-left: 100%;
}
@keyframes scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
.ticker-item { font-size: 11px; font-family: var(--font-mono); display: flex; gap: 6px; align-items: center; }
.t-name { color: var(--text-muted); }
.t-pct { font-weight: 600; }
.t-up { color: var(--up); }
.t-down { color: var(--down); }
</style>
