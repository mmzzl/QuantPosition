# API Contracts: 板块热力图

## GET /sectors/heatmap

获取板块热力图数据

### Request

```
GET /sectors/heatmap?period=24h&start_date=&end_date=
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | 时间范围: "24h", "7d", "30d" (默认"24h") |
| start_date | string | 否 | 自定义起始日期 (YYYY-MM-DD)，与period互斥 |
| end_date | string | 否 | 自定义结束日期 (YYYY-MM-DD) |

### Response 200

```json
{
  "sectors": [
    {
      "sector_name": "货币金融服务",
      "sector_code": "J66",
      "change_pct": 2.35,
      "stock_count": 45,
      "avg_volume": 12345678.5,
      "start_price": 8.50,
      "end_price": 8.70
    }
  ],
  "period": "24h",
  "total_sectors": 85
}
```

---

## GET /sectors/{sector_name}/stocks

获取指定板块的股票列表

### Request

```
GET /sectors/{sector_name}/stocks?sort_by=change_pct&sort_order=desc&page=1&page_size=50
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sector_name | string | 是 | 板块名称（URL路径参数） |
| sort_by | string | 否 | 排序字段: "change_pct", "volume", "name" (默认"change_pct") |
| sort_order | string | 否 | 排序方向: "asc", "desc" (默认"desc") |
| page | int | 否 | 页码 (默认1) |
| page_size | int | 否 | 每页数量 (默认50，最大100) |

### Response 200

```json
{
  "sector_name": "货币金融服务",
  "sector_code": "J66",
  "stocks": [
    {
      "code": "sh.600000",
      "name": "浦发银行",
      "change_pct": 3.45,
      "current_price": 9.07,
      "open_price": 9.00,
      "high": 9.22,
      "low": 8.93,
      "volume": 171982587,
      "amount": 1559276666.00
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 50
}
```

---

## GET /kline/{code}

获取股票K线数据

### Request

```
GET /kline/{code}?period=daily&start_date=2026-04-16&end_date=2026-05-16
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码（URL路径参数） |
| period | string | 否 | K线周期: "daily", "weekly", "monthly" (默认"daily") |
| start_date | string | 是 | 起始日期 (YYYY-MM-DD) |
| end_date | string | 是 | 结束日期 (YYYY-MM-DD) |

### Response 200

```json
{
  "code": "sh.600000",
  "name": "浦发银行",
  "period": "daily",
  "data": [
    {
      "date": "2026-05-16",
      "open": 9.00,
      "close": 9.07,
      "high": 9.22,
      "low": 8.93,
      "volume": 171982587,
      "amount": 1559276666.00
    }
  ],
  "total": 20
}
```
