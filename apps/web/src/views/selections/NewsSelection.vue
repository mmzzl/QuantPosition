<template>
  <div class="news-selection">
    <div class="page-header">
      <h2>新闻选股</h2>
      <div class="controls">
        <el-radio-group v-model="selectedPeriod" @change="onPeriodChange">
          <el-radio-button label="24h">24小时</el-radio-button>
          <el-radio-button label="7d">7天</el-radio-button>
          <el-radio-button label="30d">30天</el-radio-button>
          <el-radio-button label="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="selectedPeriod === 'custom'"
          v-model="dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="fetchData"
          style="margin-left: 10px"
        />
        <el-select v-model="sortBy" @change="fetchData" style="width: 120px; margin-left: 10px">
          <el-option label="预期收益" value="expected_return" />
          <el-option label="当前价" value="current_price" />
          <el-option label="风险" value="risk" />
        </el-select>
        <el-select v-model="sortOrder" @change="fetchData" style="width: 100px; margin-left: 8px">
          <el-option label="降序" value="desc" />
          <el-option label="升序" value="asc" />
        </el-select>
        <el-button type="success" @click="runSelection" :loading="running" style="margin-left: 10px">选股</el-button>
        <el-button @click="fetchData" :loading="loading" style="margin-left: 10px">刷新</el-button>
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
      <el-table :data="stocks" v-loading="loading" stripe>
        <el-table-column prop="code" label="代码" width="90" />
        <el-table-column prop="name" label="名称" width="90" />
        <el-table-column prop="bk_name" label="所属板块" width="120" />
        <el-table-column label="新闻标题" min-width="250">
          <template #default="{ row }">
            <div v-for="(t, i) in (row.news_titles || []).slice(0, 2)" :key="i">
              <el-tooltip :content="t" placement="top">
                <span class="news-title">{{ t }}</span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价" width="90" align="right">
          <template #default="{ row }">{{ row.current_price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="target_price" label="目标价" width="90" align="right">
          <template #default="{ row }">{{ row.target_price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="stop_loss" label="止损价" width="90" align="right">
          <template #default="{ row }">{{ row.stop_loss?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="expected_return" label="预期收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.expected_return >= 0 ? 'profit' : 'loss'">
              {{ row.expected_return >= 0 ? '+' : '' }}{{ row.expected_return }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="risk" label="风险" width="80" align="right">
          <template #default="{ row }">
            <span class="loss">-{{ row.risk }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="信号" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.ma_signal === 'golden_cross'" type="success" size="small">金叉</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showKLine(row)">K线</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <el-dialog v-model="klineDialogVisible" :title="`${selectedStock?.name} (${selectedStock?.code})`" width="800px">
      <KLineChart v-if="klineData.length" :data="klineData" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNewsStocks, runNewsSelection, getNewsTaskStatus } from '@/api/news_selection'
import { getKlineData } from '@/api/sectors'
import KLineChart from '@/views/holdings/KLineChart.vue'

const loading = ref(false)
const running = ref(false)
const stocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedPeriod = ref('24h')
const dateRange = ref([])
const sortBy = ref('expected_return')
const sortOrder = ref('desc')
const taskProgress = ref(null)
let pollTimer = null

const klineDialogVisible = ref(false)
const selectedStock = ref(null)
const klineData = ref([])

async function runSelection() {
  running.value = true
  taskProgress.value = { current: 0, total: 0, status: '提交任务...' }

  try {
    const res = await runNewsSelection()
    const taskId = res.data.task_id

    ElMessage.info('新闻选股任务已提交，正在处理...')
    pollTimer = setInterval(async () => {
      try {
        const sr = await getNewsTaskStatus(taskId)
        const { status, progress, result } = sr.data
        if (status === 'SUCCESS') {
          clearInterval(pollTimer)
          pollTimer = null
          running.value = false
          taskProgress.value = null
          ElMessage.success(`选股完成，共 ${result.total} 条结果`)
          await fetchData()
        } else if (status === 'FAILURE') {
          clearInterval(pollTimer)
          pollTimer = null
          running.value = false
          taskProgress.value = null
          ElMessage.error(`选股失败: ${sr.data.error}`)
        } else if (status === 'PROGRESS') {
          taskProgress.value = progress
        }
      } catch {
        // ignore
      }
    }, 1000)
  } catch (e) {
    ElMessage.error('提交选股任务失败')
    running.value = false
    taskProgress.value = null
  }
}

function onPeriodChange() {
  if (selectedPeriod.value !== 'custom') dateRange.value = []
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    if (selectedPeriod.value === 'custom' && (!dateRange.value || !dateRange.value[0])) return
    const params = {}
    if (selectedPeriod.value === 'custom') {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    } else {
      params.period = selectedPeriod.value
    }
    Object.assign(params, {
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page: page.value,
      page_size: pageSize.value
    })
    const res = await getNewsStocks(params)
    stocks.value = res.data.stocks || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取新闻选股数据失败')
  } finally {
    loading.value = false
  }
}

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

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.news-selection {
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
.news-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 280px;
}
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
