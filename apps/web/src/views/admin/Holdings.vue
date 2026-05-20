<template>
  <div class="admin-holdings-page">
    <div class="page-header">
      <h2>所有用户持仓</h2>
    </div>

    <el-card>
      <el-table :data="holdings" v-loading="loading" stripe>
        <el-table-column prop="user_id" label="用户ID" width="150" />
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

    <el-card style="margin-top: 20px">
      <template #header>
        <span>已实现盈亏汇总</span>
      </template>
      <el-table :data="pnlData" stripe>
        <el-table-column prop="user_id" label="用户ID" width="150" />
        <el-table-column prop="total_buy" label="买入总额" width="120">
          <template #default="{ row }">
            {{ row.total_buy?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_sell" label="卖出总额" width="120">
          <template #default="{ row }">
            {{ row.total_sell?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="realized_pnl" label="已实现盈亏" width="120">
          <template #default="{ row }">
            <span :class="row.realized_pnl >= 0 ? 'profit' : 'loss'">
              {{ row.realized_pnl?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllHoldings, getAllRealizedPnl } from '@/api/holdings'

const loading = ref(false)
const holdings = ref([])
const pnlData = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function fetchHoldings() {
  loading.value = true
  try {
    const res = await getAllHoldings(page.value, pageSize.value)
    holdings.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取持仓列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchPnl() {
  try {
    const res = await getAllRealizedPnl()
    pnlData.value = res.data.users || []
  } catch (e) {
    // ignore
  }
}

onMounted(() => {
  fetchHoldings()
  fetchPnl()
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

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}
</style>