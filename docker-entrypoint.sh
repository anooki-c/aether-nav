#!/bin/sh
set -eu

# Bind mount 会覆盖镜像内目录的所有权；启动时先修正持久化目录，
# 然后再降权运行应用，避免 SQLite 报 readonly database。
mkdir -p /app/backend/instance /app/backend/uploads
chown -R appuser:appuser /app/backend/instance /app/backend/uploads

exec su -s /bin/sh appuser -c "$*"
