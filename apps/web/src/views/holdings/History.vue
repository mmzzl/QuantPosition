<template>
  <div class="history-page">
    <div class="page-header">
      <h2>持仓历史</h2>
      <el-button @click="$router.push('/holdings')">返回持仓列表</el-button>
    </div>

    <el-card>
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

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getHistory(page.value, pageSize.value)
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