<template>
  <div class="history-page">
    <div class="page-header">
      <h2>持仓历史</h2>
      <el-button @click="$router.push('/holdings')">返回持仓列表</el-button>
    </div>

    <el-card>
      <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 14px; color: #606266;">排序方式</span>
        <el-select v-model="sortBy" @change="onSortChange" style="width: 140px" size="small">
          <el-option label="时间排序" value="created_at" />
          <el-option label="盈利最好" value="best" />
          <el-option label="亏损最多" value="worst" />
        </el-select>
      </div>

      <el-table :data="transactions" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="code" label="股票代码" width="100" />
        <el-table-column prop="type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'buy' ? 'success' : 'danger'">
              {{ row.type === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="price" label="价格" width="100">
          <template #default="{ row }">
            {{ row.price?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total" label="总额" width="120">
          <template #default="{ row }">
            {{ row.total?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="盈亏" width="120">
          <template #default="{ row }">
            <span v-if="row.realized_pnl != null" :style="{ color: row.realized_pnl >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ row.realized_pnl >= 0 ? '+' : '' }}{{ row.realized_pnl?.toFixed(2) }}
            </span>
            <span v-else style="color: #c0c4cc;">-</span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchHistory"
        @current-change="fetchHistory"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getHistory } from '@/api/holdings'

const loading = ref(false)
const transactions = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const sortBy = ref('created_at')

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

function getSortParams(val) {
  if (val === 'best') return ['realized_pnl', 'desc']
  if (val === 'worst') return ['realized_pnl', 'asc']
  return ['created_at', 'desc']
}

function onSortChange() {
  page.value = 1
  fetchHistory()
}

async function fetchHistory() {
  loading.value = true
  try {
    const [sortField, sortOrder] = getSortParams(sortBy.value)
    const res = await getHistory(page.value, pageSize.value, sortField, sortOrder)
    transactions.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHistory()
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
</style>