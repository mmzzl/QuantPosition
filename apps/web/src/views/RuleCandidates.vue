<template>
  <div class="rule-candidates">
    <div class="page-header">
      <h2>候选规则池</h2>
      <div>
        <el-button @click="handleValidate" :loading="validating">验证规则</el-button>
        <el-button type="primary" @click="handleApply" :loading="applying">一键更新规则</el-button>
        <el-button @click="showBlacklist = true">查看黑名单</el-button>
        <el-button type="danger" @click="handleClear">清空候选</el-button>
      </div>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-label">候选总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">已验证</div>
          <div class="stat-value">{{ stats.validated }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">黑名单</div>
          <div class="stat-value">{{ stats.blacklist }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">最优评分</div>
          <div class="stat-value">{{ stats.bestScore }}</div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-select v-model="filter.validation_round" clearable placeholder="验证轮次" style="width:100%">
          <el-option label="待验证" :value="0" />
          <el-option label="快筛通过" :value="1" />
          <el-option label="精测完成" :value="2" />
          <el-option label="已淘汰" :value="-1" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="filter.source" clearable placeholder="来源" style="width:100%">
          <el-option label="模板" value="template" />
          <el-option label="LLM" value="llm" />
          <el-option label="遗传" value="genetic" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-button @click="fetchCandidates">筛选</el-button>
      </el-col>
    </el-row>

    <el-table :data="candidates" v-loading="loading" stripe>
      <el-table-column prop="source" label="来源" width="70">
        <template #default="{ row }">
          <el-tag size="small" :type="sourceType(row.source)">{{ row.source }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="120" show-overflow-tooltip />
      <el-table-column prop="buy_condition" label="买入条件" min-width="180" show-overflow-tooltip />
      <el-table-column prop="sell_condition" label="卖出条件" min-width="180" show-overflow-tooltip />
      <el-table-column prop="risk_condition" label="风控条件" min-width="180" show-overflow-tooltip />
      <el-table-column prop="composite_score" label="综合评分" width="90" sortable />
      <el-table-column prop="validation_round" label="轮次" width="70">
        <template #default="{ row }">
          <el-tag :type="row.validation_round === 2 ? 'success' : row.validation_round === 1 ? 'warning' : 'info'" size="small">
            {{ {0:'待验证', 1:'快筛通过', 2:'精测完成', '-1':'已淘汰'}[row.validation_round] || '-' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
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

    <el-dialog v-model="showBlacklist" title="规则黑名单" width="800px">
      <el-table :data="blacklist" stripe>
        <el-table-column prop="buy_condition" label="买入" min-width="150" show-overflow-tooltip />
        <el-table-column prop="sell_condition" label="卖出" min-width="150" show-overflow-tooltip />
        <el-table-column prop="risk_condition" label="风控" min-width="150" show-overflow-tooltip />
        <el-table-column prop="reason" label="原因" width="100" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" @click="handleRemoveBlacklist(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getCandidates, deleteCandidate, clearCandidates,
  startValidateCandidates, applyCandidates,
  getBlacklist, deleteBlacklist
} from '@/api/rules'

const loading = ref(false)
const validating = ref(false)
const applying = ref(false)
const candidates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const showBlacklist = ref(false)
const blacklist = ref([])
const filter = ref({ validation_round: null, source: null })
const stats = ref({ total: 0, validated: 0, blacklist: 0, bestScore: 0 })

function sourceType(s) { return { template: '', llm: 'success', genetic: 'warning' }[s] || 'info' }

async function fetchCandidates() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filter.value.validation_round !== null) params.validation_round = filter.value.validation_round
    if (filter.value.source) params.source = filter.value.source
    const res = await getCandidates(params)
    candidates.value = res.data.candidates || []
    total.value = res.data.total || 0
  } catch { ElMessage.error('获取候选规则失败') }
  finally { loading.value = false }
}

async function fetchStats() {
  try {
    const [cands, bl] = await Promise.all([
      getCandidates({ page: 1, page_size: 1 }),
      getBlacklist({ page: 1, page_size: 1 }),
    ])
    stats.value.total = cands.data.total || 0
    const validatedRes = await getCandidates({ page: 1, page_size: 1, validated: true })
    stats.value.validated = validatedRes.data.total || 0
    stats.value.blacklist = bl.data.total || 0
    if (validatedRes.data.candidates?.[0]) {
      stats.value.bestScore = validatedRes.data.candidates[0].composite_score || 0
    }
  } catch {}
}

async function fetchBlacklist() {
  try {
    const res = await getBlacklist({ page: 1, page_size: 100 })
    blacklist.value = res.data.blacklist || []
  } catch {}
}

async function handleDelete(row) {
  try {
    await deleteCandidate(row._id)
    ElMessage.success('已删除')
    fetchCandidates()
    fetchStats()
  } catch { ElMessage.error('删除失败') }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定清空所有候选规则？', '提示')
    await clearCandidates('all')
    ElMessage.success('已清空')
    fetchCandidates()
    fetchStats()
  } catch {}
}

async function handleValidate() {
  validating.value = true
  try {
    await startValidateCandidates('all', 500)
    ElMessage.success('验证任务已启动')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动验证失败')
  } finally { validating.value = false }
}

async function handleApply() {
  try {
    await ElMessageBox.confirm('确定用最优候选替换当前规则？会自动备份。', '一键更新')
    applying.value = true
    const res = await applyCandidates()
    ElMessage.success(res.data.message)
    fetchCandidates()
    fetchStats()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally { applying.value = false }
}

async function handleRemoveBlacklist(row) {
  try {
    await deleteBlacklist(row._id)
    ElMessage.success('已移除')
    fetchBlacklist()
    fetchStats()
  } catch { ElMessage.error('移除失败') }
}

onMounted(() => {
  fetchCandidates()
  fetchStats()
  fetchBlacklist()
})
</script>

<style scoped>
.rule-candidates { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 24px; font-weight: bold; margin-top: 4px; }
</style>
