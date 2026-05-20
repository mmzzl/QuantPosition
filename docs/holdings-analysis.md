# 持仓管理 (holdings.py) 分析文档

## 1. 数据格式

### HoldingInput (买入/持仓)
```python
{
    "code": "600000",       # 股票代码 (必填)
    "name": "浦发银行",     # 股票名称 (可选)
    "quantity": 1000,      # 持仓数量 (必填)
    "average_cost": 10.5   # 平均成本价 (必填)
}
```

### SellInput (卖出)
```python
{
    "quantity": 500,       # 卖出数量
    "price": 12.0           # 卖出价格
}
```

### ExitRuleInput (卖出规则)
```python
{
    "exit_strategy": "tiered",      # 策略: tiered/trailing/fixed
    "stop_loss": 0.05,              # 止损比例 5%
    "profit_target": 0.10,          # 止盈目标 10%
    "trailing_stop_pct": 0.03,     # 追踪止损 3%
    "tier_profits": [0.03, 0.05, 0.08, 0.10],  # 分档盈利
    "tier_sell_pcts": [0.25, 0.25, 0.25, 0.25] # 分档卖出比例
}
```

---

## 2. API 接口

| 接口路径 | 方法 | 功能 |
|----------|------|------|
| `/holdings/{user_id}` | GET | 获取持仓列表 (分页) |
| `/holdings/{user_id}` | POST | 买入/添加持仓 |
| `/holdings/{user_id}/{code}/sell` | POST | 卖出持仓 |
| `/holdings/{user_id}/{code}` | DELETE | 删除持仓 |
| `/holdings/{user_id}/{code}/exit-rule` | GET | 获取卖出规则 |
| `/holdings/{user_id}/{code}/exit-rule` | PUT | 设置卖出规则 |
| `/holdings/{user_id}/history` | GET | 持仓历史 |
| `/transactions/{user_id}` | GET | 交易记录 (分页) |
| `/transactions/{user_id}/{transaction_id}` | DELETE | 删除交易记录 |
| `/pnl/{user_id}` | GET | 已实现盈亏 |
| `/pnl/admin` | GET | 管理员查看已实现盈亏 |
| `/portfolio/{user_id}` | GET | 组合汇总 (成本、市值、未实现盈亏) |
| `/holdings/admin` | GET | 管理员-所有用户持仓 |
| `/holdings/admin` | POST | 管理员-添加持仓 |
| `/holdings/admin/{code}` | DELETE | 管理员-删除持仓 |

---

## 3. 计算逻辑

### 3.1 盈亏计算

```python
# 盈亏比例 (百分比)
profit_pct = ((current_price - cost_price) / cost_price) * 100

# 止损价
stop_loss_price = cost_price * (1 - stop_loss_pct)

# 追踪止损价 (基于最高价)
trailing_stop_price = highest_price * (1 - trailing_stop_pct)

# 更新最高价
if current_price > highest_price:
    highest_price = current_price
```

### 3.2 卖出策略 (Exit Rule)

#### 策略类型: tiered (分档止盈)
```
亏损 ≥5% → 止损卖出全部
盈利 ≥3% → 卖出 25%
盈利 ≥5% → 卖出 25%
盈利 ≥8% → 卖出 25%
盈利 ≥10% → 卖出 25%
全部触发后启用 3% 回撤追踪止损
```

#### 策略类型: trailing (追踪止损)
```
盈利 ≥10% → 启用 3% 回撤追踪止损
```

#### 策略类型: fixed (固定止盈)
```
盈利 ≥10% → 卖出全部
```

---

## 4. MongoDB 数据结构

### holdings 集合 (持仓)
```json
{
    "_id": ObjectId,
    "user_id": "user123",
    "code": "600000",
    "name": "浦发银行",
    "quantity": 1000,           // 当前持仓数量
    "average_cost": 10.5,       // 平均成本价
    "highest_price": 12.0,       // 最高价 (用于追踪止损)
    "exit_rule": {              // 卖出规则
        "exit_strategy": "tiered",
        "stop_loss": 0.05,
        "profit_target": 0.10,
        "trailing_stop_pct": 0.03,
        "tier_profits": [0.03, 0.05, 0.08, 0.10],
        "tier_sell_pcts": [0.25, 0.25, 0.25, 0.25]
    },
    "tier_triggered": [false, false, false, false],  // 分档触发状态
    "created_at": datetime,
    "updated_at": datetime
}
```

### transactions 集合 (交易记录)
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

## 5. 组合汇总计算 (Portfolio)

返回字段:
```json
{
    "holdings_count": 5,         // 持仓数量
    "total_cost": 50000.0,       // 总成本
    "market_value": 55000.0,     // 市值
    "unrealized_pnl": 5000.0,    // 未实现盈亏
    "profit": 5000.0,            // 盈亏金额
    "profit_rate": 10.0,         // 盈亏比例 (%)
    "realized_pnl": 2000.0,      // 已实现盈亏
    "total_sell_value": 30000.0, // 卖出总金额
    "holdings": [...]            // 持仓列表
}
```

计算公式:
- `market_value` = Σ(quantity × current_price)
- `unrealized_pnl` = Σ(quantity × (current_price - average_cost))
- `profit_rate` = (unrealized_pnl / total_cost) × 100

---

## 6. 依赖模块

- `app.data_source.DataSourceManager` - 数据源管理 (未找到实现文件)
- MongoDB adapter - 需要实现以下方法:
  - `get_holdings(user_id, page, page_size)`
  - `upsert_holding(user_id, code, quantity, average_cost)`
  - `sell_holding(user_id, code, quantity, price)`
  - `remove_holding(user_id, code)`
  - `get_transactions(user_id, code, page, page_size)`
  - `calculate_realized_pnl(user_id, code)`
  - `get_portfolio_summary(user_id, price_fetcher)`

---

## 7. 权限控制

- `holdings:view` - 查看持仓
- `holdings:edit` - 编辑持仓

用户只能访问自己的持仓，管理员可以访问所有用户持仓。