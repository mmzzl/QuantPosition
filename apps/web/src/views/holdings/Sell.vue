<template>
  <div class="sell-page">
    <div class="page-header">
      <h2>卖出持仓</h2>
      <el-button @click="$router.push('/holdings')">返回持仓列表</el-button>
    </div>

    <el-card v-if="holding">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="股票代码">{{ holding.code }}</el-descriptions-item>
        <el-descriptions-item label="股票名称">{{ holding.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持有数量">{{ holding.quantity }} 股</el-descriptions-item>
        <el-descriptions-item label="成本价">{{ holding.average_cost?.toFixed(2) }} 元</el-descriptions-item>
        <el-descriptions-item label="当前价格">{{ holding.current_price?.toFixed(2) || '-' }} 元</el-descriptions-item>
        <el-descriptions-item label="市值">{{ holding.market_value?.toFixed(2) || '-' }} 元</el-descriptions-item>
        <el-descriptions-item label="未实现盈亏">
          <span :class="holding.unrealized_pnl >= 0 ? 'profit' : 'loss'">
            {{ holding.unrealized_pnl?.toFixed(2) || '-' }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="盈亏比例">
          <span :class="holding.profit_rate >= 0 ? 'profit' : 'loss'">
            {{ holding.profit_rate ? holding.profit_rate.toFixed(2) + '%' : '-' }}
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 500px">
        <el-form-item label="卖出数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="1" :max="holding.quantity" />
          <el-button size="small" @click="form.quantity = holding.quantity" style="margin-left: 10px">
            全部
          </el-button>
        </el-form-item>
        <el-form-item label="卖出价格" prop="price">
          <el-input-number v-model="form.price" :precision="2" :min="0.01" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading" style="width: 100%">
            确认卖出
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-empty v-else description="加载中..." />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getHoldings, sellHolding } from '@/api/holdings'

const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const loading = ref(false)
const holding = ref(null)

const form = reactive({
  quantity: 1,
  price: 0
})

const rules = {
  quantity: [
    { required: true, message: '请输入卖出数量', trigger: 'blur' },
    { type: 'number', min: 1, message: '卖出数量至少1股', trigger: 'blur' }
  ],
  price: [
    { required: true, message: '请输入卖出价格', trigger: 'blur' },
    { type: 'number', min: 0.01, message: '价格必须大于0', trigger: 'blur' }
  ]
}

async function fetchHolding() {
  const code = route.params.code
  try {
    const res = await getHoldings(1, 100)
    const holdings = res.data.items || []
    holding.value = holdings.find(h => h.code === code)

    if (holding.value) {
      form.price = holding.value.current_price || holding.value.average_cost
    } else {
      ElMessage.error('持仓不存在')
      router.push('/holdings')
    }
  } catch (e) {
    ElMessage.error('获取持仓信息失败')
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  const code = route.params.code
  loading.value = true
  try {
    await sellHolding(code, form.quantity, form.price)
    ElMessage.success('卖出成功')
    router.push('/holdings')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '卖出失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHolding()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}

.profit {
  color: #f56c6c;
}

.loss {
  color: #67c23a;
}
</style>