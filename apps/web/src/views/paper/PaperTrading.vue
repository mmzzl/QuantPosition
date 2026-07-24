<template>
  <div class="paper-page">
    <div class="page-header">
      <h2>信号模拟盘</h2>
      <div>
        <el-button @click="syncBuy" :loading="syncing">同步选股信号</el-button>
        <el-button @click="syncSell" :loading="syncing">执行规则卖出</el-button>
        <el-button @click="refresh" type="primary">刷新</el-button>
        <el-popconfirm title="确定清空所有模拟持仓？" @confirm="clearAll">
          <el-button type="danger" size="small">清空</el-button>
        </el-popconfirm>
      </div>
    </div>

    <el-row :gutter="16" v-loading="loading">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">持仓数量</div>
          <div class="stat-value">{{ data.open?.count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">总成本</div>
          <div class="stat-value">{{ (data.open?.total_cost || 0).toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">市值</div>
          <div class="stat-value">{{ (data.open?.market_value || 0).toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已平仓胜率</div>
          <div class="stat-value">{{ data.closed?.win_rate || 0 }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top:16px">
      <template #header>当前持仓</template>
      <el-table :data="data.open?.positions || []" size="small">
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="strategy" label="来源" width="80" />
        <el-table-column prop="buy_date" label="买入日" width="100" />
        <el-table-column prop="buy_price" label="买入价" width="80" />
        <el-table-column prop="current_price" label="现价" width="80" />
        <el-table-column prop="unrealized_pnl" label="盈亏" width="100">
          <template v-slot="{ row }">
            <span :class="row.unrealized_pnl >= 0 ? 'profit' : 'loss'">{{ row.unrealized_pnl.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unrealized_pnl_pct" label="收益率" width="80">
          <template v-slot="{ row }">
            <span :class="row.unrealized_pnl_pct >= 0 ? 'profit' : 'loss'">{{ row.unrealized_pnl_pct.toFixed(2) }}%</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top:16px">
      <template #header>已平仓记录</template>
      <el-table :data="data.closed?.trades || []" size="small">
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="buy_date" label="买入" width="100" />
        <el-table-column prop="sell_date" label="卖出" width="100" />
        <el-table-column prop="buy_price" label="买入价" width="80" />
        <el-table-column prop="sell_price" label="卖出价" width="80" />
        <el-table-column prop="return_pct" label="收益率" width="80">
          <template v-slot="{ row }">
            <span :class="row.return_pct >= 0 ? 'profit' : 'loss'">{{ row.return_pct }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="触发规则" min-width="150">
          <template v-slot="{ row }">
            <el-tag v-for="r in (row.triggered_rules||[])" :key="r" size="small" style="margin-right:4px">{{ r }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { getPaperPositions, syncPaperBuy, syncPaperSell, clearPaper } from '@/api/paperTrading'

export default {
  data() {
    return { loading: false, syncing: false, data: {} }
  },
  mounted() { this.refresh() },
  methods: {
    async refresh() {
      this.loading = true
      try {
        const res = await getPaperPositions()
        this.data = res.data
      } catch (e) {
        this.$message.error('加载失败')
      } finally { this.loading = false }
    },
    async syncBuy() {
      this.syncing = true
      try {
        const res = await syncPaperBuy()
        this.$message.success(`同步 ${res.data.synced_count || res.data.synced || 0} 只`)
        await this.refresh()
      } catch (e) {
        this.$message.error('同步失败')
      } finally { this.syncing = false }
    },
    async syncSell() {
      this.syncing = true
      try {
        const res = await syncPaperSell()
        this.$message.success('卖出执行完成')
        await this.refresh()
      } catch (e) {
        this.$message.error('卖出失败')
      } finally { this.syncing = false }
    },
    async clearAll() {
      await clearPaper()
      this.$message.success('已清空')
      this.data = {}
    }
  }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.stat-card { text-align: center; }
.stat-label { font-size: 13px; color: #909399; }
.stat-value { font-size: 24px; font-weight: bold; margin: 8px 0; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
