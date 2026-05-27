<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>策略回测</h2>
      <el-button @click="runBacktest" type="primary" :loading="running">运行回测</el-button>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="param-label">策略</div>
          <el-select v-model="strategy" style="width:100%">
            <el-option label="双均线金叉 (MA5/MA20)" value="dual_ma" />
            <el-option label="MACD 金叉" value="macd" />
            <el-option label="布林带突破" value="bollinger" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <div class="param-label">回测天数</div>
          <el-select v-model="daysBack" style="width:100%">
            <el-option label="90 天" :value="90" />
            <el-option label="180 天" :value="180" />
            <el-option label="365 天" :value="365" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <div class="param-label">初始资金</div>
          <el-input-number v-model="initialCash" :min="10000" :step="10000" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <div class="param-label">手续费率</div>
          <el-input-number v-model="commission" :min="0" :max="0.05" :step="0.0005" :precision="4" style="width:100%" />
        </el-col>
      </el-row>
    </el-card>

    <el-progress v-if="running && progress" :percentage="progress.pct" style="margin-bottom:16px" :status="progress.status" />
    <div v-if="running" style="color:#909399;margin-bottom:16px">{{ progress?.text || '提交任务...' }}</div>

    <div v-if="loaded && !running && !result" style="text-align:center;padding:40px;color:#909399">
      选择策略后点击「运行回测」
    </div>

    <div v-loading="running">
      <template v-if="result">
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
              <div class="perf-meta">{{ result.trades }} 笔交易 | {{ result.processed }} 只股票</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">盈亏比</div>
              <div class="perf-big" :class="result.profit_factor >= 1.5 ? 'profit' : 'loss'">{{ result.profit_factor }}</div>
              <div class="perf-meta">赢 {{ result.avg_win }}% / 亏 {{ result.avg_loss }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">最大回撤</div>
              <div class="perf-big loss">{{ result.max_drawdown }}%</div>
              <div class="perf-meta">夏普 {{ result.sharpe }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top:16px">
          <el-col :span="6">
            <el-card :class="lrClass(result.total_return)" class="perf-card">
              <div class="perf-title">总收益</div>
              <div class="perf-big">{{ result.total_return }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">最佳交易</div>
              <div class="perf-big profit">{{ result.best }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">最差交易</div>
              <div class="perf-big loss">{{ result.worst }}%</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="perf-card">
              <div class="perf-title">出场统计</div>
              <div class="perf-meta">
                止损 {{ result.stopped_out }} 次<br/>
                死叉 {{ result.death_cross || 0 }} 次<br/>
                止盈 {{ result.take_profit || 0 }} 次
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card style="margin-top:16px">
          <template #header>交易记录 (前10笔)</template>
          <el-table :data="result.examples" size="small" stripe>
            <el-table-column prop="code" label="代码" width="80" />
            <el-table-column prop="entry_date" label="买入日" width="100" />
            <el-table-column prop="entry_price" label="买入价" width="80" />
            <el-table-column prop="exit_date" label="卖出日" width="100" />
            <el-table-column prop="exit_price" label="卖出价" width="80" />
            <el-table-column prop="pnl_pct" label="收益率" width="80">
              <template v-slot="{ row }">
                <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">{{ row.pnl_pct }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="出场原因" width="100">
              <template v-slot="{ row }">
                <el-tag :type="reasonType(row.reason)" size="small">{{ reasonLabel(row.reason) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script>
import { submitSimpleBacktest, getBacktestTaskStatus, getLatestBacktest } from '@/api/backtest'

export default {
  data() {
    return {
      strategy: 'dual_ma',
      daysBack: 180,
      initialCash: 100000,
      commission: 0.001,
      running: false,
      progress: null,
      result: null,
      loaded: false,
      pollTimer: null,
    }
  },
  async mounted() {
    try {
      const res = await getLatestBacktest()
      if (res.data && res.data.exists !== false && res.data.trades) {
        this.result = res.data
      }
    } catch (e) { /* ignore */ }
    this.loaded = true
  },
  beforeUnmount() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null }
  },
  methods: {
    lrClass(v) { return v >= 0 ? 'profit' : 'loss' },
    reasonType(r) { return r === 'stop_loss' ? 'danger' : r === 'take_profit' ? 'success' : 'warning' },
    reasonLabel(r) { return { stop_loss: '止损', death_cross: '死叉', macd_cross: 'MACD', take_profit: '止盈' }[r] || r },
    async runBacktest() {
      this.running = true
      this.result = null
      this.progress = { pct: 0, text: '提交任务...', status: '' }

      try {
        const params = {
          strategy: this.strategy,
          days_back: this.daysBack,
          initial_cash: this.initialCash,
          commission: this.commission,
        }
        const res = await submitSimpleBacktest(params)
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
            this.result = result
            this.progress = { pct: 100, text: '完成', status: 'success' }
            if (!result || !result.trades) {
              this.$message.warning('回测完成，但没有产生有效交易')
            }
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
      }, 2000)
    }
  }
}
</script>

<style scoped>
.param-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.perf-card { text-align: center; }
.perf-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.perf-big { font-size: 28px; font-weight: bold; margin: 4px 0; }
.perf-meta { font-size: 12px; color: #909399; line-height: 1.6; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
</style>
