<template>
  <div class="buy-page">
    <div class="page-header">
      <h2>买入持仓</h2>
      <el-button @click="$router.push('/holdings')">返回持仓列表</el-button>
    </div>

    <el-card>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 500px">
        <el-form-item label="股票代码" prop="code">
          <el-input v-model="form.code" placeholder="例如: 600000" @blur="fetchStockInfo" />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="form.name" placeholder="自动获取" :disabled="true" />
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="100" :step="100" />
          <span style="margin-left: 10px; color: #999">股</span>
        </el-form-item>
        <el-form-item label="成本价" prop="averageCost">
          <el-input-number v-model="form.averageCost" :precision="2" :min="0.01" />
          <span style="margin-left: 10px; color: #999">元/股</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading" style="width: 100%">
            确认买入
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { buyHolding } from '@/api/holdings'
import { getStockName } from '@/utils/stock'

const router = useRouter()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  code: '',
  name: '',
  quantity: 100,
  averageCost: 0,
  note: ''
})

const rules = {
  code: [
    { required: true, message: '请输入股票代码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '股票代码为6位数字', trigger: 'blur' }
  ],
  quantity: [
    { required: true, message: '请输入数量', trigger: 'blur' },
    { type: 'number', min: 100, message: '数量至少100股', trigger: 'blur' }
  ],
  averageCost: [
    { required: true, message: '请输入成本价', trigger: 'blur' },
    { type: 'number', min: 0.01, message: '成本价必须大于0', trigger: 'blur' }
  ]
}

async function fetchStockInfo() {
  if (form.code && form.code.length === 6) {
    try {
      const name = await getStockName(form.code)
      if (name) {
        form.name = name
      }
    } catch (e) {
      // 忽略错误
    }
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  loading.value = true
  try {
    await buyHolding(form.code, form.name || null, form.quantity, form.averageCost)
    ElMessage.success('买入成功')
    router.push('/holdings')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '买入失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {})
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
</style>