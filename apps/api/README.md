# 持仓管理系统 API

## 启动项目

### 1. 启动后端 API

```bash
cd apps/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动 Celery Worker（选股任务）

Celery 用于异步执行双均线选股等耗时任务，依赖 Redis 作为消息队列。

```bash
# 启动 worker（Windows）
cd apps/api
celery -A celery_config.celery_app worker --pool=solo --loglevel=info

# 启动 worker（Linux / macOS）
cd apps/api
celery -A celery_config.celery_app worker --loglevel=info

# 启动 beat（如果后续需要定时任务）
celery -A celery_config.celery_app beat --loglevel=info
```

> 注意：Windows 下必须加 `--pool=solo`，否则 Celery 无法正常工作。

### 3. 启动前端

```bash
cd apps/web
npm install
npm run dev
```

## 初始化超级管理员

系统默认没有管理员账号，需要手动在 MongoDB 中创建：

```javascript
use your_database  // 切换到你的数据库

// 1. 创建管理员角色（如果还没有）
db.roles.insertOne({
  "name": "admin",
  "description": "管理员",
  "permissions": ["holdings:view", "holdings:edit", "users:view", "users:edit", "roles:view", "roles:edit"],
  "created_at": new Date(),
  "updated_at": new Date()
})

// 2. 创建管理员用户 (用户名: admin, 密码: admin123)
db.users.insertOne({
  "username": "admin",
  "password_hash": "$2b$12$b9dZuJtpZLVCqHOQ3YbZVuQTbF1A9T5JQkyZS4lzNxPrQwvubDtRO",
  "role": "admin",
  "is_active": true,
  "created_at": new Date(),
  "updated_at": new Date()
})
```

## API 接口

### 认证
- `POST /auth/register` - 注册
- `POST /auth/login` - 登录
- `GET /auth/me` - 当前用户
- `GET /menu` - 获取菜单（登录后）

### 持仓管理
- `GET /holdings/{user_id}` - 持仓列表
- `POST /holdings/{user_id}` - 买入
- `POST /holdings/{user_id}/{code}/sell` - 卖出
- `DELETE /holdings/{user_id}/{code}` - 删除持仓
- `GET /holdings/{user_id}/history` - 持仓历史
- `GET /holdings/portfolio/{user_id}` - 组合汇总
- `GET /holdings/pnl/{user_id}` - 已实现盈亏
- `GET /holdings/transactions/{user_id}` - 交易记录

### 管理员接口
- `GET /holdings/admin` - 所有用户持仓
- `GET /holdings/pnl/admin` - 所有用户盈亏
- `GET /users` - 用户列表
- `GET /roles` - 角色列表

## 依赖检查

- **MongoDB**: 运行在 `localhost:27017`，数据库 `eastmoney_news`
- **Redis**: 运行在 `localhost:6379`（Celery 依赖）

## 配置文件

编辑 `config/config.yaml`：

```yaml
mongodb:
  host: "127.0.0.1"
  port: 27017
  database: "eastmoney_news"
redis:
  host: "localhost"
  port: 6379
```

## 数据导入

```bash
cd apps/api
python scripts/import_sector_data.py
python scripts/add_sector_perms.py
```