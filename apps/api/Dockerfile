FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 默认启动 API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
