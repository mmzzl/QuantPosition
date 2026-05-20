<template>
  <div class="sector-stock-list">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="$router.back()">返回</el-button>
        <h2>{{ sectorName }} - 股票列表</h2>
      </div>
      <div class="header-right">
        <el-select v-model="sortBy" @change="fetchStocks" style="width: 120px">
          <el-option label="涨跌幅" value="change_pct" />
          <el-option label="成交量" value="volume" />
          <el-option label="名称" value="name" />
        </el-select>
        <el-select v-model="sortOrder" @change="fetchStocks" style="width: 100px; margin-left: 10px">
          <el-option label="降序" value="desc" />
          <el-option label="升序" value="asc" />
        </el-select>
      </div>
    </div>

    <el-card>
      <el-table :data="stocks" v-loading="loading" stripe>
        <el-table-column prop="code" label="股票代码" width="120" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="current_price" label="当前价" width="100">
          <template #default="{ row }">
            {{ row.current_price?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="change_pct" label="涨跌幅" width="100">
          <template #default="{ row }">
            <span :class="row.change_pct >= 0 ? 'profit' : 'loss'">
              {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量" width="120">
          <template #default="{ row }">
            {{ formatVolume(row.volume) }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="120">
          <template #default="{ row }">
            {{ formatAmount(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
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
        @size-change="fetchStocks"
        @current-change="fetchStocks"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <!-- K线图对话框 -->
    <el-dialog v-model="klineDialogVisible" :title="`${selectedStock?.name} (${selectedStock?.code})`" width="800px">
      <KLineChart v-if="klineData.length" :data="klineData" :title="`${selectedStock?.name} (${selectedStock?.code})`" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSectorStocks, getKlineData } from '@/api/sectors'
import KLineChart from '@/views/holdings/KLineChart.vue'

const route = useRoute()
const loading = ref(false)
const stocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const sortBy = ref('change_pct')
const sortOrder = ref('desc')
const sectorName = ref(route.params.sectorName || '')
const period = ref(route.query.period || '24h')

const klineDialogVisible = ref(false)
const selectedStock = ref(null)
const klineData = ref([])

function formatVolume(vol) {
  if (!vol) return '-'
  if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿'
  if (vol >= 10000) return (vol / 10000).toFixed(2) + '万'
  return vol
}

function formatAmount(amount) {
  if (!amount) return '-'
  if (amount >= 100000000) return (amount / 100000000).toFixed(2) + '亿'
  if (amount >= 10000) return (amount / 10000).toFixed(2) + '万'
  return amount.toFixed(2)
}

async function fetchStocks() {
  loading.value = true
  try {
    const res = await getSectorStocks(sectorName.value, {
      period: period.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page: page.value,
      page_size: pageSize.value
    })
    stocks.value = res.data.stocks || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取股票列表失败')
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

onMounted(() => {
  fetchStocks()
})
</script>

<style scoped>
.sector-stock-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-left h2 {
  margin: 0;
}

.header-right {
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
