<template>
  <div class="trading-rules">
    <div class="page-header">
      <h2>交易规则</h2>
      <div>
        <el-button type="danger" :disabled="!selectedIds.length" @click="handleBatchDelete">
          批量删除 ({{ selectedIds.length }})
        </el-button>
        <el-button type="primary" @click="openDialog()">新增</el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="rules" v-loading="loading" stripe @selection-change="onSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="rule_id" label="ID" width="60" />
        <el-table-column prop="name" label="规则名称" min-width="140" />
        <el-table-column prop="type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'buy' ? 'success' : row.type === 'sell' ? 'danger' : 'warning'" size="small">
              {{ { buy: '买入', sell: '卖出', risk: '风控' }[row.type] || row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="70" align="center" />
        <el-table-column prop="weight" label="权重" width="70" align="center">
          <template #default="{ row }">{{ row.weight?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="condition" label="条件" min-width="250">
          <template #default="{ row }">
            <code class="condition-code">{{ row.condition }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="60" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="toggleEnabled(row)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchRules"
        @current-change="fetchRules"
        style="margin-top: 16px; justify-content: center"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新增规则'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="form.name" placeholder="如：放量突破买入" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="buy">买入</el-radio>
            <el-radio value="sell">卖出</el-radio>
            <el-radio value="risk">风控</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width:100%">
            <el-option :value="1" label="1 - 风控最高" />
            <el-option :value="2" label="2 - 卖出" />
            <el-option :value="3" label="3 - 买入" />
          </el-select>
        </el-form-item>
        <el-form-item label="权重">
          <el-input-number v-model="form.weight" :min="0" :max="1" :step="0.05" />
          <span class="hint">达标阈值：卖出 >= 0.5，买入 >= 0.5</span>
        </el-form-item>
        <el-form-item label="条件">
          <div class="condition-builder">
            <div class="var-panel">
              <div class="var-group" v-for="group in varGroups" :key="group.label">
                <div class="var-group-title">{{ group.label }}</div>
                <el-tag
                  v-for="v in group.vars" :key="v.name"
                  size="small"
                  class="var-tag"
                  @click="insertVar(v.name)"
                >
                  <b>{{ v.name }}</b>
                  <span class="var-desc">{{ v.desc }}</span>
                </el-tag>
              </div>
            </div>
            <div class="op-bar">
              <el-button v-for="op in operators" :key="op" size="small" @click="insertVar(op)">{{ op }}</el-button>
            </div>
            <el-input
              ref="conditionRef"
              v-model="form.condition"
              type="textarea"
              :rows="4"
              placeholder="点击上方变量和运算符构建条件"
            />
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRules, createRule, updateRule, deleteRule, batchDeleteRules } from '@/api/rules'

const loading = ref(false)
const saving = ref(false)
const conditionRef = ref(null)

const varGroups = [
  { label: '行情数据', vars: [
    { name: 'price', desc: '最新收盘价' },
    { name: 'vol', desc: '最新成交量' },
    { name: 'ma5', desc: '5日均线' },
    { name: 'ma10', desc: '10日均线' },
    { name: 'ma5_vol', desc: '5日均量' },
    { name: 'last_close', desc: '前一日收盘价' },
    { name: 'high', desc: '20日最高价' },
    { name: 'low', desc: '20日最低价' },
    { name: 'open', desc: '今日开盘价' },
  ]},
  { label: '持仓数据', vars: [
    { name: 'has_pos', desc: '是否持仓 (true/false)' },
    { name: 'cost', desc: '持仓成本' },
    { name: 'buy_date', desc: '买入日期 (如 2026-05-19)' },
    { name: 'today', desc: '当前日期' },
  ]},
]

const operators = ['>', '<', '>=', '<=', '==', '!=', 'and', 'or', 'not', '*', '/', '+', '-', '(', ')']

function insertVar(text) {
  const el = conditionRef.value?.textarea
  if (el) {
    const start = el.selectionStart
    const end = el.selectionEnd
    const before = form.value.condition.substring(0, start)
    const after = form.value.condition.substring(end)
    form.value.condition = before + text + ' ' + after
    setTimeout(() => {
      el.focus()
      el.setSelectionRange(start + text.length + 1, start + text.length + 1)
    })
  } else {
    form.value.condition += (form.value.condition ? ' ' : '') + text
  }
}
const rules = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const selectedIds = ref([])
const dialogVisible = ref(false)
const editing = ref(false)
const form = ref({
  name: '', type: 'buy', priority: 3, weight: 0.35, condition: '', enabled: true
})

function openDialog(row) {
  if (row) {
    editing.value = true
    form.value = { ...row }
  } else {
    editing.value = false
    form.value = { name: '', type: 'buy', priority: 3, weight: 0.35, condition: '', enabled: true }
  }
  dialogVisible.value = true
}

function onSelectionChange(rows) {
  selectedIds.value = rows.map(r => r.rule_id)
}

async function fetchRules() {
  loading.value = true
  try {
    const res = await getRules({ page: page.value, page_size: pageSize.value })
    rules.value = res.data.rules || []
    total.value = res.data.total || 0
  } catch { ElMessage.error('获取规则失败') }
  finally { loading.value = false }
}

async function saveRule() {
  saving.value = true
  try {
    if (editing.value) {
      await updateRule(form.value.rule_id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createRule(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchRules()
  } catch { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该规则？', '提示')
    await deleteRule(row.rule_id)
    ElMessage.success('已删除')
    await fetchRules()
  } catch {}
}

async function handleBatchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 条规则？`, '提示')
    await batchDeleteRules(selectedIds.value)
    ElMessage.success('已批量删除')
    selectedIds.value = []
    await fetchRules()
  } catch {}
}

async function toggleEnabled(row) {
  try {
    await updateRule(row.rule_id, { enabled: !row.enabled })
    row.enabled = !row.enabled
    ElMessage.success(row.enabled ? '已启用' : '已停用')
  } catch { ElMessage.error('操作失败') }
}

onMounted(() => { fetchRules() })
</script>

<style scoped>
.trading-rules { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.condition-code { font-size: 12px; background: #f5f7fa; padding: 2px 6px; border-radius: 3px; }
.hint { font-size: 12px; color: #909399; margin-left: 8px; display: inline-block; }
.condition-builder { width: 100%; }
.var-panel { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.var-group { flex: 1; min-width: 200px; }
.var-group-title { font-size: 12px; color: #909399; margin-bottom: 4px; }
.var-tag { cursor: pointer; margin: 2px 4px 2px 0; }
.var-tag:hover { opacity: 0.8; }
.var-desc { font-size: 11px; color: #909399; margin-left: 4px; font-weight: normal; }
.op-bar { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.op-bar .el-button { padding: 4px 8px; font-size: 12px; }
</style>
