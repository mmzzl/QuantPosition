# Data Model: 持仓管理系统

## 实体定义

### 1. User (用户)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | ObjectId | 是 | 主键 |
| username | string | 是 | 用户名 (3-20字符) |
| password_hash | string | 是 | 密码哈希 |
| email | string | 否 | 邮箱 |
| phone | string | 否 | 手机号 |
| role_id | ObjectId | 否 | 关联角色 |
| is_active | boolean | 是 | 账号状态 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**验证规则**:
- username: 3-20字符，唯一
- password: 最少6字符
- email: 邮箱格式（可选）

### 2. Role (角色)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | ObjectId | 是 | 主键 |
| name | string | 是 | 角色名 (唯一) |
| description | string | 否 | 角色描述 |
| permissions | array | 是 | 权限列表 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**验证规则**:
- name: 唯一，非空

### 3. Permission (权限)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | ObjectId | 是 | 主键 |
| name | string | 是 | 权限名 (唯一) |
| description | string | 否 | 权限描述 |
| created_at | datetime | 是 | 创建时间 |

**预定义权限**:
- `holdings:view` - 查看持仓
- `holdings:edit` - 编辑持仓
- `users:view` - 查看用户
- `users:edit` - 管理用户
- `roles:view` - 查看角色
- `roles:edit` - 管理角色

### 4. Holding (持仓)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | ObjectId | 是 | 主键 |
| user_id | string | 是 | 用户ID |
| code | string | 是 | 股票代码 (6位数字) |
| name | string | 否 | 股票名称 |
| quantity | integer | 是 | 持仓数量 |
| average_cost | decimal | 是 | 平均成本价 |
| highest_price | decimal | 否 | 最高价 (用于追踪止损) |
| exit_rule | object | 否 | 卖出规则 |
| tier_triggered | array | 否 | 分档触发状态 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**验证规则**:
- code: 6位数字，A 股代码
- quantity: 正整数
- average_cost: 正数

**Exit Rule 结构**:
```json
{
    "exit_strategy": "tiered|trailing|fixed",
    "stop_loss": 0.05,
    "profit_target": 0.10,
    "trailing_stop_pct": 0.03,
    "tier_profits": [0.03, 0.05, 0.08, 0.10],
    "tier_sell_pcts": [0.25, 0.25, 0.25, 0.25]
}
```

### 5. Transaction (交易记录)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | ObjectId | 是 | 主键 |
| user_id | string | 是 | 用户ID |
| code | string | 是 | 股票代码 |
| type | string | 是 | 类型 (buy/sell) |
| quantity | integer | 是 | 数量 |
| price | decimal | 是 | 价格 |
| total | decimal | 是 | 总额 |
| created_at | datetime | 是 | 创建时间 |

**验证规则**:
- type: 枚举值 "buy" 或 "sell"

## 关系图

```
User (1) ---> (N) Role
User (1) ---> (N) Holding
User (1) ---> (N) Transaction
Role (1) ---> (N) Permission
```

## 索引设计

### users 集合
- `username`: 唯一索引
- `email`: 普通索引 (可选)

### holdings 集合
- 复合索引: `{ user_id: 1, code: 1 }` (唯一)

### transactions 集合
- 复合索引: `{ user_id: 1, created_at: -1 }`
- `{ user_id: 1, code: 1 }`