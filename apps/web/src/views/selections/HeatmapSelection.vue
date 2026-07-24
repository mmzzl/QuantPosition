<template>
  <div class="heatmap-selection">
    <div class="page-header">
      <h2>热力图选股</h2>
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
        <el-select v-model="topN" @change="fetchData" style="width: 130px; margin-left: 10px">
          <el-option label="Top 3 板块" :value="3" />
          <el-option label="Top 5 板块" :value="5" />
          <el-option label="Top 10 板块" :value="10" />
        </el-select>
        <el-button type="success" @click="runSelection" :loading="running" style="margin-left: 10px">
          选股
        </el-button>
        <el-button @click="fetchData" :loading="loading" style="margin-left: 10px">
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
        <el-progress
          :percentage="taskProgress.total > 0 ? Math.round((taskProgress.current / taskProgress.total) * 100) : 0"
        />
      </template>
    </el-alert>

    <el-alert
      v-if="filterSummary.total_raw > 0 && !taskProgress"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
    >
      原始 {{ filterSummary.total_raw }} 只 → 板块内强势排名 + 成交量 + 股价 + 涨幅过滤后 <strong>{{ filterSummary.total_filtered }}</strong> 只
    </el-alert>

    <el-card shadow="never" style="margin-bottom: 20px">
      <template #header>
        <span>强势板块排行</span>
      </template>
      <div class="sector-bar-list">
        <div
          v-for="s in sectors"
          :key="s.sector_name"
          class="sector-bar-item"
        >
          <div class="sector-bar-label">
            <span class="sector-name">{{ s.sector_name }}</span>
            <span class="sector-count">{{ s.stock_count }}只</span>
          </div>
          <div class="sector-bar-track">
            <div
              class="sector-bar-fill"
              :style="{ width: sectorBarWidth(s.avg_change_pct) + '%' }"
              :class="s.avg_change_pct >= 0 ? 'bar-up' : 'bar-down'"
            />
          </div>
          <span class="sector-bar-pct" :class="s.avg_change_pct >= 0 ? 'profit' : 'loss'">
            {{ s.avg_change_pct >= 0 ? '+' : '' }}{{ s.avg_change_pct }}%
          </span>
        </div>
        <el-empty v-if="!sectors.length" description="暂无板块数据" />
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="table-toolbar">
        <div class="sort-controls">
          <span style="margin-right: 8px">排序：</span>
          <el-select v-model="sortBy" @change="fetchData" style="width: 120px">
            <el-option label="综合评分" value="score" />
            <el-option label="涨跌幅" value="change_pct" />
            <el-option label="当前价" value="current_price" />
            <el-option label="成交量" value="volume" />
            <el-option label="板块" value="sector_name" />
            <el-option label="名称" value="name" />
          </el-select>
          <el-select v-model="sortOrder" @change="fetchData" style="width: 100px; margin-left: 8px">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </div>
      </div>

      <el-table :data="stocks" v-loading="loading" stripe>
        <el-table-column label="评分" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.score)" size="small" effect="plain">
              {{ row.score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="90" />
        <el-table-column prop="name" label="名称" width="90" />
        <el-table-column prop="sector_name" label="所属板块" min-width="130" />
        <el-table-column label="板块排名" width="80" align="center">
          <template #default="{ row }">
            <span>{{ row.sector_rank }} ({{ row.sector_rank_pct }}%)</span>
          </template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价" width="90" align="right">
          <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="change_pct" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.change_pct >= 0 ? 'profit' : 'loss'">
              {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="f in (row.flags || [])"
              :key="f"
              size="small"
              :type="flagType(f)"
              style="margin-right: 4px"
            >
              {{ f }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showKLine(row)">K线</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog v-model="klineDialogVisible" :title="`${selectedStock?.name} (${selectedStock?.code})`" width="800px">
        <KLineChart v-if="klineData.length" :data="klineData" />
      </el-dialog>

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
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runHeatmapSelection, getTaskStatus, getHeatmapSelection } from '@/api/heatmap_selection'
import { getKlineData } from '@/api/sectors'
import KLineChart from '@/views/holdings/KLineChart.vue'

const loading = ref(false)
const running = ref(false)
const sectors = ref([])
const stocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const selectedPeriod = ref('24h')
const dateRange = ref([])
const topN = ref(5)
const sortBy = ref('score')
const sortOrder = ref('desc')
const taskProgress = ref(null)
const filterSummary = ref({ total_raw: 0, total_filtered: 0 })
let pollTimer = null

const klineDialogVisible = ref(false)
const selectedStock = ref(null)
const klineData = ref([])

function scoreType(score) {
  if (score >= 70) return 'success'
  if (score >= 40) return 'warning'
  return 'info'
}

function flagType(flag) {
  if (flag === '板块龙头' || flag === '大涨') return 'success'
  if (flag === '巨量活跃' || flag === '中高价') return 'warning'
  return 'info'
}

function sectorBarWidth(pct) {
  const maxVal = Math.max(...sectors.value.map(s => Math.abs(s.avg_change_pct)), 0.01)
  return Math.max(Math.abs(pct) / maxVal * 100, 4)
}

function onPeriodChange() {
  if (selectedPeriod.value !== 'custom') dateRange.value = []
  fetchData()
}

async function runSelection() {
  running.value = true
  taskProgress.value = { current: 0, total: 0, status: '提交任务...' }

  try {
    const res = await runHeatmapSelection()
    const taskId = res.data.task_id

    ElMessage.info('热力图选股任务已提交，正在处理...')

    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(async () => {
      try {
        const sr = await getTaskStatus(taskId)
        const { status, progress, result } = sr.data

        if (status === 'SUCCESS') {
          clearInterval(pollTimer)
          pollTimer = null
          running.value = false
          taskProgress.value = null
          ElMessage.success(result.message)
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

async function fetchData() {
  loading.value = true
  try {
    const params = {
      period: selectedPeriod.value,
      top_n: topN.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page: page.value,
      page_size: pageSize.value
    }
    if (selectedPeriod.value === 'custom' && dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getHeatmapSelection(params)
    sectors.value = res.data.sectors || []
    stocks.value = res.data.stocks || []
    total.value = res.data.total || 0
    filterSummary.value = res.data.filter_summary || { total_raw: 0, total_filtered: 0 }
  } catch (e) {
    ElMessage.error('获取热力图选股数据失败')
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
.heatmap-selection {
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
.sector-bar-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sector-bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.sector-bar-label {
  width: 160px;
  display: flex;
  justify-content: space-between;
  flex-shrink: 0;
}
.sector-name {
  font-size: 13px;
  font-weight: 500;
}
.sector-count {
  font-size: 12px;
  color: #999;
}
.sector-bar-track {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.sector-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}
.bar-up {
  background: linear-gradient(90deg, #f56c6c, #e74c3c);
}
.bar-down {
  background: linear-gradient(90deg, #67c23a, #27ae60);
}
.sector-bar-pct {
  width: 70px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
