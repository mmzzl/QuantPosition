<template>
  <div class="sector-heatmap">
    <div class="page-header">
      <h2>板块热力图</h2>
      <div class="controls">
        <el-radio-group v-model="selectedPeriod" @change="fetchHeatmap">
          <el-radio-button label="24h">24小时</el-radio-button>
          <el-radio-button label="7d">7天</el-radio-button>
          <el-radio-button label="30d">30天</el-radio-button>
          <el-radio-button label="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="selectedPeriod === 'custom'"
          v-model="dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="fetchHeatmap"
          style="margin-left: 10px"
        />
      </div>
    </div>

    <div v-loading="loading" class="heatmap-grid">
      <div
        v-for="sector in sectors"
        :key="sector.sector_name"
        class="heatmap-cell"
        :style="{ backgroundColor: getHeatmapColor(sector.change_pct) }"
        @click="goToStockList(sector.sector_name)"
      >
        <div class="cell-name">{{ sector.sector_name }}</div>
        <div class="cell-change" :class="sector.change_pct >= 0 ? 'up' : 'down'">
          {{ sector.change_pct >= 0 ? '+' : '' }}{{ sector.change_pct }}%
        </div>
        <div class="cell-count">{{ sector.stock_count }} 只</div>
      </div>
    </div>

    <el-empty v-if="!loading && sectors.length === 0" description="暂无数据" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSectorHeatmap } from '@/api/sectors'

const router = useRouter()
const loading = ref(false)
const sectors = ref([])
const selectedPeriod = ref('7d')
const dateRange = ref([])

function getHeatmapColor(changePct) {
  if (changePct === 0) return '#909399'
  const absChange = Math.min(Math.abs(changePct), 10)
  if (changePct > 0) {
    const intensity = 0.3 + (absChange / 10) * 0.7
    return `rgba(245, 108, 108, ${intensity})`
  } else {
    const intensity = 0.3 + (absChange / 10) * 0.7
    return `rgba(103, 194, 58, ${intensity})`
  }
}

async function fetchHeatmap() {
  loading.value = true
  try {
    const params = { period: selectedPeriod.value }
    if (selectedPeriod.value === 'custom' && dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getSectorHeatmap(params)
    sectors.value = res.data.sectors || []
  } catch (e) {
    ElMessage.error('获取热力图数据失败')
  } finally {
    loading.value = false
  }
}

function goToStockList(sectorName) {
  router.push({
    name: 'SectorStockList',
    params: { sectorName },
    query: { period: selectedPeriod.value }
  })
}

onMounted(() => {
  fetchHeatmap()
})
</script>

<style scoped>
.sector-heatmap {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.controls {
  display: flex;
  align-items: center;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  min-height: 400px;
}

.heatmap-cell {
  padding: 15px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 80px;
}

.heatmap-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.cell-name {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  text-align: center;
  margin-bottom: 5px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.cell-change {
  font-size: 16px;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.cell-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 5px;
}
</style>
