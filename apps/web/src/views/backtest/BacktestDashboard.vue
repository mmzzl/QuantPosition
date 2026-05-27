<template>
  <div>
    <div class="page-header">
      <h2>策略回测</h2>
      <el-button @click="run" type="primary" :loading="running">运行回测</el-button>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="label">回测天数</div>
          <el-select v-model="daysBack" style="width:100%">
            <el-option label="90 天" :value="90" />
            <el-option label="180 天" :value="180" />
            <el-option label="365 天" :value="365" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <div class="label">初始资金</div>
          <el-input-number v-model="cash" :min="10000" :step="10000" style="width:100%" />
        </el-col>
        <el-col :span="6">
          <div class="label">手续费率</div>
          <el-input-number v-model="commission" :min="0" :max="0.05" :step="0.0005" :precision="4" style="width:100%" />
        </el-col>
      </el-row>
    </el-card>

    <el-progress v-if="running && progress" :percentage="progress.pct" :status="progress.status" style="margin-bottom:16px" />
    <div v-if="running" style="color:#909399;margin-bottom:16px">{{ progress?.text }}</div>

    <div v-if="!running && !result" style="text-align:center;padding:40px;color:#909399">
      点击「运行回测」，系统会加载你配置的所有规则，扫描全市场股票进行模拟交易
    </div>

    <template v-if="result">
      <el-row :gutter="16">
        <el-col :span="6"><el-card :class="cls(result.avg_return)" class="stat"><div class="t">平均收益</div><div class="v">{{ result.avg_return }}%</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">胜率</div><div class="v" :class="result.win_rate>=50?'profit':'loss'">{{ result.win_rate }}%</div><div class="m">{{ result.trades }} 笔 | {{ result.processed }} 只</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">盈亏比</div><div class="v" :class="result.profit_factor>=1.5?'profit':'loss'">{{ result.profit_factor }}</div><div class="m">赢{{ result.avg_win }}% / 亏{{ result.avg_loss }}%</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">夏普 / 回撤</div><div class="v" :class="result.sharpe>=1?'profit':'loss'">{{ result.sharpe }}</div><div class="m">最大回撤 {{ result.max_drawdown }}%</div></el-card></el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top:16px">
        <el-col :span="6"><el-card :class="cls(result.total_return)" class="stat"><div class="t">总收益</div><div class="v">{{ result.total_return }}%</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">最佳</div><div class="v profit">{{ result.best }}%</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">最差</div><div class="v loss">{{ result.worst }}%</div></el-card></el-col>
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
        <template #header>交易记录 (前10笔)</template>
        <el-table :data="result.examples" size="small" stripe>
          <el-table-column prop="code" label="代码" width="80" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="entry_date" label="买入" width="100" />
          <el-table-column prop="exit_date" label="卖出" width="100" />
          <el-table-column prop="hold_days" label="天数" width="60" />
          <el-table-column prop="pnl_pct" label="收益" width="80">
            <template v-slot="{ row }"><span :class="row.pnl_pct>=0?'profit':'loss'">{{ row.pnl_pct }}%</span></template>
          </el-table-column>
          <el-table-column prop="reason" label="出场" width="80">
            <template v-slot="{ row }"><el-tag :type="reasonType(row.reason)" size="small">{{ exitLabel(row.reason) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="触发规则" min-width="150">
            <template v-slot="{ row }"><el-tag v-for="r in (row.triggered_rules||[])" :key="r" size="small" style="margin-right:4px">{{ r }}</el-tag></template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script>
import { submitBacktest, getTaskStatus, getLatestBacktest } from '@/api/backtest'

export default {
  data() { return { daysBack: 180, cash: 100000, commission: 0.001, running: false, progress: null, result: null, pollTimer: null } },
  async mounted() {
    try {
      const { data } = await getLatestBacktest()
      if (data && data.exists !== false && data.trades) this.result = data
    } catch (e) {}
  },
  beforeUnmount() { if (this.pollTimer) clearInterval(this.pollTimer) },
  methods: {
    cls(v) { return v >= 0 ? 'profit' : 'loss' },
    exitLabel(k) { return { risk: '风控', sell: '规则卖出', stop_loss: '止损', timeout: '超时' }[k] || k },
    reasonType(k) { return { risk: 'danger', stop_loss: 'danger', sell: 'warning', timeout: 'info' }[k] || '' },
    async run() {
      this.running = true
      this.result = null
      this.progress = { pct: 0, text: '提交任务...', status: '' }
      try {
        const { data } = await submitBacktest({ days_back: this.daysBack, initial_cash: this.cash, commission: this.commission })
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
