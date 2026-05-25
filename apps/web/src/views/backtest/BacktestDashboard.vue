<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>策略回测</h2>
      <div class="header-actions">
        <el-select v-model="mode" style="width:160px;margin-right:12px">
          <el-option label="选股回测" value="simple" />
          <el-option label="规则引擎回测" value="rules" />
        </el-select>
        <el-button @click="runBacktest" type="primary" :loading="running">运行回测</el-button>
      </div>
    </div>

    <div v-if="mode === 'simple'" style="margin-bottom:16px">
      <el-radio-group v-model="strategy" style="margin-right:16px">
        <el-radio value="dual_ma">双均线金叉 (MA5上穿MA20)</el-radio>
      </el-radio-group>
      <el-select v-model="daysBack" style="width:140px;margin-right:8px">
        <el-option label="近 90 天" :value="90" />
        <el-option label="近 180 天" :value="180" />
        <el-option label="近 365 天" :value="365" />
      </el-select>
      <el-select v-model="maxHold" style="width:140px">
        <el-option label="持有时长" value="" disabled />
        <el-option label="持有 20 天" :value="20" />
        <el-option label="持有 40 天" :value="40" />
        <el-option label="持有 60 天" :value="60" />
      </el-select>
    </div>

    <div v-if="mode === 'rules'" style="margin-bottom:16px">
      <el-select v-model="daysBack" style="width:140px">
        <el-option label="近 90 天" :value="90" />
        <el-option label="近 180 天" :value="180" />
        <el-option label="近 365 天" :value="365" />
      </el-select>
      <el-tag type="warning" style="margin-left:12px">使用你配置的卖出/风控规则模拟交易</el-tag>
    </div>

    <el-progress v-if="running && progress" :percentage="progress.pct" style="margin-bottom:16px" :status="progress.status" />
    <div v-if="running" style="color:#909399;margin-bottom:16px">{{ progress?.text || '提交任务...' }}</div>

    <div v-loading="running">
      <template v-if="result && mode === 'simple'">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-card :class="lrClass(result.avg_return)" class="perf-card">
              <div class="perf-title">平均收益率</div>
              <div class="perf-big">{{ result.avg_return }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">胜率</div>
              <div class="perf-big" :class="result.win_rate >= 50 ? 'profit' : 'loss'">{{ result.win_rate }}%</div>
              <div class="perf-meta">{{ result.trades }} 笔交易</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">盈亏比</div>
              <div class="perf-big" :class="result.profit_factor >= 1.5 ? 'profit' : 'loss'">{{ result.profit_factor }}</div>
              <div class="perf-meta">平均赢 {{ result.avg_win }}% / 亏 {{ result.avg_loss }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">夏普比率</div>
              <div class="perf-big" :class="result.sharpe >= 1 ? 'profit' : 'loss'">{{ result.sharpe }}</div>
              <div class="perf-meta">止损 {{ result.stopped_out }} 次</div>
            </el-card>
          </el-col>
        </el-row>
        <el-card class="summary-card" style="margin-top:16px">
          <template #header>回测详情 ({{ result.signal_count }} 个金叉信号)</template>
          <div class="stat-grid">
            <div><label>持有上限</label><span>{{ result.max_hold_days }} 天</span></div>
            <div><label>总收益率</label><span :class="lrClass(result.total_return)">{{ result.total_return }}%</span></div>
            <div><label>最佳交易</label><span class="profit">{{ result.best }}%</span></div>
            <div><label>最差交易</label><span class="loss">{{ result.worst }}%</span></div>
          </div>
        </el-card>
        <el-table v-if="result.examples" :data="result.examples" style="margin-top:16px" size="small">
          <el-table-column prop="code" label="代码" width="80" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="buy_date" label="买入" width="100" />
          <el-table-column prop="sell_date" label="卖出" width="100" />
          <el-table-column prop="hold_days" label="持有" width="60" />
          <el-table-column prop="return_pct" label="收益率" width="80">
            <template v-slot="{ row }">
              <span :class="row.return_pct >= 0 ? 'profit' : 'loss'">{{ row.return_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="止损" width="60">
            <template v-slot="{ row }">
              <el-tag v-if="row.stopped_out" type="danger" size="small">是</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-if="result && mode === 'rules'">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-card :class="lrClass(result.avg_return)" class="perf-card">
              <div class="perf-title">平均收益率</div>
              <div class="perf-big">{{ result.avg_return }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">胜率</div>
              <div class="perf-big" :class="result.win_rate >= 50 ? 'profit' : 'loss'">{{ result.win_rate }}%</div>
              <div class="perf-meta">{{ result.trades }} 笔交易</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">平均持有</div>
              <div class="perf-big">{{ result.avg_hold_days }} 天</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">总收益</div>
              <div class="perf-big" :class="lrClass(result.total_return)">{{ result.total_return }}%</div>
            </el-card>
          </el-col>
        </el-row>
        <el-table v-if="result.trade_details" :data="result.trade_details" style="margin-top:16px" size="small">
          <el-table-column prop="code" label="代码" width="80" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="buy_date" label="买入" width="100" />
          <el-table-column prop="exit_date" label="卖出" width="135" />
          <el-table-column prop="hold_days" label="持有" width="60" />
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
      </template>
    </div>
  </div>
</template>

<script>
import { submitSimpleBacktest, submitRuleBacktest, getBacktestTaskStatus } from '@/api/backtest'

export default {
  data() {
    return {
      mode: 'simple',
      strategy: 'dual_ma',
      daysBack: 180,
      maxHold: 60,
      running: false,
      progress: null,
      result: null,
      pollTimer: null,
    }
  },
  beforeUnmount() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null }
  },
  methods: {
    lrClass(v) { return v >= 0 ? 'profit' : 'loss' },
    async runBacktest() {
      this.running = true
      this.result = null
      this.progress = { pct: 0, text: '提交任务...', status: '' }

      try {
        const params = { days_back: this.daysBack }
        let res
        if (this.mode === 'simple') {
          params.strategy = this.strategy
          params.hold_days = String(this.maxHold || 60)
          res = await submitSimpleBacktest(params)
        } else {
          res = await submitRuleBacktest(params)
        }
        this.startPolling(res.data.task_id)
      } catch (e) {
        this.$message.error('提交失败: ' + (e.response?.data?.detail || e.message))
        this.running = false
      }
    },
    startPolling(taskId) {
      if (this.pollTimer) clearInterval(this.pollTimer)
      this.pollTimer = setInterval(async () => {
        try {
          const res = await getBacktestTaskStatus(taskId)
          const { status, progress, result, error } = res.data

          if (status === 'SUCCESS') {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.running = false
            desc = progress?.status
            this.result = result
            this.progress = { pct: 100, text: '完成', status: 'success' }
          } else if (status === 'FAILURE') {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.running = false
            this.$message.error('回测失败: ' + (error || '未知错误'))
            this.progress = { pct: 100, text: '失败', status: 'exception' }
          } else if (status === 'PROGRESS' && progress) {
            const cur = progress.current || 0
            const total = progress.total || 1
            this.progress = {
              pct: Math.round(cur / total * 100),
              text: progress.status || `处理中 ${cur}/${total}`,
              status: '',
            }
          }
        } catch (e) {
          console.error('poll error', e)
        }
      }, 1500)
    }
  }
}
</script>

<style scoped>
.perf-card { text-align: center; }
.perf-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.perf-big { font-size: 28px; font-weight: bold; margin: 4px 0; }
.perf-meta { font-size: 12px; color: #909399; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.summary-card { font-size: 14px; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stat-grid label { color: #909399; margin-right: 8px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-actions { display: flex; align-items: center; }
</style>
