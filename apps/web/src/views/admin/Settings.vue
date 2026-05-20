<template>
  <div class="settings-page">
    <h2>系统设置</h2>

    <el-form :model="form" label-width="140px" v-loading="loading" style="max-width: 700px">

      <!-- 基本信息 -->
      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="网站名称">
        <el-input v-model="form.site_name" placeholder="显示在登录页、侧边栏和浏览器标题" />
      </el-form-item>
      <el-form-item label="网站副标题">
        <el-input v-model="form.site_description" placeholder="登录页标题下方的描述文字" />
      </el-form-item>
      <el-form-item label="网站 LOGO">
        <el-input v-model="form.site_logo" placeholder="LOGO 图片 URL">
          <template v-if="form.site_logo" #append>
            <el-popover trigger="hover" placement="top">
              <img :src="form.site_logo" style="max-width:200px;max-height:200px" />
              <template #reference>
                <el-button link>预览</el-button>
              </template>
            </el-popover>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item label="站点图标">
        <el-input v-model="form.site_favicon" placeholder="favicon URL（.ico / .png）" />
      </el-form-item>

      <!-- 域名与备案 -->
      <el-divider content-position="left">域名与备案</el-divider>
      <el-form-item label="网站域名">
        <el-input v-model="form.site_domain" placeholder="example.com" />
      </el-form-item>
      <el-form-item label="ICP 备案号">
        <el-input v-model="form.icp_beian" placeholder="沪ICP备XXXXXXXX号" />
      </el-form-item>
      <el-form-item label="ICP 备案链接">
        <el-input v-model="form.icp_beian_url" placeholder="https://beian.miit.gov.cn/" />
      </el-form-item>

      <!-- 地址 -->
      <el-divider content-position="left">地址</el-divider>
      <el-form-item label="官网地址">
        <el-input v-model="form.official_url" placeholder="https://example.com" />
      </el-form-item>
      <el-form-item label="前台访问地址">
        <el-input v-model="form.frontend_url" placeholder="前台部署地址" />
      </el-form-item>
      <el-form-item label="后台访问地址">
        <el-input v-model="form.backend_url" placeholder="后台 / API 地址" />
      </el-form-item>

      <!-- 站点状态 -->
      <el-divider content-position="left">站点状态</el-divider>
      <el-form-item label="站点状态">
        <el-switch
          v-model="siteOpen"
          active-text="开启"
          inactive-text="关闭"
          @change="form.site_status = siteOpen ? 'open' : 'closed'"
        />
      </el-form-item>
      <el-form-item v-if="!siteOpen" label="关闭提示语">
        <el-input v-model="form.close_tip" type="textarea" :rows="2" placeholder="站点关闭时显示的提示信息" />
      </el-form-item>

      <!-- 时区与格式 -->
      <el-divider content-position="left">时区与格式</el-divider>
      <el-form-item label="时区">
        <el-select v-model="form.timezone" style="width:100%">
          <el-option v-for="tz in timezones" :key="tz" :label="tz" :value="tz" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期格式">
        <el-select v-model="form.date_format" style="width:100%">
          <el-option label="YYYY-MM-DD" value="YYYY-MM-DD" />
          <el-option label="YYYY/MM/DD" value="YYYY/MM/DD" />
          <el-option label="DD/MM/YYYY" value="DD/MM/YYYY" />
          <el-option label="YYYY年MM月DD日" value="YYYY年MM月DD日" />
        </el-select>
      </el-form-item>
      <el-form-item label="时间格式">
        <el-select v-model="form.time_format" style="width:100%">
          <el-option label="HH:mm:ss" value="HH:mm:ss" />
          <el-option label="HH:mm" value="HH:mm" />
          <el-option label="hh:mm:ss A" value="hh:mm:ss A" />
        </el-select>
      </el-form-item>

      <!-- DingTalk -->
      <el-divider content-position="left">钉钉机器人</el-divider>
      <el-form-item label="Webhook 地址">
        <el-input v-model="form.dingtalk_webhook" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" />
      </el-form-item>
      <el-form-item label="加签密钥">
        <el-input v-model="form.dingtalk_secret" placeholder="SEC...（留空则不签名）" />
      </el-form-item>

      <!-- Session -->
      <el-divider content-position="left">会话</el-divider>
      <el-form-item label="Session 过期时间">
        <el-input-number v-model="form.session_expire_minutes" :min="1" :max="1440" />
        <span class="hint">分钟（1~1440，过期后需重新登录）</span>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="saving" @click="saveSettings">保存设置</el-button>
        <el-button @click="fetchSettings">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSystemSettings, updateSystemSettings } from '@/api/admin'

const loading = ref(false)
const saving = ref(false)

const form = ref({
  site_name: '',
  site_description: '',
  site_logo: '',
  site_favicon: '',
  site_domain: '',
  icp_beian: '',
  icp_beian_url: '',
  official_url: '',
  frontend_url: '',
  backend_url: '',
  site_status: 'open',
  close_tip: '',
  timezone: 'Asia/Shanghai',
  date_format: 'YYYY-MM-DD',
  time_format: 'HH:mm:ss',
  session_expire_minutes: 30,
  dingtalk_webhook: '',
  dingtalk_secret: ''
})

const siteOpen = computed({
  get: () => form.value.site_status !== 'closed',
  set: (v) => { form.value.site_status = v ? 'open' : 'closed' }
})

const timezones = [
  'Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Tokyo',
  'Asia/Singapore', 'America/New_York', 'America/Chicago',
  'America/Los_Angeles', 'Europe/London', 'Europe/Berlin',
  'Europe/Paris', 'Australia/Sydney', 'UTC'
]

async function fetchSettings() {
  loading.value = true
  try {
    const res = await getSystemSettings()
    Object.assign(form.value, res.data)
  } catch (e) {
    ElMessage.error('获取设置失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await updateSystemSettings(form.value)
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error('保存设置失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
.settings-page {
  padding: 20px;
}
.settings-page h2 {
  margin-bottom: 20px;
}
.hint {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}
</style>
