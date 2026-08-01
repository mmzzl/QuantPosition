<template>
  <div>
    <div class="page-header">
      <el-button @click="goBack()">{{ backLabel }}</el-button>
      <el-button v-if="isCandidate && trade" size="small" @click="trade = null">← 返回交易列表</el-button>
      <h2 v-if="trade">{{ trade.code }} {{ trade.name }}</h2>
      <span v-else>交易详情</span>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon center />
    <el-alert v-if="loading" title="加载中..." type="info" show-icon :closable="false" />
    <el-alert v-else-if="error" :title="error" type="error" show-icon />
    <el-alert v-else-if="!isCandidate && !trade" title="未找到该交易" type="warning" show-icon />

    <template v-if="isCandidate && !loading && !trade">
      <el-card v-if="backtestResult" style="margin-top:16px">
        <template #header>规则回测统计</template>
        <el-row :gutter="16">
          <el-col :span="6"><div class="stat"><div class="t">总交易</div><div class="v">{{ backtestResult.total_trades || 0 }}</div></div></el-col>
          <el-col :span="6"><div class="stat"><div class="t">Sharpe</div><div class="v">{{ backtestResult.sharpe }}</div></div></el-col>
          <el-col :span="6"><div class="stat"><div class="t">组合收益</div><div class="v" :class="backtestResult.portfolio_return >= 0 ? 'profit' : 'loss'">{{ backtestResult.portfolio_return }}%</div></div></el-col>
          <el-col :span="6"><div class="stat"><div class="t">胜率</div><div class="v">{{ backtestResult.win_rate }}%</div></div></el-col>
        </el-row>
      </el-card>

      <el-card style="margin-top:16px">
        <template #header>历史交易 ({{ trades.length }})</template>
        <el-empty v-if="trades.length === 0" description="该规则无历史交易记录" />
        <el-table v-else :data="trades" stripe>
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="140" />
          <el-table-column prop="entry_date" label="买入日" width="120" />
          <el-table-column prop="exit_date" label="卖出日" width="120" />
          <el-table-column label="持有天数" width="90">
            <template #default="{ row }">{{ row.hold_days }} 天</template>
          </el-table-column>
          <el-table-column label="收益" width="110">
            <template #default="{ row }">
              <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">{{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="出场方式" width="100">
            <template #default="{ row }">
              <el-tag :type="reasonType(row.reason)" size="small">{{ exitLabel(row.reason) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="trade = row">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <template v-else-if="trade">
      <div class="header-card" :class="trade.pnl_pct >= 0 ? 'profit-bg' : 'loss-bg'">
        <div class="header-main">
          <div class="pnl-big" :class="trade.pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ trade.pnl_pct >= 0 ? '+' : '' }}{{ trade.pnl_pct }}%
          </div>
          <div class="pnl-amount" :class="trade.pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ calcPnlAmount(trade) }}
          </div>
        </div>
        <div class="header-meta">
          <span>{{ trade.code }} {{ trade.name }}</span>
          <span>{{ trade.hold_days }} 天 · {{ exitLabel(trade.reason) }}</span>
        </div>
      </div>

      <el-row :gutter="16" style="margin-top:16px">
        <el-col :span="6"><el-card class="stat"><div class="t">买入日</div><div class="v" style="font-size:20px">{{ trade.entry_date }}</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">卖出日</div><div class="v" style="font-size:20px">{{ trade.exit_date }}</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">持有天数</div><div class="v" style="font-size:20px">{{ trade.hold_days }}</div></el-card></el-col>
        <el-col :span="6"><el-card class="stat"><div class="t">出场方式</div><div class="v" style="font-size:20px"><el-tag :type="reasonType(trade.reason)" size="large">{{ exitLabel(trade.reason) }}</el-tag></div></el-card></el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top:16px">
        <el-col :span="8"><el-card class="stat"><div class="t">买入价</div><div class="v" style="font-size:24px;color:#409eff">{{ trade.entry_price.toFixed(2) }}</div><div class="m">买入金额 {{ (trade.entry_price * 100).toFixed(0) }}</div></el-card></el-col>
        <el-col :span="8"><el-card class="stat"><div class="t">卖出价</div><div class="v" style="font-size:24px;color:#e6a23c">{{ trade.exit_price.toFixed(2) }}</div><div class="m">卖出金额 {{ (trade.exit_price * 100).toFixed(0) }}</div></el-card></el-col>
        <el-col :span="8"><el-card class="stat"><div class="t">价差</div><div class="v" style="font-size:24px" :class="trade.pnl_pct >= 0 ? 'profit' : 'loss'">{{ (trade.exit_price - trade.entry_price).toFixed(2) }}</div></el-card></el-col>
      </el-row>

      <el-card style="margin-top:16px">
        <template #header>收益率走势</template>
        <div class="pnl-large-bar-wrapper">
          <div class="pnl-large-bar" :style="{ width: Math.min(Math.abs(trade.pnl_pct) * 6, 100) + '%', background: trade.pnl_pct>=0?'#f56c6c':'#67c23a' }"></div>
        </div>
      </el-card>

      <el-card style="margin-top:16px">
        <template #header>交易时间线</template>
        <el-timeline>
          <el-timeline-item :timestamp="trade.entry_date" placement="top" color="#409eff">
            <h4>买入</h4>
            <p>{{ trade.code }} {{ trade.name }} @ {{ trade.entry_price.toFixed(2) }}</p>
          </el-timeline-item>
          <el-timeline-item :timestamp="trade.exit_date" placement="top" :color="trade.pnl_pct >= 0 ? '#f56c6c' : '#67c23a'">
            <h4>卖出 · {{ exitLabel(trade.reason) }}</h4>
            <p>@ {{ trade.exit_price.toFixed(2) }} · 收益 {{ trade.pnl_pct >= 0 ? '+' : '' }}{{ trade.pnl_pct }}%</p>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <el-card style="margin-top:16px">
        <template #header>触发规则 ({{ (trade.triggered_rules||[]).length }})</template>
        <div v-if="trade.triggered_rules?.length" class="rule-list">
          <el-tag v-for="(r,i) in trade.triggered_rules" :key="i" style="margin:3px" size="medium">{{ r }}</el-tag>
        </div>
        <div v-else style="color:#909399;font-size:13px">无</div>
      </el-card>
    </template>
  </div>
</template>

<script>
import { getLatestBacktest, getCandidateBacktest } from '@/api/backtest'

export default {
  data() {
    return { loading: true, error: '', trade: null, loadError: null, trades: [], backtestResult: null }
  },
  computed: {
    isCandidate() {
      return this.$route.name === 'CandidateTradeDetail'
    },
    backLabel() {
      return this.isCandidate ? '← 返回候选规则' : '← 返回回测'
    }
  },
  async created() {
    const { code, entry, id } = this.$route.query
    if (id) {
      await this.loadCandidateTrades(id)
    } else if (code && entry) {
      await this.loadTradeDetail(code, entry)
    }
  },
  async mounted() {
    if (this.trade || this.loadError) return
  },
  methods: {
    goBack() {
      this.$router.push(this.isCandidate ? '/candidates' : '/backtest')
    },
    async loadCandidateTrades(id) {
      this.loading = true
      try {
        const { data } = await getCandidateBacktest(id)
        this.backtestResult = data
        this.trades = data.trades || []
      } catch (e) {
        this.loadError = '规则不存在或数据异常'
      } finally {
        this.loading = false
      }
    },
    async loadTradeDetail(code, entry) {
      try {
        const { data } = await getLatestBacktest()
        const trades = data?.trades || data?.trades_list || []
        this.trade = trades.find(t => t.code === code && t.entry_date === entry) || null
        if (!this.trade) this.error = `未找到 ${code} ${entry} 的交易记录`
      } catch (e) { this.error = e.response?.data?.detail || e.message }
      finally { this.loading = false }
    },
    exitLabel(k) { return { risk: '风控', sell: '规则卖出', stop_loss: '止损', timeout: '超时' }[k] || k },
    reasonType(k) { return { risk: 'danger', stop_loss: 'danger', sell: 'warning', timeout: 'info' }[k] || '' },
    calcPnlAmount(t) {
      const amt = (t.exit_price - t.entry_price) * 100
      return (amt >= 0 ? '+' : '') + amt.toFixed(0) + ' 元'
    }
  }
}
</script>

<style scoped>
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.header-card { border-radius: 8px; padding: 24px; text-align: center; }
.profit-bg { background: linear-gradient(135deg, #fff5f5, #fff); }
.loss-bg { background: linear-gradient(135deg, #f0f9eb, #fff); }
.header-main { margin-bottom: 8px; }
.pnl-big { font-size: 48px; font-weight: bold; line-height: 1.2; }
.pnl-amount { font-size: 20px; margin-top: 4px; }
.header-meta { font-size: 14px; color: #909399; display: flex; gap: 16px; justify-content: center; }
.stat { text-align: center; }
.t { font-size: 13px; color: #909399; margin-bottom: 4px; }
.v { font-size: 28px; font-weight: bold; margin: 4px 0; }
.m { font-size: 12px; color: #909399; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.pnl-large-bar-wrapper { height: 28px; background: #f5f7fa; border-radius: 14px; overflow: hidden; }
.pnl-large-bar { height: 100%; border-radius: 14px; transition: width .3s; min-width: 4px; }
.rule-list { display: flex; flex-wrap: wrap; }
</style>
