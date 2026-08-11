#!/usr/bin/env bash
# 依据变更内容自动管理版本号（语义化版本 MAJOR.MINOR.PATCH）
#
# 用法:
#   ./scripts/bump_version.sh            # 自动推断（扫描自上次 tag 起的提交）
#   ./scripts/bump_version.sh patch      # 强制 patch（修复）
#   ./scripts/bump_version.sh minor      # 强制 minor（新增功能）
#   ./scripts/bump_version.sh major      # 强制 major（破坏性变更）
#   ./scripts/bump_version.sh --push     # 推断并同时推送 tag 到 remote
#   ./scripts/bump_version.sh minor --push
#
# 自动推断规则（取自上次 tag 起到 HEAD 的提交，取最高级别）:
#   major : 含 BREAKING / 破坏性 / 重大变更 / "!: " 的提交
#   minor : 含 feat / 新增 / 新功能 / 支持 / 增加 的提交
#   patch : 含 fix / 修复 / bug 的提交，或兜底（默认）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"
test -f "$VERSION_FILE" || { echo "✗ VERSION 文件不存在: $VERSION_FILE"; exit 1; }

cur="$(cat "$VERSION_FILE" | tr -d '[:space:]')"
if ! [[ "$cur" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "✗ VERSION 格式非法: $cur (应为 X.Y.Z)"; exit 1
fi
IFS='.' read -r MAJOR MINOR PATCH <<< "$cur"

FORCE=""
PUSH=0
for a in "$@"; do
  case "$a" in
    major|minor|patch) FORCE="$a" ;;
    --push) PUSH=1 ;;
    *) echo "✗ 未知参数: $a (用 major|minor|patch 或 --push)"; exit 1 ;;
  esac
done

bump=""
if [[ -z "$FORCE" ]]; then
  last_tag="$(git -C "$ROOT" describe --tags --abbrev=0 2>/dev/null || echo "")"
  range="${last_tag:+$last_tag..HEAD}"
  log="$(git -C "$ROOT" log --no-merges $range --pretty=%s)"
  if echo "$log" | grep -qiE 'BREAKING|破坏性|重大变更|!: '; then
    bump=major
  elif echo "$log" | grep -qiE 'feat|新增|新功能|支持|增加'; then
    bump=minor
  elif echo "$log" | grep -qiE 'fix|修复|bug'; then
    bump=patch
  else
    bump=patch
  fi
  echo "自动推断变更级别: $bump (基于自 ${last_tag:-初始提交} 起的提交)"
else
  bump="$FORCE"
fi

case "$bump" in
  major) MAJOR=$((MAJOR+1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR+1)); PATCH=0 ;;
  patch) PATCH=$((PATCH+1)) ;;
esac

new="$MAJOR.$MINOR.$PATCH"
echo "$new" > "$VERSION_FILE"
echo "版本: $cur -> $new"

git -C "$ROOT" add VERSION
git -C "$ROOT" commit -q -m "chore: 发布 v$new"
git -C "$ROOT" tag -a "v$new" -m "v$new"
echo "✓ 已更新 VERSION 并打 tag v$new"

if [[ "$PUSH" -eq 1 ]]; then
  git -C "$ROOT" push origin "$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
  git -C "$ROOT" push origin "v$new"
  echo "✓ 已推送 tag v$new 到 remote"
fi
