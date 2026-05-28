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

    <el-row :gutter="16" style="margin-top:20px">
      <el-col :span="12">
        <el-card v-loading="sectorLoading">
          <template #header><span>板块分布</span></template>
          <div v-if="sectors.length">
            <div v-for="s in sectors" :key="s.sector" class="sector-row">
              <div class="sector-label">{{ s.sector }}</div>
              <el-progress
                :percentage="s.pct"
                :color="s.pct > 30 ? '#f56c6c' : s.pct > 15 ? '#e6a23c' : '#67c23a'"
                :stroke-width="18"
                :format="() => s.pct + '%'"
              />
              <div class="sector-count">{{ s.stock_count }}只</div>
            </div>
          </div>
          <div v-else style="color:#999;text-align:center;padding:20px">暂无持仓或未找到板块信息</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card v-loading="corrLoading">
          <template #header><span>相关性矩阵</span></template>
          <div v-if="corrCodes.length >= 2">
            <div class="corr-header">
              <span></span>
              <span v-for="c in corrCodes" :key="c" class="corr-code">{{ c }}</span>
            </div>
            <div v-for="c1 in corrCodes" :key="c1" class="corr-row">
              <span class="corr-code">{{ c1 }}</span>
              <span
                v-for="c2 in corrCodes"
                :key="c2"
                class="corr-val"
                :style="{ background: corrColor(getCorr(c1, c2)) }"
              >{{ getCorr(c1, c2) }}</span>
            </div>
            <div style="margin-top:8px;font-size:12px;color:#999">
              <span style="background:#f56c6c;padding:2px 6px;margin-right:8px">正相关</span>
              <span style="background:#e6a23c;padding:2px 6px;margin-right:8px">中</span>
              <span style="background:#67c23a;padding:2px 6px">低/负相关</span>
            </div>
          </div>
          <div v-else style="color:#999;text-align:center;padding:20px">
            {{ corrError || '至少需要2只持仓股票' }}
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPortfolio, getSectorExposure, getCorrelation } from '@/api/holdings'

const loading = ref(false)
const portfolio = ref({})
const sectorLoading = ref(false)
const corrLoading = ref(false)
const sectors = ref([])
const corrData = ref([])
const corrCodes = ref([])
const corrError = ref('')

function getCorr(c1, c2) {
  const row = corrData.value.find(r => r.code === c1)
  return row ? row[c2] : 0
}

function corrColor(v) {
  const a = Math.abs(v)
  if (a > 0.6) return '#f56c6c30'
  if (a > 0.3) return '#e6a23c30'
  return '#67c23a30'
}

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

async function fetchSectors() {
  sectorLoading.value = true
  try {
    const res = await getSectorExposure()
    sectors.value = res.data?.sectors || []
  } catch (e) {
    sectors.value = []
  } finally {
    sectorLoading.value = false
  }
}

async function fetchCorrelation() {
  corrLoading.value = true
  corrError.value = ''
  try {
    const res = await getCorrelation()
    if (res.data?.error) {
      corrError.value = res.data.error
      corrData.value = []
      corrCodes.value = []
    } else {
      corrData.value = res.data?.matrix || []
      corrCodes.value = res.data?.codes || []
    }
  } catch (e) {
    corrError.value = '获取失败'
    corrData.value = []
    corrCodes.value = []
  } finally {
    corrLoading.value = false
  }
}

onMounted(() => {
  fetchPortfolio()
  fetchSectors()
  fetchCorrelation()
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