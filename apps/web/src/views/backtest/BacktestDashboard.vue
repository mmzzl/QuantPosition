<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>策略回测</h2>
      <div class="header-actions">
        <el-select v-model="mode" style="width:160px;margin-right:12px">
          <el-option label="选股回测" value="simple" />
          <el-option label="规则引擎回测" value="rules" />
        </el-select>
        <el-button @click="runBacktest" type="primary" :loading="loading">运行回测</el-button>
      </div>
    </div>

    <div v-if="mode === 'simple'" style="margin-bottom:16px">
      <el-radio-group v-model="strategy" style="margin-right:16px">
        <el-radio value="dual_ma">双均线选股</el-radio>
        <el-radio value="news">新闻选股</el-radio>
      </el-radio-group>
      <el-select v-model="daysBack" style="width:140px">
        <el-option label="近 90 天" :value="90" />
        <el-option label="近 180 天" :value="180" />
        <el-option label="近 365 天" :value="365" />
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

    <div v-loading="loading">
      <template v-if="result && mode === 'simple'">
        <el-row :gutter="16">
          <el-col :span="8" v-for="(r, period) in result.results" :key="period">
            <el-card v-if="r.trades" :class="'perf-card ' + (r.avg_return > 0 ? 'good' : 'bad')">
              <div class="perf-title">{{ period.toUpperCase() }} 持有期</div>
              <div class="perf-big">{{ r.avg_return }}%</div>
              <div class="perf-meta">
                <span>胜率 {{ r.win_rate }}%</span>
                <span>{{ r.trades }} 笔交易</span>
              </div>
              <el-divider />
              <div class="perf-detail">
                <div>总收益: {{ r.total_return }}%</div>
                <div>最佳: {{ r.best_return }}%</div>
                <div>最差: {{ r.worst_return }}%</div>
              </div>
              <el-collapse v-if="r.examples && r.examples.length" style="margin-top:8px">
                <el-collapse-item title="示例交易" name="1">
                  <div v-for="t in r.examples.slice(0,5)" :key="t.code" class="trade-row">
                    <span>{{ t.name || t.code }}</span>
                    <span :class="t.return_pct >= 0 ? 'profit' : 'loss'">{{ t.return_pct }}%</span>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </el-col>
        </el-row>

        <el-card v-if="result.results.summary" class="summary-card" style="margin-top:16px">
          <div slot="header">总体统计</div>
          <div>分析股票数: {{ result.results.summary.stocks }}</div>
          <div>平均收益率: {{ result.results.summary.avg_return }}%</div>
          <div>平均最大回撤: {{ result.results.summary.avg_max_drawdown }}%</div>
        </el-card>
      </template>

      <template v-if="result && mode === 'rules'">
        <el-card :class="'perf-card ' + (result.avg_return > 0 ? 'good' : 'bad')">
          <div class="perf-title">规则引擎回测 ({{ result.trades }} 笔交易)</div>
          <div class="perf-big">{{ result.avg_return }}%</div>
          <div class="perf-meta">
            <span>胜率 {{ result.win_rate }}%</span>
            <span>平均持有 {{ result.avg_hold_days }} 天</span>
          </div>
          <el-divider />
          <div class="perf-detail">
            <div>总收益: {{ result.total_return }}%</div>
            <div>最佳: {{ result.best_return }}%</div>
            <div>最差: {{ result.worst_return }}%</div>
          </div>
        </el-card>

        <el-table v-if="result.trade_details" :data="result.trade_details" style="margin-top:16px" size="small">
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="buy_date" label="买入日" width="100" />
          <el-table-column prop="buy_price" label="买入价" width="80" />
          <el-table-column prop="exit_date" label="卖出日" width="135" />
          <el-table-column prop="exit_price" label="卖出价" width="80" />
          <el-table-column prop="return_pct" label="收益率" width="80">
            <template v-slot="{ row }">
              <span :class="row.return_pct >= 0 ? 'profit' : 'loss'">{{ row.return_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="hold_days" label="持有天数" width="80" />
          <el-table-column prop="triggered_rules" label="触发规则" min-width="150">
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
import { getSimpleBacktest, getRuleBacktest } from '@/api/backtest'
import { getUserId } from '@/utils/auth'

export default {
  data() {
    return {
      mode: 'simple',
      strategy: 'dual_ma',
      daysBack: 180,
      loading: false,
      result: null,
    }
  },
  methods: {
    async runBacktest() {
      this.loading = true
      this.result = null
      try {
        const params = { days_back: this.daysBack }
        if (this.mode === 'simple') {
          params.strategy = this.strategy
          const res = await getSimpleBacktest(params)
          this.result = res.data
        } else {
          const res = await getRuleBacktest(params)
          this.result = res.data
        }
      } catch (e) {
        this.$message.error('回测失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.perf-card { text-align: center; }
.perf-card.good { border-top: 3px solid #67c23a; }
.perf-card.bad { border-top: 3px solid #f56c6c; }
.perf-title { font-size: 14px; color: #909399; margin-bottom: 8px; }
.perf-big { font-size: 36px; font-weight: bold; }
.good .perf-big { color: #67c23a; }
.bad .perf-big { color: #f56c6c; }
.perf-meta { font-size: 13px; color: #909399; margin-top: 4px; }
.perf-meta span { margin: 0 8px; }
.perf-detail { font-size: 13px; color: #606266; line-height: 1.8; }
.trade-row { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.summary-card { font-size: 14px; line-height: 2; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-actions { display: flex; align-items: center; }
</style>
