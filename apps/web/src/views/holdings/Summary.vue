<template>
  <div class="summary-page">
    <div class="page-header">
      <h2>组合汇总</h2>
      <el-button @click="$router.push('/holdings')">返回持仓列表</el-button>
    </div>

    <el-row :gutter="20" v-loading="loading">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">持仓数量</div>
          <div class="stat-value">{{ portfolio.holdings_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">总成本</div>
          <div class="stat-value">{{ (portfolio.total_cost || 0).toFixed(2) }}</div>
          <div class="stat-unit">元</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">总市值</div>
          <div class="stat-value">{{ (portfolio.market_value || 0).toFixed(2) }}</div>
          <div class="stat-unit">元</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">未实现盈亏</div>
          <div class="stat-value" :class="portfolio.unrealized_pnl >= 0 ? 'profit' : 'loss'">
            {{ (portfolio.unrealized_pnl || 0).toFixed(2) }}
          </div>
          <div class="stat-unit">元</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" v-loading="loading" style="margin-top: 20px">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">盈亏比例</div>
          <div class="stat-value" :class="portfolio.profit_rate >= 0 ? 'profit' : 'loss'">
            {{ (portfolio.profit_rate || 0).toFixed(2) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已实现盈亏</div>
          <div class="stat-value" :class="portfolio.realized_pnl >= 0 ? 'profit' : 'loss'">
            {{ (portfolio.realized_pnl || 0).toFixed(2) }}
          </div>
          <div class="stat-unit">元</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px" v-if="portfolio.holdings?.length">
      <template #header>
        <span>持仓明细</span>
      </template>
      <el-table :data="portfolio.holdings" stripe>
        <el-table-column prop="code" label="股票代码" width="100" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="average_cost" label="成本" width="100">
          <template #default="{ row }">
            {{ row.average_cost?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_price" label="现价" width="100">
          <template #default="{ row }">
            {{ row.current_price?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="market_value" label="市值" width="120">
          <template #default="{ row }">
            {{ row.market_value?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="unrealized_pnl" label="盈亏" width="100">
          <template #default="{ row }">
            <span :class="row.unrealized_pnl >= 0 ? 'profit' : 'loss'">
              {{ row.unrealized_pnl?.toFixed(2) || '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPortfolio } from '@/api/holdings'

const loading = ref(false)
const portfolio = ref({})

async function fetchPortfolio() {
  loading.value = true
  try {
    const res = await getPortfolio()
    portfolio.value = res.data || {}
  } catch (e) {
    ElMessage.error('获取组合汇总失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchPortfolio()
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

.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-unit {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}
</style>