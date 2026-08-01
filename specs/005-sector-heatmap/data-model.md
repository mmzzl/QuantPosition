# Data Model: 板块热力图

## 实体定义

### 1. K线数据 (stock_kline)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码（纯数字，已去除交易所前缀），如 "600000" |
| date | string | 是 | 交易日期，格式 "YYYY-MM-DD HH:mm" |
| open | float | 是 | 开盘价 |
| close | float | 是 | 收盘价 |
| high | float | 是 | 最高价 |
| low | float | 是 | 最低价 |
| volume | int | 是 | 成交量 |
| amount | float | 是 | 成交额 |
| frequency | int | 是 | K线频率，9=日K |

**索引**: 
- `{ code: 1, date: -1 }` 复合索引（用于按股票和时间范围查询）
- `{ code: 1, frequency: 1, date: -1 }` 复合索引（用于按股票+频率查询）

### 2. 板块-股票映射 (sector_stocks)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sector_name | string | 是 | 板块名称，如 "货币金融服务" |
| sector_code | string | 否 | 板块代码，如 "J66" |
| stock_code | string | 是 | 股票代码，如 "sh.600000" |
| stock_name | string | 是 | 股票名称，如 "浦发银行" |

**索引**:
- `{ sector_name: 1 }` （用于按板块查询）
- `{ stock_code: 1 }` （用于按股票查询所属板块）
- `{ sector_name: 1, stock_code: 1 }` 复合唯一索引

### 3. 板块聚合结果 (API返回，不存储)

| 字段 | 类型 | 说明 |
|------|------|------|
| sector_name | string | 板块名称 |
| sector_code | string | 板块代码 |
| change_pct | float | 板块等权涨跌幅（%） |
| stock_count | int | 成分股数量 |
| volume | float | 平均成交量 |

## 验证规则

- K线数据: `open`, `close`, `high`, `low` 必须 > 0
- K线数据: `high >= open` 且 `high >= close` 且 `high >= low`
- K线数据: `low <= open` 且 `low <= close`
- 板块-股票映射: `stock_code` 带交易所前缀（如 "sh.600000"），查询K线时需通过 `split(".")[0]` 转换为纯数字代码匹配 `stock_kline.code`

## 数据流

```
CSV文件 → import_sector_data.py → sector_stocks 集合 (stock_code 含交易所前缀)
                                          │
                                          │ split(".")[0] 归一化为纯代码
                                          ▼
K线数据 (已有, stock_kline.code 为纯数字) → MongoDB聚合 → 板块涨跌幅
                                          |
                                          ▼
                                    API返回 → 前端热力图
```
