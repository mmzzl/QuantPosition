# 持仓管理系统 + Vue3 前端设计方案

## 1. 项目概述

### 1.1 目标
- 完善 FastAPI 后端 holdings.py 的全部 API 功能
- 创建 Vue 3 + Element Plus 前端项目
- 实现用户管理、角色权限管理、持仓管理的完整功能

### 1.2 技术栈
- 后端：Python 3.11 + FastAPI + MongoDB (pymongo) + JWT
- 前端：Vue 3 + Vite + Element Plus + Axios

---

## 2. 后端 API 设计

### 2.1 持仓相关 API (holdings.py)

| 接口路径 | 方法 | 功能 | 权限 |
|----------|------|------|------|
| `/holdings/{user_id}` | GET | 获取持仓列表 (分页) | 用户只能查看自己的，管理员可查看所有 |
| `/holdings/{user_id}` | POST | 买入/添加持仓 | holdings:edit |
| `/holdings/{user_id}/{code}/sell` | POST | 卖出持仓 | holdings:edit |
| `/holdings/{user_id}/{code}` | DELETE | 删除持仓 | holdings:edit |
| `/holdings/{user_id}/{code}/exit-rule` | GET | 获取卖出规则 | holdings:view |
| `/holdings/{user_id}/{code}/exit-rule` | PUT | 设置卖出规则 | holdings:edit |
| `/holdings/{user_id}/history` | GET | 持仓历史 | holdings:view |
| `/transactions/{user_id}` | GET | 交易记录 (分页) | holdings:view |
| `/transactions/{user_id}/{transaction_id}` | DELETE | 删除交易记录 | holdings:edit |
| `/pnl/{user_id}` | GET | 已实现盈亏 | holdings:view |
| `/pnl/admin` | GET | 管理员查看已实现盈亏 | 管理员 |
| `/portfolio/{user_id}` | GET | 组合汇总 | holdings:view |
| `/holdings/admin` | GET | 管理员-所有用户持仓 | 管理员 |
| `/holdings/admin` | POST | 管理员-添加持仓 | 管理员 |
| `/holdings/admin/{code}` | DELETE | 管理员-删除持仓 | 管理员 |

### 2.2 认证相关 API

| 接口路径 | 方法 | 功能 |
|----------|------|------|
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 用户登录，返回 JWT token |
| `/auth/me` | GET | 获取当前用户信息 |

### 2.3 用户管理 API

| 接口路径 | 方法 | 功能 |
|----------|------|------|
| `/users` | GET | 用户列表（管理员） |
| `/users/{user_id}` | GET | 获取用户详情 |
| `/users/{user_id}` | PUT | 更新用户信息 |
| `/users/{user_id}/password` | PUT | 修改密码 |
| `/users/{user_id}/role` | PUT | 分配角色 |
| `/users/{user_id}` | DELETE | 删除用户（管理员） |

### 2.4 角色权限 API

| 接口路径 | 方法 | 功能 |
|----------|------|------|
| `/roles` | GET | 角色列表 |
| `/roles` | POST | 创建角色 |
| `/roles/{role_id}` | PUT | 更新角色 |
| `/roles/{role_id}` | DELETE | 删除角色 |
| `/roles/{role_id}/permissions` | PUT | 分配权限 |
| `/permissions` | GET | 权限列表 |

### 2.5 数据模型

#### Holdings 集合
```json
{
    "_id": ObjectId,
    "user_id": "user123",
    "code": "600000",
    "name": "浦发银行",
    "quantity": 1000,
    "average_cost": 10.5,
    "highest_price": 12.0,
    "exit_rule": {
        "exit_strategy": "tiered",
        "stop_loss": 0.05,
        "profit_target": 0.10,
        "trailing_stop_pct": 0.03,
        "tier_profits": [0.03, 0.05, 0.08, 0.10],
        "tier_sell_pcts": [0.25, 0.25, 0.25, 0.25]
    },
    "tier_triggered": [false, false, false, false],
    "created_at": datetime,
    "updated_at": datetime
}
```

#### Transactions 集合
```json
{
    "_id": ObjectId,
    "user_id": "user123",
    "code": "600000",
    "type": "buy" | "sell",
    "quantity": 1000,
    "price": 10.5,
    "total": 10500,
    "created_at": datetime
}
```

---

## 3. 前端页面设计

### 3.1 页面结构

```
/                         # 登录页
/register                 # 注册页
/dashboard                # 首页/仪表盘
/users                    # 用户管理
    ├── list              # 用户列表
    ├── edit/:id         # 编辑用户
    └── password/:id     # 修改密码
/roles                    # 角色管理
    ├── list             # 角色列表
    └── edit/:id         # 编辑角色（含权限分配）
/holdings                 # 持仓管理（普通用户/管理员）
    ├── list             # 持仓列表
    ├── buy              # 买入持仓
    ├── sell/:code       # 卖出
    ├── history          # 历史记录
    ├── transactions     # 交易记录
    └── summary          # 组合汇总
```

### 3.2 页面详情

#### 登录页 `/`
- Logo + 系统名称
- 用户名/密码输入
- 验证码（可选）
- "记住我" 复选框
- 登录按钮
- "还没有账号？去注册" 链接

#### 注册页 `/register`
- 用户名、密码、确认密码
- 邮箱（可选）
- 注册按钮
- "已有账号？去登录" 链接

#### 首页 `/dashboard`
- 欢迎语 + 当前用户信息
- 快捷操作按钮
- 持仓概览卡片（数量、市值、盈亏）

#### 用户管理页 `/users`
- 表格：用户名、邮箱、角色、状态、创建时间、操作
- 搜索框（按用户名搜索）
- 添加用户按钮
- 操作：编辑、修改密码、分配角色、删除

#### 角色管理页 `/roles`
- 表格：角色名、描述、权限数量、操作
- 添加角色按钮
- 操作：编辑、删除
- 编辑页面：角色名、描述、权限树形选择

#### 持仓列表页 `/holdings`
- 表格：股票代码、名称、数量、成本、市值、盈亏、盈亏比例
- 筛选：按代码搜索
- 添加持仓按钮
- 操作：卖出、设置卖出规则、删除

#### 买入页 `/holdings/buy`
- 股票代码输入
- 股票名称（自动补全）
- 数量输入
- 成本价输入
- 提交按钮

#### 卖出页 `/holdings/sell/:code`
- 当前持仓信息展示
- 数量输入
- 卖出价格输入
- 确认卖出按钮

#### 历史记录页 `/holdings/history`
- 表格：时间、股票代码、类型、数量、价格、总额
- 时间范围筛选

#### 组合汇总页 `/holdings/summary`
- 总持仓数
- 总成本
- 总市值
- 未实现盈亏
- 盈亏比例
- 已实现盈亏

### 3.3 UI 设计规范

- 主题色：蓝色系 (#409EFF Element Plus 默认蓝)
- 侧边栏：深蓝色 (#304156)
- 表格：斑马纹、hover 高亮
- 按钮：主要按钮蓝色，次要按钮灰色
- 表单：清晰的标签和验证提示
- 响应式：支持 1024px 以上屏幕

---

## 4. 权限控制

### 4.1 角色
- **管理员 (admin)**：可查看所有用户持仓、管理用户、角色、权限
- **普通用户**：只能查看和操作自己的持仓

### 4.2 权限
- `holdings:view` - 查看持仓
- `holdings:edit` - 编辑持仓
- `users:view` - 查看用户
- `users:edit` - 管理用户
- `roles:view` - 查看角色
- `roles:edit` - 管理角色

---

## 5. 部署

### 后端
```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

### 前端
```bash
cd apps/web
npm install
npm run dev
```

---

## 6. 验收标准

1. 用户可以注册、登录、登出
2. 管理员可以管理用户（CRUD）
3. 管理员可以管理角色和权限
4. 用户可以买入、卖出持仓
5. 用户可以查看持仓列表、历史、汇总
6. 管理员可以查看所有用户持仓
7. 页面美观、交互流畅
8. API 有适当的错误处理和验证