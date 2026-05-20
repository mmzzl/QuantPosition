# Quickstart: 板块热力图

## 前置条件

- MongoDB 运行中，包含K线数据
- 板块-股票映射CSV文件位于 `apps/api/data/stock_industry.csv`
- 后端服务 (FastAPI) 运行在 `http://localhost:8000`
- 前端服务 (Vue 3) 运行在 `http://localhost:5173`

## 步骤 1: 导入板块数据

```bash
cd apps/api
python scripts/import_sector_data.py
```

这将读取CSV文件并导入MongoDB的 `sector_stocks` 集合。

## 步骤 2: 启动后端

```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

## 步骤 3: 启动前端

```bash
cd apps/web
npm run dev
```

## 步骤 4: 访问热力图

打开浏览器访问 `http://localhost:5173/sectors/heatmap`

## 测试API

```bash
# 获取热力图数据
curl "http://localhost:8000/sectors/heatmap?period=7d"

# 获取板块股票列表
curl "http://localhost:8000/sectors/货币金融服务/stocks"

# 获取K线数据
curl "http://localhost:8000/sectors/kline/sh.600000?start_date=2026-04-16&end_date=2026-05-16"
```
