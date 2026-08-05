<template>
  <div class="dashboard">
    <!-- 欢迎与时间 -->
    <div class="welcome-bar">
      <div class="welcome-text">
        <h1 class="welcome-title">{{ username }}，{{ welcomeSubtitle }}</h1>
      </div>
      <div class="welcome-time">
        <div class="time-display font-mono">{{ currentTime }}</div>
        <div class="date-display">{{ currentDate }}</div>
      </div>
    </div>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card" @click="$router.push('/holdings')">
        <div class="kpi-left">
          <div class="kpi-label">持仓数量</div>
          <div class="kpi-value font-mono">{{ stats.holdings_count || 0 }}</div>
          <div class="kpi-unit">只</div>
        </div>
        <div class="kpi-icon-wrap">
          <svg class="kpi-icon" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/>
            <rect x="12" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/>
            <rect x="3" y="12" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/>
            <rect x="12" y="12" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/>
          </svg>
        </div>
      </div>

      <div class="kpi-card" @click="$router.push('/holdings/summary')">
        <div class="kpi-left">
          <div class="kpi-label">总市值</div>
          <div class="kpi-value font-mono">{{ fmt(stats.market_value) }}</div>
          <div class="kpi-unit">元</div>
        </div>
        <div class="kpi-icon-wrap accent-blue">
          <svg class="kpi-icon" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M5 17L9 12L13 15L17 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="17" cy="8" r="1.5" fill="currentColor"/>
          </svg>
        </div>
      </div>

      <div class="kpi-card" :class="{ 'kpi-profit': (stats.unrealized_pnl || 0) > 0, 'kpi-loss': (stats.unrealized_pnl || 0) < 0 }" @click="$router.push('/holdings/summary')">
        <div class="kpi-left">
          <div class="kpi-label">未实现盈亏</div>
          <div class="kpi-value font-mono" :class="(stats.unrealized_pnl || 0) >= 0 ? 'text-up' : 'text-down'">
            {{ (stats.unrealized_pnl || 0) >= 0 ? '+' : '' }}{{ fmt(Math.abs(stats.unrealized_pnl || 0)) }}
          </div>
          <div class="kpi-unit">元</div>
        </div>
        <div class="kpi-icon-wrap" :class="(stats.unrealized_pnl || 0) >= 0 ? 'accent-up' : 'accent-down'">
          <svg class="kpi-icon" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path :d="(stats.unrealized_pnl || 0) >= 0 ? 'M6 12L10 7L14 11L18 5' : 'M6 7L10 12L14 8L18 14'" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path :d="(stats.unrealized_pnl || 0) >= 0 ? 'M15 5H18V8' : 'M15 14H18V11'" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-left">
          <div class="kpi-label">账户角色</div>
          <div class="kpi-value" style="font-size: 18px;">{{ isAdmin ? '管理员' : '用户' }}</div>
          <div class="kpi-unit">权限</div>
        </div>
        <div class="kpi-icon-wrap accent-purple">
          <svg class="kpi-icon" width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M4 19C4 15.6863 7.13401 13 11 13C14.866 13 18 15.6863 18 19" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <circle cx="11" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="actions-section">
      <div class="actions-grid">
        <button class="action-btn" @click="$router.push('/holdings/buy')">
          <span class="action-icon a-buy">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 3V15M3 9H15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </span>
          <span>买入</span>
        </button>
        <button class="action-btn" @click="$router.push('/holdings')">
          <span class="action-icon a-list">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 4H16M2 9H16M2 14H16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </span>
          <span>持仓列表</span>
        </button>
        <button class="action-btn" @click="$router.push('/holdings/history')">
          <span class="action-icon a-history">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="6.5" stroke="currentColor" stroke-width="1.5"/><path d="M9 5V9L11.5 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          </span>
          <span>历史记录</span>
        </button>
        <button class="action-btn" @click="$router.push('/holdings/summary')">
          <span class="action-icon a-summary">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 14V9M7 14V3M12 14V10M17 14V7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
          </span>
          <span>组合汇总</span>
        </button>
        <button class="action-btn" v-if="isAdmin" @click="$router.push('/admin/users')">
          <span class="action-icon a-admin">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="6" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M3 15.5C3 12.5 5.5 10 9 10C12.5 10 15 12.5 15 15.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          </span>
          <span>用户管理</span>
        </button>
        <button class="action-btn" v-if="isAdmin" @click="$router.push('/admin/roles')">
          <span class="action-icon a-roles">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2L10.5 6.5H15.5L11.5 9.5L13 14L9 11L5 14L6.5 9.5L2.5 6.5H7.5L9 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span>角色管理</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getUserInfo } from '@/utils/auth'
import { getPortfolio } from '@/api/holdings'

const userInfo = getUserInfo() || {}
const username = computed(() => userInfo.username || '用户')
const isAdmin = computed(() => userInfo.role === 'admin')

const stats = ref({ holdings_count: 0, market_value: 0, unrealized_pnl: 0 })
const currentTime = ref('')
const currentDate = ref('')
let timeTimer = null

const welcomeSubtitle = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 9) return '盘前准备'
  if (h < 12) return '早盘交易中'
  if (h < 13) return '午间休市'
  if (h < 15) return '午后交易中'
  if (h < 18) return '收盘复盘'
  return '晚间研究'
})

function updateTime() {
  const now = new Date()
  currentTime.value = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
  const w = ['周日','周一','周二','周三','周四','周五','周六']
  currentDate.value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${w[now.getDay()]}`
}

function fmt(n) {
  if (n == null) return '0.00'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchStats() {
  try { const r = await getPortfolio(); stats.value = r.data || {} } catch (e) {}
}

onMounted(() => { updateTime(); timeTimer = setInterval(updateTime, 1000); fetchStats() })
onUnmounted(() => { if (timeTimer) clearInterval(timeTimer) })
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 18px; }

/* 欢迎栏 */
.welcome-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 24px;
  background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.welcome-title { font-size: 17px; font-weight: 600; color: var(--text-primary); }
.time-display { font-size: 24px; font-weight: 700; color: var(--accent); letter-spacing: 1px; }
.date-display { font-size: 12px; color: var(--text-muted); text-align: right; margin-top: 2px; }

/* KPI 卡片 */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.kpi-card {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px;
  background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  cursor: pointer; transition: all 0.2s;
}
.kpi-card:hover { border-color: var(--accent); box-shadow: var(--shadow-md); transform: translateY(-1px); }
.kpi-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 6px; }
.kpi-value { font-size: 24px; font-weight: 700; color: var(--text-primary); line-height: 1; }
.kpi-unit { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

.kpi-icon-wrap {
  width: 40px; height: 40px; border-radius: 8px;
  background: var(--accent-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.kpi-icon-wrap.accent-up { background: var(--up-soft); color: var(--up); }
.kpi-icon-wrap.accent-down { background: var(--down-soft); color: var(--down); }
.kpi-icon-wrap.accent-purple { background: rgba(99, 102, 241, 0.1); color: #6366f1; }
.kpi-icon-wrap.accent-blue { background: rgba(8, 145, 178, 0.1); color: #0891b2; }

.kpi-card.kpi-profit { border-left: 3px solid var(--up); }
.kpi-card.kpi-loss { border-left: 3px solid var(--down); }

/* 快捷操作 */
.actions-section {
  background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm); padding: 20px 24px;
}
.actions-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
.action-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 14px 8px; border-radius: var(--radius-sm);
  border: 1px solid transparent; background: transparent;
  cursor: pointer; font-size: 13px; font-family: var(--font-ui); font-weight: 500;
  color: var(--text-secondary); transition: all 0.2s;
}
.action-btn:hover { background: var(--bg-hover); border-color: var(--border); color: var(--text-primary); transform: translateY(-1px); }
.action-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: transform 0.2s;
}
.action-btn:hover .action-icon { transform: scale(1.08); }
.a-buy { background: var(--up-soft); color: var(--up); }
.a-list { background: rgba(8, 145, 178, 0.1); color: #0891b2; }
.a-history { background: var(--accent-soft); color: var(--accent); }
.a-summary { background: rgba(99, 102, 241, 0.1); color: #6366f1; }
.a-admin { background: var(--down-soft); color: var(--down); }
.a-roles { background: rgba(244, 114, 182, 0.1); color: #db2777; }

@media (max-width: 1024px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .actions-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
