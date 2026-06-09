<template>
  <div>
    <div class="page-header">
      <h2>策略回测</h2>
      <el-button @click="run" type="primary" :loading="running">运行回测</el-button>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="16">
        <el-col :span="5">
          <div class="label">回测天数</div>
            <el-select v-model="daysBack" style="width:100%">
            <el-option label="180 天" :value="180" />
            <el-option label="360 天（推荐）" :value="360" />
            <el-option label="730 天" :value="730" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <div class="label">初始资金</div>
          <el-input-number v-model="cash" :min="10000" :step="10000" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <div class="label">手续费率</div>
          <el-input-number v-model="commission" :min="0" :max="0.05" :step="0.0005" :precision="4" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <div class="label">最大持仓</div>
          <el-input-number v-model="maxPositions" :min="1" :max="20" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <div class="label">候选股票数</div>
          <el-select v-model="maxStocks" style="width:100%">
            <el-option label="100 只（快速）" :value="100" />
            <el-option label="300 只" :value="300" />
            <el-option label="500 只（推荐）" :value="500" />
            <el-option label="全市场" :value="0" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <div class="label">&nbsp;</div>
          <el-button @click="run" type="primary" :loading="running" style="width:100%">运行回测</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-progress v-if="running && progress" :percentage="progress.pct" :status="progress.status" style="margin-bottom:8px" />
    <div v-if="running" style="color:#909399;margin-bottom:16px;font-size:13px">
      {{ progress?.text || '准备中...' }}
      <span v-if="progress?.detail"> — {{ progress.detail }}</span>
    </div>

    <div v-if="!running && !result" style="text-align:center;padding:40px;color:#909399">
      点击「运行回测」，系统会加载你配置的所有规则，扫描全市场股票进行模拟交易
    </div>

    <template v-if="result">
      <el-row :gutter="16">
        <el-col :span="6"><el-card :class="cls(result.portfolio_return)" class="stat"><div class="t">组合收益</div><div class="v">{{ result.portfolio_return }}%</div><div class="m">{{ result.trades }} 笔交易 | {{ result.unique_stocks || result.processed }} 只股票</div></el-card></el-col>
        <el-col :span="4"><el-card :class="cls(result.avg_return)" class="stat"><div class="t">平均单笔</div><div class="v">{{ result.avg_return }}%</div></el-card></el-col>
        <el-col :span="4"><el-card class="stat"><div class="t">胜率</div><div class="v" :class="result.win_rate>=50?'profit':'loss'">{{ result.win_rate }}%</div></el-card></el-col>
        <el-col :span="5"><el-card class="stat"><div class="t">盈亏比</div><div class="v" :class="result.profit_factor>=1.5?'profit':'loss'">{{ result.profit_factor }}</div><div class="m">赢{{ result.avg_win }}% / 亏{{ result.avg_loss }}%</div></el-card></el-col>
        <el-col :span="5"><el-card class="stat"><div class="t">夏普</div><div class="v" :class="result.sharpe>=1?'profit':'loss'">{{ result.sharpe }}</div></el-card></el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top:16px">
        <el-col :span="6"><el-card :class="cls(result.total_return)" class="stat"><div class="t">单笔总收益</div><div class="v">{{ result.total_return }}%</div></el-card></el-col>
        <el-col :span="4"><el-card class="stat"><div class="t">最佳</div><div class="v profit">{{ result.best }}%</div></el-card></el-col>
        <el-col :span="4"><el-card class="stat"><div class="t">最差</div><div class="v loss">{{ result.worst }}%</div></el-card></el-col>
        <el-col :span="6">
          <el-card class="stat">
            <div class="t">出场方式</div>
            <div class="m" v-for="(v,k) in (result.exit_stats||{})" :key="k">{{ exitLabel(k) }}: {{ v }} 次</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card style="margin-top:16px">
        <template #header>使用的规则</template>
        <div v-if="result.rules" style="font-size:13px;color:#606266">
          {{ result.rules.join(' → ') }}
        </div>
      </el-card>

      <el-card style="margin-top:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>交易记录</span>
            <div style="display:flex;gap:8px">
              <el-radio-group v-model="filterRank" size="small">
                <el-radio-button value="">全部</el-radio-button>
                <el-radio-button value="best">最好</el-radio-button>
                <el-radio-button value="worst">最差</el-radio-button>
              </el-radio-group>
              <el-input v-model="filterCode" placeholder="代码" clearable style="width:120px" size="small" />
              <el-input v-model="filterName" placeholder="名称" clearable style="width:120px" size="small" />
              <el-select v-model="filterReason" placeholder="出场方式" clearable size="small" style="width:120px">
                <el-option label="风控" value="risk" />
                <el-option label="规则卖出" value="sell" />
                <el-option label="止损" value="stop_loss" />
                <el-option label="超时" value="timeout" />
              </el-select>
            </div>
          </div>
        </template>
        <el-table :data="pagedTrades" size="small" stripe @sort-change="handleSortChange">
          <el-table-column prop="code" label="代码" width="80" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="entry_date" label="买入日" width="105" />
          <el-table-column prop="entry_price" label="买入价" width="80">
            <template v-slot="{ row }">{{ row.entry_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="exit_date" label="卖出日" width="105" />
          <el-table-column prop="exit_price" label="卖出价" width="80">
            <template v-slot="{ row }">{{ row.exit_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="hold_days" label="天数" width="60" />
          <el-table-column prop="pnl_pct" label="收益" width="80" sortable="custom">
            <template v-slot="{ row }"><span :class="row.pnl_pct>=0?'profit':'loss'">{{ row.pnl_pct }}%</span></template>
          </el-table-column>
          <el-table-column prop="reason" label="出场" width="80">
            <template v-slot="{ row }"><el-tag :type="reasonType(row.reason)" size="small">{{ exitLabel(row.reason) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="触发规则" min-width="150">
            <template v-slot="{ row }"><el-tag v-for="r in (row.triggered_rules||[])" :key="r" size="small" style="margin-right:4px">{{ r }}</el-tag></template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filteredTrades.length"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          style="margin-top:16px;justify-content:center"
        />
      </el-card>
    </template>
  </div>
</template>

<script>
import { submitBacktest, getTaskStatus, getLatestBacktest } from '@/api/backtest'

export default {
  data() {
    return {
      daysBack: 360, cash: 100000, commission: 0.001, maxStocks: 500, maxPositions: 5,
      running: false, progress: null, result: null, pollTimer: null,
      page: 1, pageSize: 20,
      filterCode: '', filterName: '', filterReason: '', filterRank: '',
      sortKey: 'pnl_pct', sortOrder: 'descending',
    }
  },
  async mounted() {
    try {
      const { data } = await getLatestBacktest()
      if (data && data.exists !== false && data.trades) this.result = data
    } catch (e) {}
  },
  computed: {
    allTrades() {
      if (this.filterRank === 'best') return this.result?.examples_best || []
      if (this.filterRank === 'worst') return this.result?.examples_worst || []
      return this.result?.trades_list || this.result?.examples || []
    },
    filteredTrades() {
      let list = [...this.allTrades]
      if (this.filterCode) list = list.filter(t => t.code.includes(this.filterCode))
      if (this.filterName) list = list.filter(t => (t.name || '').includes(this.filterName))
      if (this.filterReason) list = list.filter(t => t.reason === this.filterReason)
      if (this.sortKey) {
        list.sort((a, b) => {
          const va = a[this.sortKey] ?? 0
          const vb = b[this.sortKey] ?? 0
          return this.sortOrder === 'ascending' ? va - vb : vb - va
        })
      }
      return list
    },
    pagedTrades() {
      const start = (this.page - 1) * this.pageSize
      return this.filteredTrades.slice(start, start + this.pageSize)
    },
  },
  beforeUnmount() { if (this.pollTimer) clearInterval(this.pollTimer) },
  watch: {
    filterCode() { this.page = 1 },
    filterName() { this.page = 1 },
    filterReason() { this.page = 1 },
    filterRank() { this.page = 1 },
  },
  methods: {
    cls(v) { return v >= 0 ? 'profit' : 'loss' },
    exitLabel(k) { return { risk: '风控', sell: '规则卖出', stop_loss: '止损', timeout: '超时' }[k] || k },
    reasonType(k) { return { risk: 'danger', stop_loss: 'danger', sell: 'warning', timeout: 'info' }[k] || '' },
    handleSortChange({ prop, order }) {
      if (prop) {
        this.sortKey = prop
        this.sortOrder = order || 'descending'
      }
    },
    async run() {
      this.running = true
      this.result = null
      this.progress = { pct: 0, text: '提交任务...', status: '' }
      try {
        const { data } = await submitBacktest({ days_back: this.daysBack, initial_cash: this.cash, commission: this.commission, max_stocks: this.maxStocks, max_positions: this.maxPositions })
        this.poll(data.task_id)
      } catch (e) {
        this.$message.error(e.response?.data?.detail || e.message)
        this.running = false
      }
    },
    poll(id) {
      this.pollTimer = setInterval(async () => {
        try {
          const { data } = await getTaskStatus(id)
          if (data.status === 'SUCCESS') {
            clearInterval(this.pollTimer)
            this.running = false
            this.result = data.result
            this.progress = { pct: 100, text: '完成', status: 'success' }
            if (!data.result?.trades) this.$message.warning('没有产生交易，请检查规则配置')
          } else if (data.status === 'FAILURE') {
            clearInterval(this.pollTimer)
            this.running = false
            this.$message.error(data.error || '回测失败')
          } else if (data.progress) {
            const { current: c, total: t, status: s } = data.progress
            this.progress = { pct: t ? Math.round(c / t * 100) : 0, text: s || '', status: '' }
          }
        } catch (e) { console.error(e) }
      }, 2000)
    }
  }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.stat { text-align: center; }
.t { font-size: 13px; color: #909399; margin-bottom: 4px; }
.v { font-size: 28px; font-weight: bold; margin: 4px 0; }
.m { font-size: 12px; color: #909399; line-height: 1.6; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
