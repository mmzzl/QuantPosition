# Quick Start: 持仓管理系统

## 前置要求

- Python 3.11+
- Node.js 18+
- MongoDB 4.4+

## 后端启动

```bash
# 1. 进入后端目录
cd apps/api

# 2. 创建虚拟环境 (如需要)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install fastapi uvicorn pymongo python-jose passlib bcrypt pydantic

# 4. 启动服务
uvicorn main:app --reload --port 8000
```

## 前端启动

```bash
# 1. 进入前端目录
cd apps/web

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

## 初始数据

### 创建管理员角色

```python
# 在 MongoDB shell 中
use your_database

# 创建角色
db.roles.insertOne({
    "name": "admin",
    "description": "管理员",
    "permissions": ["holdings:view", "holdings:edit", "users:view", "users:edit", "roles:view", "roles:edit"],
    "created_at": new Date(),
    "updated_at": new Date()
})

# 创建普通用户角色
db.roles.insertOne({
    "name": "user",
    "description": "普通用户",
    "permissions": ["holdings:view", "holdings:edit"],
    "created_at": new Date(),
    "updated_at": new Date()
})
```

### 创建管理员用户

```python
# 通过注册 API 或数据库直接插入
# 注意：密码需要 bcrypt 哈希
```

## API 端点

### 认证
- `POST /auth/register` - 注册
- `POST /auth/login` - 登录
- `GET /auth/me` - 当前用户

### 用户管理
- `GET /users` - 用户列表
- `GET /users/{id}` - 用户详情
- `PUT /users/{id}` - 更新用户
- `PUT /users/{id}/password` - 修改密码
- `PUT /users/{id}/role` - 分配角色

### 角色权限
- `GET /roles` - 角色列表
- `POST /roles` - 创建角色
- `PUT /roles/{id}` - 更新角色
- `DELETE /roles/{id}` - 删除角色

### 持仓管理
- `GET /holdings/{user_id}` - 持仓列表
- `POST /holdings/{user_id}` - 买入
- `POST /holdings/{user_id}/{code}/sell` - 卖出
- `DELETE /holdings/{user_id}/{code}` - 删除持仓

### 其他
- `GET /holdings/{user_id}/history` - 持仓历史
- `GET /transactions/{user_id}` - 交易记录
- `GET /pnl/{user_id}` - 已实现盈亏
- `GET /portfolio/{user_id}` - 组合汇总

## 前端页面

- `/` - 登录页
- `/register` - 注册页
- `/dashboard` - 首页
- `/users` - 用户管理
- `/roles` - 角色管理
- `/holdings` - 持仓列表
- `/holdings/buy` - 买入
- `/holdings/sell/:code` - 卖出
- `/holdings/history` - 历史记录
- `/holdings/summary` - 组合汇总