#!/usr/bin/env bash
# sync-source.sh — reference 学习源镜像管理(形制移植自 one-creator reference-miner)。
#
# 镜像 = git submodule(reference/mirrors/<id>),钉 commit 消费;sources.yaml 的 ref 是唯一真相。
# ⚠️ 只挖不跑:镜像是被读的知识快照,不运行其代码、不装其依赖。
# ⚠️ 不自动跟随上游:刷新只更新镜像与 ref;变化要经 /mine-reference <id> 人审才吸收。
#
# 用法:
#   reference/sync-source.sh --add <id>   # 首次建镜像:submodule add + 钉当前 commit + 回写 ref
#   reference/sync-source.sh <id>         # 刷一个已有镜像到上游最新 + 回写 ref
#   reference/sync-source.sh --all        # 刷所有已建镜像
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # reference/
ROOT="$(cd "$HERE/.." && pwd)"                          # repo 根
SOURCES="$HERE/sources.yaml"
cd "$ROOT"

py_field() { # py_field <id> <field> -> value or empty
  python3 - "$SOURCES" "$1" "$2" <<'PY'
import sys, yaml
src = next((s for s in yaml.safe_load(open(sys.argv[1]))["sources"] if s["id"] == sys.argv[2]), None)
if src is None:
    sys.exit(f"✗ {sys.argv[2]}: 未在 sources.yaml 登记(先注册一行)")
v = src.get(sys.argv[3], "")
print(v if v is not None else "")
PY
}

write_ref() { # write_ref <id> <sha> — 只改该 id 块的 ref 行(无则插在 license 前),保注释
  python3 - "$SOURCES" "$1" "$2" <<'PY'
import re, sys
p, sid, ref = sys.argv[1:4]
lines = open(p, encoding="utf-8").read().splitlines(keepends=True)
in_block, done = False, False
out = []
for ln in lines:
    m = re.match(r"^  - id:\s*(\S+)", ln)
    if m:
        in_block = m.group(1) == sid
    if in_block and not done and re.match(r"^    ref:", ln):
        ln = re.sub(r"(^    ref:\s*)\S*", lambda x: x.group(1) + ref, ln)
        done = True
    elif in_block and not done and re.match(r"^    license:", ln):
        out.append(f"    ref: {ref}\n")
        done = True
    out.append(ln)
open(p, "w", encoding="utf-8").write("".join(out))
print(f"  ref → {ref}")
PY
}

add_one() {
  local id="$1" path="reference/mirrors/$1"
  [ -d "$path/.git" ] || [ -f "$path/.git" ] && { echo "✗ $id:镜像已存在,用 '$0 $id' 刷新" >&2; return 1; }
  local mirror repo
  mirror="$(py_field "$id" mirror)"
  [ "$mirror" = "False" ] && { echo "✗ $id:mirror:false(license 禁区,只读文档不镜像代码)" >&2; return 1; }
  repo="$(py_field "$id" repository)"
  echo "→ $id:submodule add https://$repo …"
  git submodule add -q "https://$repo" "$path"
  local ref; ref="$(git -C "$path" rev-parse --short HEAD)"
  write_ref "$id" "$ref"
  echo "✓ $id @ $ref(镜像已建 + ref 回写;记得 cp reference/miner-template.md reference/miners/$id.md)"
}

sync_one() {
  local id="$1" path="reference/mirrors/$1"
  [ -e "$path" ] || { echo "✗ $id:无镜像(用 --add 建)" >&2; return 1; }
  local before; before="$(git -C "$path" rev-parse --short HEAD 2>/dev/null || echo none)"
  # 失败不假成功:update 失败就报错返回,不 re-pin 旧 ref
  if ! git submodule update --remote --init -- "$path" >/dev/null 2>&1; then
    echo "✗ $id:submodule update 失败(网络/上游不可达?)—— ref 未变($before)" >&2
    return 1
  fi
  local ref; ref="$(git -C "$path" rev-parse --short HEAD)"
  write_ref "$id" "$ref"
  if [ "$ref" = "$before" ]; then echo "✓ $id @ $ref(已是最新)"; else
    echo "✓ $id @ $before → $ref(有上游 diff:跑 /mine-reference $id 评估,不自动吸收)"
  fi
}

case "${1:-}" in
  ""|-h|--help) sed -n '2,12p' "$0"; exit 2 ;;
  --add) shift; add_one "${1:?用法: --add <id>}" ;;
  --all)
    for d in reference/mirrors/*/; do
      [ -e "$d" ] || continue
      sync_one "$(basename "$d")" || true
    done ;;
  *) sync_one "$1" ;;
esac

echo "提醒:ref 变了 → git add reference/mirrors/<id> reference/sources.yaml .gitmodules 一起提交。"
