#!/usr/bin/env bash
# trigger-sync.sh — 立刻触发上游同步流水线（拉取 + 重建索引 + 部署）
#
# 背景：GitHub 对 schedule（cron）有节流，实测每 15 分钟的 cron 经常被延迟到
# 数小时一次，导致新发布的正式版迟迟不上架。发版后主动调用本脚本可做到秒级同步。
#
# 用法：
#   ./sileo/scripts/trigger-sync.sh            # 用本机 gh 登录身份触发
#   SOURCE_TOKEN=xxx ./sileo/scripts/trigger-sync.sh   # 或用指定 token（需 actions:write）
#
# 说明：需要 gh CLI 已登录（gh auth login），或提供 SOURCE_TOKEN。
#      触发后流水线约 1~2 分钟完成，可在 Actions 页或仓库提交记录确认。

set -euo pipefail

REPO="tanyou88888/tanyou88888.github.io"
WF="pull-release.yml"

if [ -n "${SOURCE_TOKEN:-}" ]; then
  curl -sS -o /dev/null -w "trigger-sync: %{http_code}\n" \
    -X POST \
    -H "Authorization: Bearer $SOURCE_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/actions/workflows/$WF/dispatches" \
    -d '{"ref":"main"}'
else
  command -v gh >/dev/null || { echo "需要 gh CLI 或设置 SOURCE_TOKEN"; exit 1; }
  gh api "repos/$REPO/actions/workflows/$WF/dispatches" -X POST -f ref=main >/dev/null
  echo "trigger-sync: 已触发（gh）"
fi
