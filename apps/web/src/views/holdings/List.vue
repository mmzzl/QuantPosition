<template>
  <div class="holdings-list">
    <div class="page-header">
      <h2>持仓列表</h2>
      <div class="header-actions">
        <el-button type="primary" @click="$router.push('/holdings/buy')">
          <el-icon><Plus /></el-icon>买入
        </el-button>
        <el-button @click="$router.push('/holdings/summary')">
          <el-icon><DataAnalysis /></el-icon>汇总
        </el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="holdings" v-loading="loading" stripe>
        <el-table-column prop="code" label="股票代码" width="100" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="average_cost" label="成本价" width="100">
          <template #default="{ row }">
            {{ row.average_cost?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价" width="100">
          <template #default="{ row }">
            {{ row.current_price?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="market_value" label="市值" width="120">
          <template #default="{ row }">
            {{ row.market_value?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="unrealized_pnl" label="未实现盈亏" width="120">
          <template #default="{ row }">
            <span :class="row.unrealized_pnl >= 0 ? 'profit' : 'loss'">
              {{ row.unrealized_pnl?.toFixed(2) || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="profit_rate" label="盈亏比例" width="100">
          <template #default="{ row }">
            <span :class="row.profit_rate >= 0 ? 'profit' : 'loss'">
              {{ row.profit_rate ? row.profit_rate.toFixed(2) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button size="small" type="primary" @click="handleSell(row)" link>
                <el-icon><Sell /></el-icon> 卖出
              </el-button>
              <el-button size="small" type="warning" @click="handleSetExitRule(row)" link>
                <el-icon><Setting /></el-icon> 止盈/止损
              </el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)" link>
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchHoldings"
        @current-change="fetchHoldings"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <!-- 卖出对话框 -->
    <el-dialog v-model="sellDialogVisible" title="卖出持仓" width="400px">
      <el-form :model="sellForm" label-width="80px">
        <el-form-item label="股票代码">
          <el-input v-model="sellForm.code" disabled />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="sellForm.name" disabled />
        </el-form-item>
        <el-form-item label="持有数量">
          <el-input v-model="sellForm.quantity" disabled />
        </el-form-item>
        <el-form-item label="卖出数量">
          <el-input-number v-model="sellForm.sellQuantity" :min="1" :max="sellForm.quantity" />
        </el-form-item>
        <el-form-item label="卖出价格">
          <el-input-number v-model="sellForm.price" :precision="2" :min="0.01" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sellDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSell" :loading="selling">确定卖出</el-button>
      </template>
    </el-dialog>

    <!-- 止盈止损对话框 -->
    <el-dialog v-model="exitRuleDialogVisible" title="设置止盈止损" width="500px">
      <el-form :model="exitRuleForm" label-width="100px">
        <el-form-item label="策略类型">
          <el-select v-model="exitRuleForm.exit_strategy">
            <el-option label="分档止盈 (tiered)" value="tiered" />
            <el-option label="追踪止损 (trailing)" value="trailing" />
            <el-option label="固定止盈 (fixed)" value="fixed" />
          </el-select>
        </el-form-item>
        <el-form-item label="止损比例">
          <el-input-number v-model="exitRuleForm.stop_loss" :min="0" :max="1" :step="0.01" :precision="2" />
          <span style="margin-left: 10px">例如: 0.05 表示 5%</span>
        </el-form-item>
        <el-form-item label="止盈目标">
          <el-input-number v-model="exitRuleForm.profit_target" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="追踪止损比例" v-if="exitRuleForm.exit_strategy === 'trailing'">
          <el-input-number v-model="exitRuleForm.trailing_stop_pct" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exitRuleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmExitRule" :loading="savingRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DataAnalysis, Sell, Setting, Delete } from '@element-plus/icons-vue'
import { getHoldings, sellHolding, deleteHolding, setExitRule, getStockPrices } from '@/api/holdings'

const router = useRouter()

const loading = ref(false)
const holdings = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

let refreshTimer = null

const sellDialogVisible = ref(false)
const sellForm = reactive({
  code: '',
  name: '',
  quantity: 0,
  sellQuantity: 1,
  price: 0
})
const selling = ref(false)

const exitRuleDialogVisible = ref(false)
const exitRuleForm = reactive({
  code: '',
  exit_strategy: 'tiered',
  stop_loss: 0.05,
  profit_target: 0.10,
  trailing_stop_pct: 0.03
})
const savingRule = ref(false)

async function fetchHoldings() {
  loading.value = true
  try {
    const res = await getHoldings(page.value, pageSize.value)
    holdings.value = (res.data.items || []).map(item => ({
      ...item,
      current_price: null,
      market_value: null,
      unrealized_pnl: null,
      profit_rate: null
    }))
    total.value = res.data.total || 0
    // 获取实时价格
    await refreshPrices()
  } catch (e) {
    ElMessage.error('获取持仓列表失败')
  } finally {
    loading.value = false
  }
}

async function refreshPrices() {
  if (holdings.value.length === 0) return
  const codes = [...new Set(holdings.value.map(h => h.code))]
  try {
    const res = await getStockPrices(codes)
    const prices = res.data.prices || {}
    // 更新持仓数据
    holdings.value = holdings.value.map(h => {
      const priceInfo = prices[h.code] || {}
      const currentPrice = priceInfo.price
      const marketValue = currentPrice ? currentPrice * h.quantity : null
      const unrealizedPnl = currentPrice ? (currentPrice - h.average_cost) * h.quantity : null
      const profitRate = currentPrice ? ((currentPrice - h.average_cost) / h.average_cost * 100) : null
      return {
        ...h,
        name: priceInfo.name || h.name,
        current_price: currentPrice,
        market_value: marketValue ? round(marketValue, 2) : null,
        unrealized_pnl: unrealizedPnl ? round(unrealizedPnl, 2) : null,
        profit_rate: profitRate ? round(profitRate, 2) : null
      }
    })
  } catch (e) {
    // 静默失败
  }
}

function round(num, decimals) {
  const factor = Math.pow(10, decimals)
  return Math.round(num * factor) / factor
}

function handleSell(row) {
  sellForm.code = row.code
  sellForm.name = row.name || ''
  sellForm.quantity = row.quantity
  sellForm.sellQuantity = 1
  sellForm.price = row.current_price || row.average_cost
  sellDialogVisible.value = true
}

async function confirmSell() {
  if (sellForm.sellQuantity > sellForm.quantity) {
    ElMessage.error('卖出数量不能超过持有数量')
    return
  }

  selling.value = true
  try {
    await sellHolding(sellForm.code, sellForm.sellQuantity, sellForm.price)
    ElMessage.success('卖出成功')
    sellDialogVisible.value = false
    fetchHoldings()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '卖出失败')
  } finally {
    selling.value = false
  }
}

function handleSetExitRule(row) {
  exitRuleForm.code = row.code
  exitRuleForm.exit_strategy = row.exit_rule?.exit_strategy || 'tiered'
  exitRuleForm.stop_loss = row.exit_rule?.stop_loss || 0.05
  exitRuleForm.profit_target = row.exit_rule?.profit_target || 0.10
  exitRuleForm.trailing_stop_pct = row.exit_rule?.trailing_stop_pct || 0.03
  exitRuleDialogVisible.value = true
}

async function confirmExitRule() {
  savingRule.value = true
  try {
    await setExitRule(exitRuleForm.code, exitRuleForm)
    ElMessage.success('设置成功')
    exitRuleDialogVisible.value = false
  } catch (e) {
    ElMessage.error('设置失败')
  } finally {
    savingRule.value = false
  }
}

function handleDelete(row) {
  ElMessageBox.confirm(`确定要删除持仓 ${row.code} 吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteHolding(row.code)
      ElMessage.success('删除成功')
      fetchHoldings()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchHoldings()
  // 每 10 秒刷新一次价格
  refreshTimer = setInterval(refreshPrices, 10000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
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

.header-actions {
  display: flex;
  gap: 10px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
}

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}

:deep(.el-table .profit) {
  color: #f56c6c;
}

:deep(.el-table .loss) {
  color: #67c23a;
}
</style>