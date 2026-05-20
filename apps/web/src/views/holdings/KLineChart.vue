<template>
  <div class="kline-chart">
    <div ref="chartRef" :style="{ width, height }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, required: true },
  title: { type: String, default: '' },
  width: { type: String, default: '100%' },
  height: { type: String, default: '500px' }
})

const chartRef = ref(null)
let chartInstance = null

function renderChart() {
  if (!chartRef.value || !props.data.length) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const dates = props.data.map(d => d.date)
  const ohlc = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map(d => d.volume)

  const option = {
    title: { text: props.title, left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [
      { left: '10%', right: '8%', top: '15%', height: '50%' },
      { left: '10%', right: '8%', top: '70%', height: '20%' }
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1 }
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisTick: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: '5%', start: 0, end: 100 }
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc,
        itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' }
      },
      {
        name: '成交量', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (p) => p.value >= 0 ? '#ef232a' : '#14b143' }
      }
    ]
  }

  chartInstance.setOption(option, true)
  chartInstance.resize()
}

function handleResize() {
  chartInstance?.resize()
}

watch(() => props.data, renderChart, { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({ getChart: () => chartInstance })
</script>

<style scoped>
.kline-chart {
  padding: 10px;
}
</style>
