#!/usr/bin/env bash
# 每周批量跑的显式预设(agent-service-plan.md M-C5,创始人 2026-07-08 拍板:
# "默认先都使用腾讯")。LLM 步骤全走 router(腾讯 LKEAP tc-code/tc-think,单价见
# config/llm/prices.json)+ --live(vps_browser/hn_algolia 已是真代码,已配置的
# 目标直接触网;jobs/marketplace/reviews 三源 + enrich 三 fetcher 仍是桩,优雅
# 返回 []——接哪些站点仍是创始人待给的清单,见 agent-service-plan.md §5-①)。
#
# 特意做成一个 opt-in 脚本,而不是改 `idea run` 的裸参数默认值:
# * CLAUDE.md 硬规则——默认管线路径不得静默加真实外部调用;
# * `idea run`(无参数)必须继续保持无网络、零 token、确定性(CI/离线 demo 依赖这个)。
#
# 用法:scripts/weekly-run.sh [透传给 idea run 的额外参数...]
set -euo pipefail
cd "$(dirname "$0")/.."

exec idea run \
  --live \
  --generate-backend router \
  --judge-backend router \
  --persona-backend router \
  --persona-pressure-backend router \
  "$@"
