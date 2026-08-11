#!/usr/bin/env bash
# 本地拉取最新版本 → 构建 Docker 镜像 → 重新部署
#
# 用法:
#   ./scripts/deploy.sh            # 拉取 master 最新并重新部署
#   ./scripts/deploy.sh --release  # 部署最新的正式 tag（而非 master HEAD）
#
# 前置: 机器已安装 docker 与 docker compose，且当前目录为仓库根。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> 拉取最新代码"
git pull origin "$(git rev-parse --abbrev-ref HEAD)"

if [[ "${1:-}" == "--release" ]]; then
  latest="$(git describe --tags --abbrev=0)"
  echo "==> 切换到正式版本 $latest"
  git checkout -q "$latest"
fi

VER="$(cat VERSION | tr -d '[:space:]')"
echo "==> 当前版本 v$VER"

echo "==> 构建并重新部署 Docker 镜像"
docker compose build
docker compose up -d --force-recreate

echo ""
echo "✓ 部署完成: aether-nav v$VER"
echo "  访问: http://localhost:5000"
