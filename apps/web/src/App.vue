<template>
  <div id="app">
    <router-view v-slot="{ Component }">
      <transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
</script>

<style>
/* ============================================
   全局主题 — 量化研究终端 · 明亮专业
   ============================================ */

:root {
  /* — 背景层次 — */
  --bg-base: #f1f5f9;
  --bg-surface: #ffffff;
  --bg-elevated: #f8fafc;
  --bg-hover: #f1f5f9;

  /* — 文字层次 — */
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-muted: #94a3b8;

  /* — 主色调：专业蓝 — */
  --accent: #2563eb;
  --accent-hover: #3b82f6;
  --accent-soft: rgba(37, 99, 235, 0.08);
  --accent-glow: rgba(37, 99, 235, 0.2);

  /* — 交互色 — */
  --info: #0891b2;
  --info-soft: rgba(8, 145, 178, 0.08);

  /* — 涨跌色（中国股市惯例） — */
  --up: #dc2626;
  --up-soft: rgba(220, 38, 38, 0.08);
  --down: #16a34a;
  --down-soft: rgba(22, 163, 74, 0.08);

  /* — 边框 — */
  --border: #e2e8f0;
  --border-strong: #cbd5e1;

  /* — 卡片 — */
  --card-bg: #ffffff;
  --card-blur: blur(0px);

  /* — 阴影 — */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.04);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04);

  /* — 圆角 — */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* — 字体 — */
  --font-ui: 'DM Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'Consolas', monospace;
  --font-display: 'Sora', 'PingFang SC', sans-serif;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: var(--font-ui);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
  font-size: 14px;
}

body {
  background-color: var(--bg-base);
  min-height: 100vh;
}

/* ============================================
   Element Plus 亮色专业覆盖
   ============================================ */

/* — 按钮 — */
.el-button {
  font-family: var(--font-ui);
  font-weight: 500;
  font-size: 13px;
  border-radius: var(--radius-sm);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  letter-spacing: 0.3px;
}

.el-button--primary {
  --el-color-primary: var(--accent);
  background: var(--accent) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.el-button--primary:hover {
  background: #1d4ed8 !important;
  border-color: #1d4ed8 !important;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.el-button--danger {
  background: var(--up) !important;
  border: 1px solid var(--up) !important;
  box-shadow: var(--shadow-sm);
}

.el-button--default {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-strong) !important;
  color: var(--text-secondary) !important;
}

.el-button--default:hover {
  background: var(--bg-elevated) !important;
  color: var(--accent) !important;
  border-color: var(--accent) !important;
}

/* — 卡片 — */
.el-card {
  background: var(--card-bg) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-sm);
  color: var(--text-primary);
}

.el-card.is-always-shadow {
  box-shadow: var(--shadow-sm) !important;
}

.el-card__header {
  border-bottom: 1px solid var(--border) !important;
  padding: 14px 20px !important;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-elevated);
}

.el-card__body {
  padding: 20px !important;
}

/* — 表格 — */
.el-table {
  background: transparent !important;
  color: var(--text-primary);
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-border-color: var(--border);
  --el-table-hover-bg-color: #f1f5f9;
  --el-table-text-color: var(--text-primary);
  --el-table-header-text-color: var(--text-secondary);
  font-size: 13px;
}

.el-table th.el-table__cell {
  background: var(--bg-elevated) !important;
  border-bottom: 2px solid var(--border) !important;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted) !important;
}

.el-table td.el-table__cell {
  border-bottom: 1px solid var(--border) !important;
  padding: 10px 12px !important;
}

.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: #f8fafc !important;
}

.el-table__body tr:hover > td.el-table__cell {
  background: #eef2ff !important;
}

/* — 输入框 — */
.el-input__wrapper {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-strong) !important;
  box-shadow: none !important;
  border-radius: var(--radius-sm) !important;
  transition: all 0.2s;
}

.el-input__wrapper:hover {
  border-color: #94a3b8 !important;
}

.el-input__wrapper.is-focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
}

.el-input__inner {
  color: var(--text-primary) !important;
  font-size: 13px;
}

.el-input__inner::placeholder {
  color: var(--text-muted) !important;
}

/* — 下拉选择/级联/日期 — */
.el-select__wrapper,
.el-cascader__wrapper {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-strong) !important;
  box-shadow: none !important;
  border-radius: var(--radius-sm) !important;
}

/* — 弹出层（下拉菜单/选择器面板） — */
.el-popper.is-light {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--shadow-lg) !important;
  border-radius: var(--radius-md) !important;
}

.el-select-dropdown__item {
  color: var(--text-primary) !important;
  font-size: 13px;
}

.el-select-dropdown__item.hover,
.el-select-dropdown__item:hover {
  background: var(--accent-soft) !important;
}

.el-select-dropdown__item.selected {
  color: var(--accent) !important;
  font-weight: 600;
}

/* — 对话框 — */
.el-dialog {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) !important;
  box-shadow: var(--shadow-lg);
}

.el-dialog__header {
  border-bottom: 1px solid var(--border);
  padding: 18px 24px !important;
}

.el-dialog__title {
  color: var(--text-primary) !important;
  font-weight: 600;
  font-size: 16px;
}

.el-dialog__body {
  padding: 24px !important;
  color: var(--text-primary);
}

.el-dialog__footer {
  border-top: 1px solid var(--border);
  padding: 14px 24px !important;
}

/* — 分页 — */
.el-pagination {
  --el-pagination-bg-color: transparent;
  --el-pagination-button-bg-color: var(--bg-surface);
  --el-pagination-hover-color: var(--accent);
  --el-pagination-text-color: var(--text-secondary);
}

.el-pagination .btn-prev,
.el-pagination .btn-next,
.el-pagination .el-pager li {
  background: var(--bg-surface) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm);
  margin: 0 2px;
  font-size: 13px;
}

.el-pagination .el-pager li.is-active {
  background: var(--accent) !important;
  color: #fff !important;
  border-color: var(--accent) !important;
  font-weight: 600;
}

.el-pagination button:disabled {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
}

/* — 菜单 — */
.el-menu {
  border-right: none !important;
}

/* — 标签 — */
.el-tag {
  border-radius: 4px;
  font-weight: 500;
  font-size: 12px;
}

/* — 表单 — */
.el-form-item__label {
  color: var(--text-secondary) !important;
  font-weight: 500;
  font-size: 13px;
}

/* — 单选按钮组 — */
.el-radio-button__inner {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border-strong) !important;
  color: var(--text-secondary) !important;
  transition: all 0.2s;
  font-size: 13px;
}

.el-radio-button__inner:hover {
  color: var(--accent) !important;
}

.el-radio-button__original-radio:checked + .el-radio-button__inner {
  background: var(--accent) !important;
  color: #fff !important;
  border-color: var(--accent) !important;
  font-weight: 600;
}

/* — 日期选择器 — */
.el-date-editor.el-input__wrapper {
  background: var(--bg-surface) !important;
}

/* — 空状态 — */
.el-empty__description p {
  color: var(--text-muted);
}

/* — 警告提示 — */
.el-alert--warning {
  background: #fffbeb !important;
  border: 1px solid #fde68a !important;
}

/* — Loading 遮罩 — */
.el-loading-mask {
  background: rgba(255, 255, 255, 0.6) !important;
}

/* — 滚动条 — */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* — 页面过渡动画 — */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* — 全局工具类 — */
.font-mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.text-up {
  color: var(--up);
  font-weight: 600;
}

.text-down {
  color: var(--down);
  font-weight: 600;
}
</style>
