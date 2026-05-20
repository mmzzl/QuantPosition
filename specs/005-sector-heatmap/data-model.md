# Data Model: 板块热力图

## 实体定义

### 1. K线数据 (kline_data)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码，如 "sh.600000" |
| date | date | 是 | 交易日期 |
| open | float | 是 | 开盘价 |
| close | float | 是 | 收盘价 |
| high | float | 是 | 最高价 |
| low | float | 是 | 最低价 |
| volume | int | 是 | 成交量 |
| amount | float | 是 | 成交额 |

**索引**: 
- `{ code: 1, date: 1 }` 复合索引（用于按股票和时间范围查询）
- `{ date: 1 }` 单字段索引（用于按日期范围查询）

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
| change_pct | float | 板块涨跌幅（%） |
| stock_count | int | 成分股数量 |
| avg_volume | float | 平均成交量 |
| top_stocks | array | 领涨/领跌股票列表 |

## 验证规则

- K线数据: `open`, `close`, `high`, `low` 必须 > 0
- K线数据: `high >= open` 且 `high >= close` 且 `high >= low`
- K线数据: `low <= open` 且 `low <= close`
- 板块-股票映射: `stock_code` 必须与K线数据中的格式一致

## 数据流

```
CSV文件 → import_sector_data.py → sector_stocks集合
                                    ↓
K线数据 (已有) + sector_stocks → MongoDB聚合 → 板块涨跌幅
                                    ↓
                              API返回 → 前端热力图
```
