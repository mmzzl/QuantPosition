# 持仓管理系统

基于 FastAPI + Vue 3 的股票持仓管理与智能选股系统。

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | Python 3.12, FastAPI |
| 前端 | Vue 3, Element Plus, ECharts |
| 数据库 | MongoDB |
| 消息队列 | Redis + Celery |
| 认证 | JWT (python-jose) |

## 快速开始

### 方式一：Docker（推荐）

```bash
# 启动所有服务
docker compose up -d

# 导入板块映射数据
docker compose exec api python scripts/import_sector_data.py
docker compose exec api python scripts/import_bk_data.py
docker compose exec api python scripts/add_sector_perms.py

# 重启 celery 注册任务
docker compose restart celery

# 查看日志
docker compose logs -f
```

访问：
- 前端：http://localhost:5173
- API：http://localhost:8000
- 默认管理员：admin / admin123

### 方式二：本地开发

**前置条件**：MongoDB 运行在 localhost:27017，Redis 运行在 localhost:6379

#### 后端

```bash
cd apps/api

# 安装依赖
pip install -r requirements.txt

# 导入板块数据
python scripts/import_sector_data.py
python scripts/import_bk_data.py
python scripts/add_sector_perms.py

# 启动 API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 新开终端，启动 Celery Worker（选股任务）
celery -A celery_config.celery_app worker --pool=solo --loglevel=info
```

#### 前端

```bash
cd apps/web
npm install
npm run dev
```

访问 http://localhost:5173

## 配置文件

`apps/api/config/config.yaml`：

```yaml
mongodb:
  host: "127.0.0.1"
  port: 27017
  database: "eastmoney_news"
redis:
  host: "localhost"
  port: 6379
jwt:
  secret: "your-secret-key-change-in-production"
  access_token_expire_minutes: 30
```

Docker 环境下使用 `config.docker.yaml`（MongoDB/Redis 指向容器名），通过环境变量 `CONFIG_FILE=config.docker.yaml` 切换。

## 功能模块

### 持仓管理
- 持仓列表、买入、卖出、历史记录
- 组合汇总、盈亏分析
- 批量获取实时行情（新浪接口）

### 板块热力图
- 按 24h / 7d / 30d 查看板块涨跌幅
- 颜色映射（红涨绿跌），点击进入板块股票列表
- 个股 K 线图

### 选股
- **双均线选股**：短期均线上穿长期均线（金叉），异步 Celery 任务，支持进度轮询
- **新闻选股**：解析新闻中的东方财富板块代码（BKxxx），关联板块股票，计算目标价/止损价/预期收益

### 交易规则
- 可视化条件构建器，点击变量和运算符拼装条件
- 规则类型：买入 / 卖出 / 风控
- 条件测试：实时验证条件语法和执行结果
- 引擎读取持仓 + 选股候选池，触发后推送钉钉机器人
- 同股票同规则同日不重复告警

### 规则探索
- **模板搜索**：基于指标组合网格搜索生成候选规则
- **LLM 生成**：调用大模型批量生成交易规则
- **遗传算法**：多轮进化优化规则参数
- **回测验证**：自动回测评分，筛选高分规则
- 候选规则管理：查看、验证、应用、黑名单

### 策略回测
- 基于 Backtrader 的规则驱动回测引擎
- 支持自定义规则、抽样股票数量、手续费率
- 实时进度展示（MongoDB 存储，按任务隔离）
- 输出：胜率、夏普比率、盈亏比、最大回撤、出场方式统计

### 系统管理
- 用户管理、角色管理、权限管理
- 系统设置：网站名称、Logo、备案信息、Session 过期时间、站点开关、时区格式、钉钉配置
- LLM 配置：API 地址、API Key、模型名称、批量生成条数（规则探索用）

### 新闻浏览
- 按时间筛选新闻，展示标题、摘要、关联板块

## 数据导入

```bash
# 证监会行业分类 → sector_stocks（5191 条，83 个板块）
python scripts/import_sector_data.py

# 东方财富 BK 板块 → bk_stocks（60062 条，469 个板块）
python scripts/import_bk_data.py

# 初始化权限
python scripts/add_sector_perms.py
```

CSV 数据文件位于 `apps/api/data/`：
- `stock_industry.csv` — 证监会行业分类映射
- `all_stock_industry.csv` — 东方财富 BK 板块映射
- `code_to_industry.csv` — 股票代码→行业

## API 概览

| 路径 | 说明 |
|------|------|
| `POST /auth/login` | 登录获取 Token |
| `POST /auth/register` | 注册新用户 |
| `GET /holdings/{user_id}` | 持仓列表 |
| `POST /holdings/{user_id}` | 买入同步（记录买入 + 摊薄成本） |
| `POST /holdings/{user_id}/{code}/sell` | 卖出同步（扣减持仓 + 计算盈亏） |
| `GET /holdings/transactions/{user_id}` | 交易记录 |
| `GET /holdings/pnl/{user_id}` | 已实现盈亏汇总 |
| `GET /settings/public` | 公开设置（无需登录） |
| `GET /news` | 新闻列表 |
| `GET /sectors/heatmap` | 板块热力图 |
| `GET /sectors/{name}/stocks` | 板块股票列表 |
| `GET /sectors/kline/{code}` | K 线数据 |
| `POST /selections/dual-ma` | 触发双均线选股 |
| `POST /news-selection/run` | 触发新闻选股 |
| `GET /rules` | 交易规则 CRUD |
| `POST /rules/validate` | 规则条件校验 |
| `POST /rules/explore` | 启动规则探索 |
| `GET /rules/explore/status` | 探索进度 |
| `GET /rules/candidates` | 候选规则列表 |
| `POST /rules/validate-candidates` | 验证候选规则 |
| `POST /backtest/run` | 运行策略回测 |
| `GET /backtest/task/{id}` | 回测任务进度 |
| `GET /backtest/latest` | 最新回测结果 |
| `GET /settings` | 系统设置（需管理员） |
| `PUT /settings` | 更新系统设置 |

## 实盘交易同步

### 获取 Token

```bash
# 默认管理员：admin / admin123
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

返回示例：
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "user_id": "67f8a1b2c3d4e5f6a7b8c9d0",
  "role": "super_admin"
}
```

> Token 有效期默认 30 分钟，过期后需重新登录。

### 买入同步

在东方财富买入股票后，调用此接口记录到系统：

```bash
curl -X POST http://localhost:8000/holdings/{user_id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"code": "000001", "name": "平安银行", "quantity": 1000, "average_cost": 11.50}'
```

- 同一股票再次买入自动**摊薄成本**
- 自动计算买入费用（佣金 + 过户费）
- 记录买入交易流水

### 卖出同步

```bash
curl -X POST http://localhost:8000/holdings/{user_id}/{code}/sell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"quantity": 500, "price": 12.00}'
```

- 支持**分批卖出**，系统自动扣减持仓数量
- 计算已实现盈亏 = 卖出净额 - 卖出部分成本（含印花税+佣金+过户费）
- 清仓后自动删除持仓记录

### 查询

```bash
# 持仓列表
curl -H "Authorization: Bearer {token}" http://localhost:8000/holdings/{user_id}

# 交易记录
curl -H "Authorization: Bearer {token}" http://localhost:8000/holdings/transactions/{user_id}

# 已实现盈亏
curl -H "Authorization: Bearer {token}" http://localhost:8000/holdings/pnl/{user_id}
```
