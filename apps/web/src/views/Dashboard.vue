<template>
  <div class="dashboard">
    <div class="welcome">
      <h2>欢迎，{{ username }}</h2>
      <p>这里是您的持仓管理系统</p>
    </div>

    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card" @click="$router.push('/holdings')">
          <el-icon class="stat-icon" :size="40"><TrendCharts /></el-icon>
          <div class="stat-info">
            <div class="stat-label">持仓数量</div>
            <div class="stat-value">{{ stats.holdings_count }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" @click="$router.push('/holdings/summary')">
          <el-icon class="stat-icon" :size="40"><Money /></el-icon>
          <div class="stat-info">
            <div class="stat-label">总市值</div>
            <div class="stat-value">{{ (stats.market_value || 0).toFixed(2) }}</div>
            <div class="stat-unit">元</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" @click="$router.push('/holdings/summary')">
          <el-icon class="stat-icon" :size="40" :class="stats.unrealized_pnl >= 0 ? 'profit' : 'loss'">
            <TrendCharts />
          </el-icon>
          <div class="stat-info">
            <div class="stat-label">未实现盈亏</div>
            <div class="stat-value" :class="stats.unrealized_pnl >= 0 ? 'profit' : 'loss'">
              {{ (stats.unrealized_pnl || 0).toFixed(2) }}
            </div>
            <div class="stat-unit">元</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-icon class="stat-icon" :size="40"><Medal /></el-icon>
          <div class="stat-info">
            <div class="stat-label">我的角色</div>
            <div class="stat-value">{{ isAdmin ? '管理员' : '普通用户' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>快捷操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/holdings/buy')">
              <el-icon><Plus /></el-icon>买入
            </el-button>
            <el-button @click="$router.push('/holdings')">
              <el-icon><List /></el-icon>持仓列表
            </el-button>
            <el-button @click="$router.push('/holdings/history')">
              <el-icon><Clock /></el-icon>历史记录
            </el-button>
            <el-button @click="$router.push('/holdings/summary')">
              <el-icon><DataAnalysis /></el-icon>组合汇总
            </el-button>
            <el-button v-if="isAdmin" @click="$router.push('/admin/users')">
              <el-icon><User /></el-icon>用户管理
            </el-button>
            <el-button v-if="isAdmin" @click="$router.push('/admin/roles')">
              <el-icon><Setting /></el-icon>角色管理
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUserInfo } from '@/utils/auth'
import { getPortfolio } from '@/api/holdings'

const userInfo = getUserInfo() || {}
const username = computed(() => userInfo.username || '用户')
const isAdmin = computed(() => userInfo.role === 'admin')

const stats = ref({
  holdings_count: 0,
  market_value: 0,
  unrealized_pnl: 0
})

async function fetchStats() {
  try {
    const res = await getPortfolio()
    stats.value = res.data || {}
  } catch (e) {
    // ignore
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.welcome {
  margin-bottom: 30px;
}

.welcome h2 {
  margin: 0 0 10px 0;
  color: #333;
}

.welcome p {
  margin: 0;
  color: #999;
}

.stat-card {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.stat-icon {
  margin-right: 20px;
  color: #409eff;
}

.stat-info {
  flex: 1;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-unit {
  font-size: 12px;
  color: #999;
}

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}

.quick-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>