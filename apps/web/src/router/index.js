import { createRouter, createWebHistory } from 'vue-router'
import { getToken, removeToken, getUserRole, getUserPermissions } from '@/utils/auth'
import Login from '@/views/Login.vue'
import Register from '@/views/Register.vue'
import Layout from '@/views/Layout.vue'
import Dashboard from '@/views/Dashboard.vue'
import HoldingsList from '@/views/holdings/List.vue'
import HoldingsBuy from '@/views/holdings/Buy.vue'
import HoldingsSell from '@/views/holdings/Sell.vue'
import HoldingsHistory from '@/views/holdings/History.vue'
import HoldingsSummary from '@/views/holdings/Summary.vue'
import AdminUsers from '@/views/admin/Users.vue'
import AdminRoles from '@/views/admin/Roles.vue'
import AdminHoldings from '@/views/admin/Holdings.vue'
import AdminSettings from '@/views/admin/Settings.vue'
import SectorHeatmap from '@/views/sectors/Heatmap.vue'
import SectorStockList from '@/views/sectors/StockList.vue'
import DualMASelection from '@/views/selections/DualMA.vue'
import NewsSelection from '@/views/selections/NewsSelection.vue'
import HeatmapSelection from '@/views/selections/HeatmapSelection.vue'
import NewsView from '@/views/NewsView.vue'
import TradingRules from '@/views/TradingRules.vue'
import RuleCandidates from '@/views/RuleCandidates.vue'
import RuleOptimized from '@/views/RuleOptimized.vue'
import BacktestDashboard from '@/views/backtest/BacktestDashboard.vue'
import BacktestDetail from '@/views/backtest/BacktestDetail.vue'
import PaperTrading from '@/views/paper/PaperTrading.vue'

const routes = [
  {
    path: '/',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: { title: '首页', permission: null }
      },
      {
        path: 'holdings',
        name: 'HoldingsList',
        component: HoldingsList,
        meta: { title: '持仓管理', permission: 'holdings:view', menuPath: '/holdings' }
      },
      {
        path: 'holdings/buy',
        name: 'HoldingsBuy',
        component: HoldingsBuy,
        meta: { title: '买入', permission: 'holdings:edit', menuPath: '/holdings' }
      },
      {
        path: 'holdings/sell/:code',
        name: 'HoldingsSell',
        component: HoldingsSell,
        meta: { title: '卖出', permission: 'holdings:edit', menuPath: '/holdings' }
      },
      {
        path: 'holdings/history',
        name: 'HoldingsHistory',
        component: HoldingsHistory,
        meta: { title: '历史记录', permission: 'holdings:view', menuPath: '/holdings' }
      },
      {
        path: 'holdings/summary',
        name: 'HoldingsSummary',
        component: HoldingsSummary,
        meta: { title: '持仓汇总', permission: 'holdings:view', menuPath: '/holdings' }
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: AdminUsers,
        meta: { requiresAdmin: true, title: '用户管理', permission: 'users:view', menuPath: '/admin/users' }
      },
      {
        path: 'admin/roles',
        name: 'AdminRoles',
        component: AdminRoles,
        meta: { requiresAdmin: true, title: '角色管理', permission: 'roles:view', menuPath: '/admin/roles' }
      },
      {
        path: 'admin/holdings',
        name: 'AdminHoldings',
        component: AdminHoldings,
        meta: { requiresAdmin: true, title: '持仓管理', permission: 'holdings:view', menuPath: '/admin/holdings' }
      },
      {
        path: 'admin/settings',
        name: 'AdminSettings',
        component: AdminSettings,
        meta: { requiresAdmin: true, title: '系统设置', permission: 'settings:view', menuPath: '/admin/settings' }
      },
      {
        path: 'sectors/heatmap',
        name: 'SectorHeatmap',
        component: SectorHeatmap,
        meta: { requiresAdmin: true, title: '板块热力图', permission: 'holdings:view', menuPath: '/sectors/heatmap' }
      },
      {
        path: 'sectors/:sectorName/stocks',
        name: 'SectorStockList',
        component: SectorStockList,
        meta: { requiresAdmin: true, title: '板块股票列表', permission: 'holdings:view', menuPath: '/sectors' }
      },
      {
        path: 'selections/dual-ma',
        name: 'DualMASelection',
        component: DualMASelection,
        meta: { title: '双均线选股', permission: 'selections:view', menuPath: '/selections/dual-ma' }
      },
      {
        path: 'selections/news',
        name: 'NewsSelection',
        component: NewsSelection,
        meta: { requiresAdmin: true, title: '新闻选股', permission: 'selections:view', menuPath: '/selections/news' }
      },
      {
        path: 'selections/heatmap',
        name: 'HeatmapSelection',
        component: HeatmapSelection,
        meta: { title: '热力图选股', permission: 'selections:view', menuPath: '/selections/heatmap' }
      },
      {
        path: 'news',
        name: 'NewsView',
        component: NewsView,
        meta: { requiresAdmin: true, title: '新闻浏览', permission: 'holdings:view', menuPath: '/news' }
      },
      {
        path: 'rules',
        name: 'TradingRules',
        component: TradingRules,
        meta: { requiresAdmin: true, title: '交易规则', permission: 'rules:view', menuPath: '/rules' }
      },
      {
        path: 'candidates',
        name: 'RuleCandidates',
        component: RuleCandidates,
        meta: { requiresAdmin: true, title: '候选规则', permission: 'rules:view', menuPath: '/rules' }
      },
      {
        path: 'rules/optimized',
        name: 'RuleOptimized',
        component: RuleOptimized,
        meta: { requiresAdmin: true, title: '优化后的候选规则', permission: 'rules:view', menuPath: '/rules' }
      },
      {
        path: 'backtest',
        name: 'BacktestDashboard',
        component: BacktestDashboard,
        meta: { requiresAdmin: true, title: '策略回测', permission: 'holdings:view', menuPath: '/backtest' }
      },
      {
        path: 'backtest/detail',
        name: 'BacktestDetail',
        component: BacktestDetail,
        meta: { requiresAdmin: true, title: '交易详情', permission: 'holdings:view', menuPath: '/backtest' }
      },
      {
        path: 'rules/candidates/detail',
        name: 'CandidateTradeDetail',
        component: BacktestDetail,
        meta: { requiresAdmin: true, title: '候选规则交易详情', permission: 'rules:view', menuPath: '/rules' }
      },
      {
        path: 'paper-trading',
        name: 'PaperTrading',
        component: PaperTrading,
        meta: { requiresAdmin: true, title: '模拟盘', permission: 'holdings:view', menuPath: '/paper-trading' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = getToken()
  const requiresAuth = to.meta.requiresAuth !== false
  const requiresAdmin = to.meta.requiresAdmin === true
  const requiredPermission = to.meta.permission

  if (requiresAuth && !token) {
    next('/')
    return
  }

  if (requiresAdmin && token) {
    const role = getUserRole()
    if (role !== 'admin' && role !== 'super_admin' && role !== 'system_admin' && role !== 'normal_admin') {
      next('/dashboard')
      return
    }
  }

  if (requiredPermission && token) {
    const role = getUserRole()
    if (role === 'admin' || role === 'super_admin' || role === 'normal_admin' || role === 'system_admin') {
      next()
      return
    }
    const permissions = getUserPermissions()
    if (!permissions.includes(requiredPermission)) {
      next('/dashboard')
      return
    }
  }

  next()
})

export default router