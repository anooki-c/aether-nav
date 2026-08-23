# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS fe
# 接收构建提交 SHA：把它注入 ENV 以污染前端 build 层的缓存键，
# 确保每次提交都强制重新构建前端（绕开 gha 对已变源码的层误复用，
# 否则会出现「后端 version.json 是新 commit、但 dist 仍是旧产物」的不一致）。
ARG BUILD_COMMIT=unknown
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_BUILD_COMMIT=$BUILD_COMMIT
RUN npm run build

# ---- 阶段 2：运行后端 ----
FROM python:3.11-slim
ARG BUILD_COMMIT=unknown
ARG BUILD_TIME=unknown
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 appuser
COPY backend/ /app/backend/
COPY VERSION /app/VERSION
COPY --from=fe /app/frontend/dist /app/frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/aether-nav-entrypoint
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
# 注入构建版本信息（CI 通过 build-arg 传入 github.sha 与构建时间）；
# 开发环境未传入时回落为 unknown，后端 /api/version 据此标识为开发版。
# tag 取自仓库根目录 VERSION 文件（与 bump_version.sh 共用），使镜像内版本号与发布版本一致。
RUN VT=$(cat /app/VERSION 2>/dev/null | tr -d '[:space:]'); \
    VT=$${VT:-latest}; \
    printf '{"commit":"%s","tag":"%s","build_time":"%s","source":"docker"}' "$BUILD_COMMIT" "$VT" "$BUILD_TIME" > /app/version.json

RUN chown -R appuser:appuser /app
RUN chmod 755 /usr/local/bin/aether-nav-entrypoint

# 持久化数据库与上传图标
VOLUME ["/app/backend/instance", "/app/backend/uploads"]
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3)"

# 首次启动建表+注入示例数据，再用 gunicorn 运行；entrypoint 会先处理 bind mount 权限并降权
ENTRYPOINT ["/usr/local/bin/aether-nav-entrypoint"]
CMD ["sh", "-c", "cd /app && python -m backend.seed && gunicorn -b 0.0.0.0:5000 backend.app:app"]
