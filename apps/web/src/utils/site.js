import { ref } from 'vue'
import http from '@/utils/http'

const siteName = ref('持仓管理系统')
const siteDescription = ref('')
const siteLogo = ref('')
const siteFavicon = ref('')
const siteDomain = ref('')
const icpBeian = ref('')
const icpBeianUrl = ref('')
const siteStatus = ref('open')
const closeTip = ref('')
const timezone = ref('Asia/Shanghai')
const dateFormat = ref('YYYY-MM-DD')
const timeFormat = ref('HH:mm:ss')
const loaded = ref(false)

async function fetchPublicSettings() {
  try {
    const res = await http.get('/settings/public')
    const d = res.data
    siteName.value = d.site_name || '持仓管理系统'
    siteDescription.value = d.site_description || ''
    siteLogo.value = d.site_logo || ''
    siteFavicon.value = d.site_favicon || ''
    siteDomain.value = d.site_domain || ''
    icpBeian.value = d.icp_beian || ''
    icpBeianUrl.value = d.icp_beian_url || ''
    siteStatus.value = d.site_status || 'open'
    closeTip.value = d.close_tip || ''
    timezone.value = d.timezone || 'Asia/Shanghai'
    dateFormat.value = d.date_format || 'YYYY-MM-DD'
    timeFormat.value = d.time_format || 'HH:mm:ss'
    document.title = siteName.value
    if (siteFavicon.value) {
      let link = document.querySelector('link[rel*="icon"]')
      if (!link) {
        link = document.createElement('link')
        link.rel = 'icon'
        document.head.appendChild(link)
      }
      link.href = siteFavicon.value
    }
  } catch {
    // 默认值
  } finally {
    loaded.value = true
  }
}

function useSite() {
  if (!loaded.value) {
    fetchPublicSettings()
  }
  return {
    siteName, siteDescription, siteLogo, siteFavicon,
    siteDomain, icpBeian, icpBeianUrl,
    siteStatus, closeTip, timezone, dateFormat, timeFormat
  }
}

export { useSite, fetchPublicSettings }
