<template>
  <div class="stock-selection">
    <div class="page-header">
      <h2>双均线选股</h2>
      <div class="controls">
        <el-radio-group v-model="selectedPeriod" @change="fetchResults">
          <el-radio-button label="24h">24小时</el-radio-button>
          <el-radio-button label="7d">7天</el-radio-button>
          <el-radio-button label="30d">30天</el-radio-button>
          <el-radio-button label="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="selectedPeriod === 'custom'"
          v-model="dateRange"
          type="daterange"
          start-placeholder="K线开始日期"
          end-placeholder="K线结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="fetchResults"
          style="margin-left: 10px"
        />
        <el-button type="success" @click="runSelection" :loading="running" style="margin-left: 10px">
          选股
        </el-button>
        <el-button @click="fetchResults" :loading="loading" style="margin-left: 10px">
          刷新
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="taskProgress"
      :title="taskProgress.status"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
    >
      <template #default>
        <el-progress :percentage="taskProgress.total > 0 ? Math.round((taskProgress.current / taskProgress.total) * 100) : 0" />
      </template>
    </el-alert>

    <el-card>
      <div class="table-toolbar">
        <div class="sort-controls">
          <span style="margin-right: 8px">排序：</span>
          <el-select v-model="sortBy" @change="fetchResults" style="width: 120px">
            <el-option label="选股时间" value="selection_date" />
            <el-option label="涨跌幅" value="change_pct" />
            <el-option label="当前价" value="current_price" />
          </el-select>
          <el-select v-model="sortOrder" @change="fetchResults" style="width: 100px; margin-left: 8px">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </div>
      </div>

      <el-table :data="results" v-loading="loading" stripe>
        <el-table-column prop="code" label="股票代码" width="120" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="current_price" label="当前价" width="100">
          <template #default="{ row }">
            {{ row.current_price?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="short_ma" label="短期均线" width="100">
          <template #default="{ row }">
            {{ row.short_ma?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="long_ma" label="长期均线" width="100">
          <template #default="{ row }">
            {{ row.long_ma?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="change_pct" label="区间涨跌幅" width="120">
          <template #default="{ row }">
            <span :class="row.change_pct >= 0 ? 'profit' : 'loss'">
              {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="selection_date" label="选股时间" width="160" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showKLine(row)">K线</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- K线图对话框 -->
      <el-dialog v-model="klineDialogVisible" :title="`${selectedStock?.name} (${selectedStock?.code})`" width="800px">
        <KLineChart v-if="klineData.length" :data="klineData" :title="`${selectedStock?.name} (${selectedStock?.code})`" />
      </el-dialog>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchResults"
        @current-change="fetchResults"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runDualMASelection, getTaskStatus, getDualMAResults } from '@/api/selections'
import { getKlineData } from '@/api/sectors'
import { getStockPrices } from '@/api/holdings'
import KLineChart from '@/views/holdings/KLineChart.vue'

const loading = ref(false)
const running = ref(false)
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const selectedPeriod = ref('24h')
const dateRange = ref([])
const sortBy = ref('selection_date')
const sortOrder = ref('desc')
const taskProgress = ref(null)
let pollTimer = null

const klineDialogVisible = ref(false)
const selectedStock = ref(null)
const klineData = ref([])
let priceTimer = null

async function runSelection() {
  running.value = true
  taskProgress.value = { current: 0, total: 0, status: '提交任务...' }
  
  try {
    const res = await runDualMASelection()
    const taskId = res.data.task_id
    
    ElMessage.info('选股任务已提交，正在处理...')
    
    // 开始轮询任务状态
    startPolling(taskId)
  } catch (e) {
    ElMessage.error('提交选股任务失败')
    running.value = false
    taskProgress.value = null
  }
}

function startPolling(taskId) {
  if (pollTimer) clearInterval(pollTimer)
  
  pollTimer = setInterval(async () => {
    try {
      const res = await getTaskStatus(taskId)
      const { status, progress, result } = res.data
      
      if (status === 'SUCCESS') {
        clearInterval(pollTimer)
        pollTimer = null
        running.value = false
        taskProgress.value = null
        ElMessage.success(`选股完成，选出 ${result.total} 只股票`)
        await fetchResults()
      } else if (status === 'FAILURE') {
        clearInterval(pollTimer)
        pollTimer = null
        running.value = false
        taskProgress.value = null
        ElMessage.error(`选股失败: ${res.data.error}`)
      } else if (status === 'PROGRESS') {
        taskProgress.value = progress
      }
    } catch (e) {
      console.error('轮询任务状态失败', e)
    }
  }, 1000)
}

function stopPricePolling() {
  if (priceTimer) {
    clearInterval(priceTimer)
    priceTimer = null
  }
}

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  stopPricePolling()
})

async function showKLine(row) {
  selectedStock.value = row
  klineData.value = []
  klineDialogVisible.value = true

  try {
    const res = await getKlineData(row.code)
    klineData.value = res.data.data || []
  } catch (e) {
    ElMessage.error('获取K线数据失败')
  }
}

async function fetchPrices() {
  if (!results.value.length) return
  const codes = results.value.map(r => r.code)
  try {
    const res = await getStockPrices(codes)
    const prices = res.data.prices || {}
    results.value = results.value.map(r => ({
      ...r,
      current_price: prices[r.code]?.price ?? r.current_price
    }))
  } catch {
    // 静默失败，保持上次价格
  }
}

function startPricePolling() {
  stopPricePolling()
  fetchPrices()
  priceTimer = setInterval(fetchPrices, 300000)
}

async function fetchResults() {
  loading.value = true
  try {
    const params = {
      period: selectedPeriod.value,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value
    }
    if (selectedPeriod.value === 'custom' && dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getDualMAResults(params)
    results.value = res.data.results || []
    total.value = res.data.total || 0
    startPricePolling()
  } catch (e) {
    ElMessage.error('获取选股结果失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchResults()
})

// 页面可见时自动开始/停止轮询
onUnmounted(() => {
  stopPricePolling()
})
</script>

<style scoped>
.stock-selection {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.controls {
  display: flex;
  align-items: center;
}

.table-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

.sort-controls {
  display: flex;
  align-items: center;
}

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}
</style>
