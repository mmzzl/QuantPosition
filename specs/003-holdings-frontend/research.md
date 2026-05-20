# Research: 持仓管理系统 + Vue3 前端

## 技术决策

### 1. 股票行情 API - 新浪财经

**Decision**: 使用新浪财经 A 股行情接口

**Rationale**:
- 新浪 API 免费、无需认证
- 接口稳定，A 股数据全面
- 返回 JSON 格式，易于解析

**Alternatives considered**:
- 腾讯财经 API (接口格式类似)
- 东方财富 API (需要 key)
- 最终选择新浪，因其最简单且稳定

**接口格式**:
```
http://hq.sinajs.cn/list=sh600000
返回: var hq_str_sh600000="浦发银行,10.50,10.80,..."
```

### 2. 前端框架 - Vue 3 + Element Plus

**Decision**: Vue 3 + Vite + Element Plus + Axios

**Rationale**:
- Element Plus 是 Vue 3 的官方 UI 组件库
- Vite 提供极快的开发启动和热更新
- Axios 是最流行的 HTTP 客户端
- 中文文档丰富，便于开发

**Alternatives considered**:
- Vue 2 + Element UI (已过时)
- React + Ant Design (团队更熟悉 Vue)
- 最终选择 Vue 3，因团队需求且 Element Plus 成熟

### 3. 后端认证 - JWT

**Decision**: 使用 JWT (python-jose) 进行身份验证

**Rationale**:
- 无状态认证，适合前后端分离
- FastAPI 生态成熟
- 支持 token 过期和刷新

**Alternatives considered**:
- Session (需要服务端存储)
- OAuth2 (过于复杂)
- 最终选择 JWT，因实现简单且符合需求

### 4. 数据库 - MongoDB

**Decision**: 继续使用 MongoDB (现有)

**Rationale**:
- 项目已使用 MongoDB
- 持仓数据结构灵活，适合文档数据库
- pymongo 驱动成熟

**Alternatives considered**:
- PostgreSQL (需要迁移)
- MySQL (不适合持仓场景)
- 继续使用 MongoDB

## 实现模式

### 前端项目结构
```
apps/web/
├── src/
│   ├── api/          # API 调用
│   ├── components/   # 公共组件
│   ├── views/        # 页面视图
│   ├── router/       # 路由配置
│   ├── store/        # 状态管理
│   └── utils/        # 工具函数
├── public/
└── package.json
```

### 后端 holdings.py 实现要点
1. holdings 集合存储持仓信息
2. transactions 集合存储交易记录
3. 卖出时计算已实现盈亏
4. 组合汇总需要实时获取股票价格

### 验证码方案
- 使用简单图片验证码（后端生成，前端展示）
- 或使用短信验证码（需要第三方服务）
- 初期采用简单图片验证码