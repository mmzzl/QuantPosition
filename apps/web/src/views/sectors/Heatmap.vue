<template>
  <div class="sector-heatmap">
    <!-- 页头 -->
    <div class="section-header">
      <div class="header-left">
        <h1 class="header-title">板块热力图</h1>
        <p class="header-desc">板块涨跌分布 · 点击查看成分股</p>
      </div>
      <div class="header-right">
        <div class="period-switch">
          <button
            v-for="p in periods" :key="p.value"
            class="period-btn" :class="{ active: selectedPeriod === p.value }"
            @click="selectedPeriod = p.value; fetchHeatmap()"
          >{{ p.label }}</button>
        </div>
        <el-date-picker
          v-if="selectedPeriod === 'custom'"
          v-model="dateRange" type="daterange"
          start-placeholder="开始" end-placeholder="结束"
          format="YYYY-MM-DD" value-format="YYYY-MM-DD"
          @change="fetchHeatmap" size="small" style="margin-left:10px"
        />
      </div>
    </div>

    <!-- 涨跌概览 -->
    <div class="overview-strip" v-if="!loading && sectors.length > 0">
      <div class="ov-item"><span class="ov-label">上涨</span><span class="ov-value text-up font-mono">{{ upCount }}</span></div>
      <span class="ov-sep">|</span>
      <div class="ov-item"><span class="ov-label">下跌</span><span class="ov-value text-down font-mono">{{ downCount }}</span></div>
      <span class="ov-sep">|</span>
      <div class="ov-item"><span class="ov-label">平盘</span><span class="ov-value font-mono" style="color:var(--text-muted)">{{ flatCount }}</span></div>
      <span class="ov-sep">|</span>
      <div class="ov-item" v-if="topGainer">
        <span class="ov-label">最强</span>
        <span class="ov-value text-up font-mono">{{ topGainer.sector_name }} +{{ topGainer.change_pct }}%</span>
      </div>
      <span class="ov-sep">|</span>
      <div class="ov-item" v-if="topLoser">
        <span class="ov-label">最弱</span>
        <span class="ov-value text-down font-mono">{{ topLoser.sector_name }} {{ topLoser.change_pct }}%</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-box" v-if="!loading && sectors.length === 0">
      <p class="empty-title">暂无热力图数据</p>
      <p class="empty-desc">K 线数据可能尚未采集，请先运行 K 线爬虫</p>
    </div>

    <!-- 热力图网格 -->
    <div v-loading="loading" class="heatgrid" v-if="sectors.length > 0 || loading">
      <div
        v-for="s in sectors" :key="s.sector_name"
        class="hcell" :class="cellClass(s.change_pct)"
        :style="cellStyle(s.change_pct)"
        @click="goToStockList(s.sector_name)"
      >
        <div class="hcell-name">{{ s.sector_name }}</div>
        <div class="hcell-pct font-mono">{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct }}%</div>
        <div class="hcell-count">{{ s.stock_count }} 只</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSectorHeatmap } from '@/api/sectors'

const router = useRouter()
const loading = ref(false)
const sectors = ref([])
const selectedPeriod = ref('7d')
const dateRange = ref([])

const periods = [
  { label: '24小时', value: '24h' },
  { label: '7天', value: '7d' },
  { label: '30天', value: '30d' },
  { label: '自定义', value: 'custom' },
]

const upCount = computed(() => sectors.value.filter(s => s.change_pct > 0).length)
const downCount = computed(() => sectors.value.filter(s => s.change_pct < 0).length)
const flatCount = computed(() => sectors.value.filter(s => s.change_pct === 0).length)
const topGainer = computed(() => sectors.value.length ? [...sectors.value].sort((a,b) => b.change_pct - a.change_pct)[0] : null)
const topLoser = computed(() => sectors.value.length ? [...sectors.value].sort((a,b) => a.change_pct - b.change_pct)[0] : null)

function cellClass(v) {
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}
function cellStyle(v) {
  if (v === 0) return {}
  const a = Math.min(Math.abs(v), 10)
  if (v > 0) return { '--intensity': 0.25 + (a/10)*0.55, '--cell': '220, 38, 38' }
  return { '--intensity': 0.25 + (a/10)*0.55, '--cell': '22, 163, 74' }
}

async function fetchHeatmap() {
  loading.value = true
  try {
    const p = { period: selectedPeriod.value }
    if (selectedPeriod.value === 'custom' && dateRange.value) {
      p.start_date = dateRange.value[0]; p.end_date = dateRange.value[1]
    }
    const r = await getSectorHeatmap(p)
    sectors.value = r.data.sectors || []
  } catch (e) { ElMessage.error('获取热力图数据失败') }
  finally { loading.value = false }
}

function goToStockList(name) {
  router.push({ name: 'SectorStockList', params: { sectorName: name }, query: { period: selectedPeriod.value } })
}

onMounted(() => fetchHeatmap())
</script>

<style scoped>
.sector-heatmap { display: flex; flex-direction: column; gap: 16px; }

/* 页头 */
.section-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.header-title { font-family: var(--font-display); font-size: 20px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px; }
.header-desc { font-size: 12px; color: var(--text-muted); }
.header-right { display: flex; align-items: center; }

.period-switch { display: flex; gap: 1px; background: var(--bg-surface); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 2px; }
.period-btn {
  padding: 5px 14px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 12px; font-family: var(--font-ui); font-weight: 500;
  border-radius: 4px; cursor: pointer; transition: all 0.15s;
}
.period-btn:hover { color: var(--text-primary); }
.period-btn.active { background: var(--accent); color: #fff; font-weight: 600; }

/* 概览 */
.overview-strip {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 18px; background: #fff;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm); flex-wrap: wrap;
}
.ov-item { display: flex; align-items: center; gap: 6px; }
.ov-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.3px; }
.ov-value { font-size: 13px; font-weight: 600; }
.ov-sep { color: var(--border); font-size: 16px; user-select: none; }

/* 空状态 */
.empty-box {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 20px; text-align: center;
  background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md);
}
.empty-title { font-size: 15px; color: var(--text-secondary); margin-bottom: 6px; font-weight: 500; }
.empty-desc { font-size: 12px; color: var(--text-muted); }

/* 热力图网格 */
.heatgrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 6px; min-height: 180px;
}

.hcell {
  position: relative; border-radius: var(--radius-sm); cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4,0,0.2,1); overflow: hidden;
  min-height: 82px; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 10px; gap: 2px;
  background: rgba(var(--cell, 148,163,184), calc(var(--intensity, 0.2) * 0.7));
  border: 1px solid rgba(var(--cell, 148,163,184), calc(var(--intensity, 0.2) * 0.5));
}

.hcell.up { color: #fff; }
.hcell.down { color: #fff; }
.hcell.flat {
  background: var(--bg-surface);
  border: 1px solid var(--border);
}

.hcell:hover {
  transform: translateY(-2px) scale(1.02);
  z-index: 1;
  box-shadow: 0 6px 18px rgba(0,0,0,0.1), 0 0 12px rgba(var(--cell, 100,100,100), 0.2);
}

.hcell-name {
  font-size: 13px; font-weight: 600;
  color: rgba(255,255,255,0.95);
  text-shadow: 0 1px 3px rgba(0,0,0,0.2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 130px;
}
.hcell.flat .hcell-name { color: var(--text-secondary); text-shadow: none; }

.hcell-pct { font-size: 17px; font-weight: 700; color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.hcell.flat .hcell-pct { color: var(--text-muted); text-shadow: none; }

.hcell-count { font-size: 11px; color: rgba(255,255,255,0.7); text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
.hcell.flat .hcell-count { color: var(--text-muted); text-shadow: none; }
</style>
