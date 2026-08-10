# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS fe
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：运行后端 ----
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY backend/ /app/backend/
COPY --from=fe /app/frontend/dist /app/frontend/dist
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 持久化数据库与上传图标
VOLUME ["/app/backend/instance", "/app/backend/uploads"]
EXPOSE 5000

# 首次启动建表+注入示例数据，再用 gunicorn 运行
CMD ["sh", "-c", "cd /app && python -m backend.seed && gunicorn -b 0.0.0.0:5000 backend.app:app"]
