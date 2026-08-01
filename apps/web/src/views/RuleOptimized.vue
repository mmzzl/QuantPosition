<template>
  <div class="rule-optimized">
    <div class="page-header">
      <h2>优化后的候选规则</h2>
      <div>
        <el-button type="primary" @click="handleOptimize" :loading="optimizing">
          开始 LLM 优化
        </el-button>
        <el-button type="danger" @click="handleClear">清空</el-button>
      </div>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-label">优化后总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">任务状态</div>
          <div class="stat-value" style="font-size: 16px">
            <el-tag :type="statusType">{{ statusLabel }}</el-tag>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="label">优化范围</div>
          <el-select v-model="optScope" style="width:100%">
            <el-option label="全部候选" value="all" />
            <el-option label="已验证候选" value="validated" />
            <el-option label="未验证候选" value="unvalidated" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <div class="label">本轮处理条数</div>
          <el-input-number v-model="optLimit" :min="1" :max="5000" style="width:100%" />
        </el-col>
        <el-col :span="6">
          <div class="label">任务进度</div>
          <el-progress :percentage="progressPct" v-if="progressPct > 0" />
          <span v-else style="color:#909399">未运行</span>
        </el-col>
      </el-row>
    </el-card>

    <el-table :data="candidates" v-loading="loading" stripe>
      <el-table-column prop="name" label="名称" width="140" show-overflow-tooltip />
      <el-table-column prop="parent_source" label="来源" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="sourceType(row.parent_source)">{{ row.parent_source }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="买入条件" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <div>
            <div style="color:#999;font-size:12px">原: {{ row.original_buy }}</div>
            <div style="color:#409eff">{{ row.buy_condition }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="卖出条件" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <div>
            <div style="color:#999;font-size:12px">原: {{ row.original_sell }}</div>
            <div style="color:#e6a23c">{{ row.sell_condition }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="风控条件" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <div>
            <div style="color:#999;font-size:12px">原: {{ row.original_risk }}</div>
            <div style="color:#f56c6c">{{ row.risk_condition }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="optimization_note" label="优化说明" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="handleApplySingle(row)">更新规则</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[50, 100, 200]"
      layout="total, sizes, prev, pager, next"
      @size-change="fetchCandidates"
      @current-change="fetchCandidates"
      style="margin-top: 16px; justify-content: center"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getOptimizedCandidates, startOptimizeCandidates,
  deleteOptimizedCandidate, clearOptimizedCandidates, applyOptimizedCandidate,
  getExploreStatus
} from '@/api/rules'

const loading = ref(false)
const optimizing = ref(false)
const candidates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const stats = ref({ total: 0 })
const optScope = ref('all')
const optLimit = ref(500)
const status = ref(null)

function sourceType(s) { return { template: '', llm: 'success', genetic: 'warning' }[s] || 'info' }

const statusLabel = computed(() => {
  const s = status.value
  if (!s) return '未运行'
  if (s.status === 'running') return s.phase_label || '运行中'
  if (s.status === 'done') return s.phase_label || '完成'
  if (s.status === 'error') return s.error_msg || '失败'
  return '空闲'
})
const statusType = computed(() => {
  if (!status.value || status.value.status === 'idle') return 'info'
  if (status.value.status === 'running') return 'warning'
  if (status.value.status === 'done') return 'success'
  if (status.value.status === 'error') return 'danger'
  return 'info'
})
const progressPct = computed(() => {
  const s = status.value
  if (!s || s.status !== 'running') return 0
  const done = s.llm_evolve_done || 0
  const totalRun = s.llm_evolve_total || 0
  if (!totalRun) return 0
  return Math.round(done * 100 / totalRun)
})

let timer = null

async function fetchCandidates() {
  loading.value = true
  try {
    const res = await getOptimizedCandidates({ page: page.value, page_size: pageSize.value })
    candidates.value = res.data.candidates || []
    total.value = res.data.total || 0
  } catch { ElMessage.error('获取优化后规则失败') }
  finally { loading.value = false }
}

async function fetchStats() {
  try {
    const res = await getOptimizedCandidates({ page: 1, page_size: 1 })
    stats.value.total = res.data.total || 0
  } catch {}
}

async function fetchStatus() {
  try {
    const res = await getExploreStatus()
    status.value = res.data
    if (res.data?.status === 'running') {
      fetchStats()
      fetchCandidates()
    }
  } catch {}
}

async function handleOptimize() {
  try {
    optimizing.value = true
    const res = await startOptimizeCandidates(optScope.value, optLimit.value)
    ElMessage.success(res.data.message || '优化任务已启动')
    fetchStatus()
    if (timer) clearInterval(timer)
    timer = setInterval(fetchStatus, 3000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动优化失败')
  } finally { optimizing.value = false }
}

async function handleDelete(row) {
  try {
    await deleteOptimizedCandidate(row._id)
    ElMessage.success('已删除')
    fetchCandidates()
    fetchStats()
  } catch { ElMessage.error('删除失败') }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定清空所有优化后的候选规则？', '提示')
    await clearOptimizedCandidates()
    ElMessage.success('已清空')
    fetchCandidates()
    fetchStats()
  } catch {}
}

async function handleApplySingle(row) {
  try {
    await ElMessageBox.confirm(`确定用「${row.name || '未命名'}」替换当前规则？会自动备份。`, '更新规则')
    const res = await applyOptimizedCandidate(row._id)
    ElMessage.success(res.data.message)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

onMounted(() => {
  fetchCandidates()
  fetchStats()
  fetchStatus()
  timer = setInterval(fetchStatus, 5000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.rule-optimized { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 24px; font-weight: bold; margin-top: 4px; }
.label { font-size: 12px; color: #909399; margin-bottom: 4px; }
</style>
