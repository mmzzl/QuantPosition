<template>
  <div class="news-view">
    <div class="page-header">
      <h2>新闻浏览</h2>
      <div class="controls">
        <el-radio-group v-model="selectedPeriod" @change="fetchData">
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
          @change="fetchData"
          style="margin-left: 10px"
        />
        <el-button @click="fetchData" :loading="loading" style="margin-left: 10px">刷新</el-button>
      </div>
    </div>

    <div v-loading="loading">
      <el-card v-for="item in news" :key="item.code" class="news-card" shadow="hover">
        <div class="news-header">
          <h3 class="news-title">{{ item.title }}</h3>
          <span class="news-time">{{ item.showTime }}</span>
        </div>
        <p class="news-summary">{{ item.summary }}</p>
        <div v-if="item.stockList && item.stockList.length" class="news-tags">
          <el-tag v-for="tag in item.stockList" :key="tag" size="small">{{ tag }}</el-tag>
        </div>
      </el-card>

      <el-empty v-if="!loading && news.length === 0" description="暂无新闻" />

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
        style="margin-top: 20px; justify-content: center"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNews } from '@/api/news'

const loading = ref(false)
const news = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedPeriod = ref('24h')
const dateRange = ref([])

async function fetchData() {
  loading.value = true
  try {
    const params = { period: selectedPeriod.value, page: page.value, page_size: pageSize.value }
    if (selectedPeriod.value === 'custom' && dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getNews(params)
    news.value = res.data.news || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取新闻失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => { fetchData() })
</script>

<style scoped>
.news-view {
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
.news-card {
  margin-bottom: 12px;
}
.news-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.news-title {
  font-size: 16px;
  margin: 0;
  flex: 1;
  line-height: 1.4;
}
.news-time {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  margin-left: 16px;
}
.news-summary {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin: 0 0 8px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.news-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
