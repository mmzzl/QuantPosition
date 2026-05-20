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
- 引擎读取持仓 + 选股候选池，触发后推送钉钉机器人
- 同股票同规则同日不重复告警

### 系统管理
- 用户管理、角色管理、权限管理
- 系统设置：网站名称、Logo、备案信息、Session 过期时间、站点开关、时区格式、钉钉配置

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
| `POST /auth/login` | 登录 |
| `GET /settings/public` | 公开设置（无需登录） |
| `GET /news` | 新闻列表 |
| `GET /sectors/heatmap` | 板块热力图 |
| `GET /sectors/{name}/stocks` | 板块股票列表 |
| `GET /sectors/kline/{code}` | K 线数据 |
| `POST /selections/dual-ma` | 触发双均线选股 |
| `POST /news-selection/run` | 触发新闻选股 |
| `GET /rules` | 交易规则 CRUD |
| `GET /settings` | 系统设置（需管理员） |
| `PUT /settings` | 更新系统设置 |
