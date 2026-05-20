# Research: 板块热力图

## Decision 1: K线数据存储结构

**Context**: MongoDB中K线数据的字段结构

**Decision**: 假设K线数据存储在 `kline_data` 集合中，字段结构为：
```json
{
  "code": "sh.600000",
  "date": "2026-05-16",
  "open": 9.00,
  "close": 9.07,
  "high": 9.22,
  "low": 8.93,
  "volume": 171982587,
  "amount": 1559276666.00
}
```

**Rationale**: 这是标准的OHLCV数据格式，与新浪接口返回的数据结构一致

**Alternatives considered**: 
- 使用嵌套文档存储多个时间周期的K线数据（过于复杂）
- 使用时间序列数据库如InfluxDB（增加技术栈复杂度）

## Decision 2: 板块-股票映射存储

**Context**: CSV文件包含板块-股票映射，需要导入MongoDB

**Decision**: 创建 `sector_stocks` 集合，存储板块与股票的映射关系：
```json
{
  "sector_name": "货币金融服务",
  "sector_code": "J66",
  "stock_code": "sh.600000",
  "stock_name": "浦发银行"
}
```

**Rationale**: 扁平化结构便于查询和聚合，支持按板块名称或代码查询

**Alternatives considered**:
- 嵌套结构：板块文档中包含股票数组（更新困难）
- 双向引用（查询复杂）

## Decision 3: 板块涨跌幅计算方式

**Context**: 如何计算板块在指定时间范围内的涨跌幅

**Decision**: 使用MongoDB聚合管道：
1. 按股票代码分组，获取起始和结束价格
2. 计算每只股票的涨跌幅
3. 按板块分组，计算板块内股票的平均涨跌幅或市值加权涨跌幅

**Rationale**: 聚合管道在数据库层面计算，避免传输大量数据到应用层

**Alternatives considered**:
- Python计算（数据传输量大，慢）
- 预计算+缓存（数据更新不及时）

## Decision 4: K线图前端库选择

**Context**: 前端需要展示K线图

**Decision**: 使用 Apache ECharts

**Rationale**: 
- 内置K线图类型（candlestick）
- 支持缩放、拖拽、数据缩放等交互
- 与Element Plus兼容良好
- 文档完善，社区活跃

**Alternatives considered**:
- TradingView Lightweight Charts（轻量但功能有限）
- Highcharts（商业许可）
- D3.js（开发成本高）

## Decision 5: 热力图前端实现

**Context**: 如何展示板块热力图

**Decision**: 使用CSS Grid + 动态背景色实现

**Rationale**:
- 简单直接，无需额外图表库
- 响应式布局，自适应屏幕
- 颜色映射灵活可控

**Alternatives considered**:
- ECharts热力图（适合地理热力图，不适合板块展示）
- Canvas自绘（复杂度高）
